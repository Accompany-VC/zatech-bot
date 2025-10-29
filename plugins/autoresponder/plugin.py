"""Auto-responder plugin: greets users in #introductions and handles pattern-based responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from starlette import status
from urllib.parse import quote

from core.plugins import BasePlugin, PluginContext
from dashboards import AdminTab
from security.auth import require_auth
from security.validation import (
    sanitize_autoresponder_response,
    sanitize_channel_suggestions,
    sanitize_greeting_template,
    sanitize_model_identifier,
    sanitize_openai_api_key,
    sanitize_system_prompt,
    validate_autoresponder_regex,
)

NAMESPACE = "autoresponder"
RULES_KEY = "rules"
GREETER_SETTINGS_KEY = "greeter_settings"
GREETER_COUNTER_KEY = "greeter_count"
AI_GREETER_SETTINGS_KEY = "ai_greeter_settings"
AI_GREETER_COUNTER_KEY = "ai_greeter_count"
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
DEFAULT_RULES: List["AutoResponseRule"] = []
DEFAULT_GREETER_SETTINGS = {
    "greeting_template": "Welcome to the community, {mention}! We're excited to have you here.\n\nFeel free to take a look at our code of conduct: https://github.com/zatech/code-of-conduct\n\nand our wiki: https://wiki.zatech.co.za/",
    "enabled": True,
}
DEFAULT_AI_GREETER_SETTINGS = {
    "enabled": False,
    "openai_api_key": "",
    "model": "gpt-5-nano",
    "channel_suggestions": [
        "#general - General discussion",
        "#python - Python programming",
        "#javascript - JavaScript development",
        "#career - Career advice and opportunities",
        "#projects - Share your projects",
    ],
    "system_prompt": """You are a friendly community greeter for ZATech, a South African technology community.\n\nYour task is to warmly welcome a new member who just introduced themselves in the #introductions channel.\n\nBased on their introduction message, you should:\n1. Greet them warmly and acknowledge something specific from their introduction\n2. Suggest 2-3 relevant channels from the available channels list that match their interests\n3. Remind them about the Code of Conduct\n4. Mention the community wiki\n\nWhen suggesting channels, format them as Slack links using the pattern <#CHANNEL_ID|#channel-name>. You will receive channels with IDs and names below.\n\nKeep your response friendly, conversational, and not too long (2-3 short paragraphs max).\n\nAvailable channels to suggest:\n{channels}\n\nCode of Conduct: https://github.com/zatech/code-of-conduct\nWiki: https://wiki.zatech.co.za/""",
}


def _replace_markdown_links(text: str) -> str:
    """Convert common Markdown links to Slack mrkdwn links."""

    def _sub(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        return f"<{url}|{label}>"

    return MARKDOWN_LINK_PATTERN.sub(_sub, text)


def _build_message_payload(mention: str, body: str, *, prepend_mention: bool = False) -> Dict[str, Any]:
    """Prepare Slack payload with mrkdwn formatting and optional mention prefix."""

    normalized_body = _replace_markdown_links(body.strip())
    requires_prepend = prepend_mention or (mention not in normalized_body)

    if normalized_body:
        if requires_prepend:
            block_text = f"{mention}\n\n{normalized_body}"
            normalized_single_line = normalized_body.replace('\n', ' ')
            fallback_text = f"{mention} {normalized_single_line}"
        else:
            block_text = normalized_body
            normalized_single_line = normalized_body.replace('\n', ' ')
            fallback_text = normalized_single_line
    else:
        block_text = mention
        fallback_text = mention

    block_text = block_text.strip()
    fallback_text = fallback_text.strip()

    return {
        "text": fallback_text,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": block_text,
                },
            }
        ],
    }


def _extract_completion_text(message: Dict[str, Any]) -> str:
    """Normalize chat.completions message content into a plain string."""

    if isinstance(message, dict):
        data = message
    elif hasattr(message, "model_dump"):
        data = message.model_dump()
    else:
        data = {}
        if hasattr(message, "content"):
            data["content"] = getattr(message, "content")
        if hasattr(message, "refusal"):
            data["refusal"] = getattr(message, "refusal")

    content = data.get("content")
    parts: List[str] = []

    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                item_type = item.get("type")
                if item_type in {"text", "output_text"}:
                    candidate = str(item.get("text", "")).strip()
                    if candidate:
                        parts.append(candidate)
                elif item_type == "paragraph":
                    inner = item.get("elements") or []
                    paragraph_chunks = []
                    for element in inner:
                        if isinstance(element, dict) and element.get("type") in {"text", "output_text"}:
                            paragraph_chunks.append(str(element.get("text", "")))
                    if paragraph_chunks:
                        parts.append("".join(paragraph_chunks))

    if not parts and data.get("refusal"):
        refusal = data["refusal"]
        if isinstance(refusal, dict):
            text = refusal.get("text")
            if isinstance(text, str):
                parts.append(text)

    return "\n\n".join(chunk.strip() for chunk in parts if chunk and chunk.strip())


def _extract_response_text(response: Any) -> str:
    """Extract text from the Responses API payload."""

    output_text_attr = getattr(response, "output_text", None)
    if isinstance(output_text_attr, list):
        joined = "\n\n".join(str(chunk).strip() for chunk in output_text_attr if str(chunk).strip())
        if joined:
            return joined
    elif isinstance(output_text_attr, str) and output_text_attr.strip():
        return output_text_attr.strip()

    data: Dict[str, Any]

    if isinstance(response, dict):
        data = response
    elif hasattr(response, "model_dump"):
        data = response.model_dump()
    else:
        data = {}
        for attr in ("output", "candidates", "output_text"):
            if hasattr(response, attr):
                data[attr] = getattr(response, attr)

    output = data.get("output") or data.get("candidates")
    parts: List[str] = []

    if isinstance(output, list):
        for item in output:
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, list):
                    for content_item in content:
                        if isinstance(content_item, dict):
                            if content_item.get("type") in {"output_text", "text"}:
                                text_value = str(content_item.get("text", "")).strip()
                                if text_value:
                                    parts.append(text_value)
                            elif content_item.get("type") == "reasoning" and isinstance(content_item.get("summary"), dict):
                                summary_text = content_item["summary"].get("text")
                                if isinstance(summary_text, str) and summary_text.strip():
                                    parts.append(summary_text.strip())
            elif isinstance(item, str):
                parts.append(item)

    if not parts and isinstance(data.get("output_text"), list):
        parts.extend(str(chunk).strip() for chunk in data["output_text"] if str(chunk).strip())
    elif not parts and isinstance(data.get("output_text"), str):
        candidate = data["output_text"].strip()
        if candidate:
            parts.append(candidate)

    return "\n\n".join(chunk for chunk in parts if chunk)


@dataclass
class AutoResponseRule:
    pattern: str
    response: str
    flags: int = re.IGNORECASE

    def compiled(self) -> Optional[re.Pattern[str]]:
        try:
            return re.compile(self.pattern, self.flags)
        except re.error:
            return None


class AutoResponderPlugin(BasePlugin):
    key = "autoresponder"
    name = "AutoResponder"
    description = "Greets users in #introductions and auto-responds to pattern matches."

    def register(self, context: PluginContext) -> None:
        app = context.slack_app
        storage = context.storage
        templates_path = Path(__file__).parent / "templates"
        context.dashboard.add_template_dir(self.key, templates_path)

        async def get_rules() -> List[AutoResponseRule]:
            stored = await storage.get(NAMESPACE, RULES_KEY)
            if not stored:
                return list(DEFAULT_RULES)
            rules: List[AutoResponseRule] = []
            for item in stored:
                try:
                    pattern = str(item["pattern"])
                    response = str(item["response"])
                    flags = int(item.get("flags", re.IGNORECASE))
                except (KeyError, TypeError, ValueError):
                    continue
                candidate = AutoResponseRule(pattern=pattern, response=response, flags=flags)
                if candidate.compiled() is not None:
                    rules.append(candidate)
            return rules

        async def get_greeter_settings() -> Dict[str, Any]:
            stored = await storage.get(NAMESPACE, GREETER_SETTINGS_KEY) or {}
            if not isinstance(stored, dict):
                stored = {}
            return {**DEFAULT_GREETER_SETTINGS, **stored}

        async def get_ai_greeter_settings() -> Dict[str, Any]:
            stored = await storage.get(NAMESPACE, AI_GREETER_SETTINGS_KEY) or {}
            if not isinstance(stored, dict):
                stored = {}
            settings = {**DEFAULT_AI_GREETER_SETTINGS, **stored}
            model = str(settings.get("model", DEFAULT_AI_GREETER_SETTINGS["model"])).strip()
            if not model:
                model = DEFAULT_AI_GREETER_SETTINGS["model"]
            settings["model"] = model
            channel_suggestions = settings.get("channel_suggestions", [])
            if isinstance(channel_suggestions, str):
                settings["channel_suggestions"] = [
                    line.strip()
                    for line in channel_suggestions.split("\n")
                    if line.strip()
                ]
            else:
                settings["channel_suggestions"] = [
                    str(entry).strip()
                    for entry in channel_suggestions
                    if str(entry).strip()
                ]
            return settings

        async def generate_ai_greeting(
            user_message: str,
            settings: Dict[str, Any],
            channels_text: str,
            logger,
        ) -> Optional[str]:
            try:
                from openai import OpenAI
            except ImportError:
                logger.warning("OpenAI library not installed")
                return None

            api_key = settings.get("openai_api_key", "").strip()
            if not api_key:
                return None

            try:
                client = OpenAI(api_key=api_key)

                system_prompt = settings.get("system_prompt", DEFAULT_AI_GREETER_SETTINGS["system_prompt"])
                system_prompt = system_prompt.replace("{channels}", channels_text)

                response = client.responses.create(
                    model=settings.get("model", DEFAULT_AI_GREETER_SETTINGS["model"]),
                    input=[
                        {
                            "role": "system",
                            "content": [
                                {"type": "input_text", "text": system_prompt}
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": f"New member introduction: {user_message}",
                                }
                            ],
                        },
                    ],
                    max_output_tokens=750,
                    text={
                        "format": {"type": "text"},
                        "verbosity": "low",
                    },
                    reasoning={"effort": "minimal"},
                    tools=[],
                    store=False,
                )

                choice_text = _extract_response_text(response)
                if choice_text:
                    return choice_text
                return None
            except Exception as exc:  # pragma: no cover - network failure path
                logger.error("AI greeting generation failed: %s", exc)
                return None

        @app.message(re.compile(".+"))
        async def autoresponder_handler(message, say, context, client, logger):  # type: ignore[override]
            if message.get("bot_id") or message.get("user") == context.get("bot_user_id"):
                return

            # Check if this is #introductions channel - handle greetings first
            channel_id = message.get("channel", "")
            if channel_id:
                try:
                    result = await client.conversations_info(channel=channel_id)
                    channel_name = result.get("channel", {}).get("name", "")

                    # Handle #introductions greetings
                    if channel_name == "introductions":
                        greeter_settings = await get_greeter_settings()
                        ai_settings = await get_ai_greeter_settings()

                        if not message.get("thread_ts"):
                            user = message.get("user", "someone")
                            mention = f"<@{user}>"
                            user_message = message.get("text", "")
                            thread_ts = message.get("ts")

                            greeting_sent = False

                            if ai_settings.get("enabled") and ai_settings.get("openai_api_key", "").strip():
                                channels_text = "\n".join(ai_settings.get("channel_suggestions", []))
                                ai_text = await generate_ai_greeting(
                                    user_message,
                                    ai_settings,
                                    channels_text,
                                    logger,
                                )
                                if ai_text:
                                    ai_payload = _build_message_payload(mention, ai_text, prepend_mention=True)
                                    await say(thread_ts=thread_ts, **ai_payload)
                                    logger.info("AI greeted user %s in #introductions", user)
                                    current = await storage.get(NAMESPACE, AI_GREETER_COUNTER_KEY) or 0
                                    await storage.set(NAMESPACE, AI_GREETER_COUNTER_KEY, current + 1)
                                    greeting_sent = True
                                else:
                                    logger.error("Failed to generate AI greeting for user %s", user)

                            if not greeting_sent and greeter_settings.get("enabled", True):
                                greeting_text = greeter_settings["greeting_template"].replace("{mention}", mention)
                                payload = _build_message_payload(mention, greeting_text)
                                await say(thread_ts=thread_ts, **payload)
                                logger.info("Greeted user %s in #introductions", user)
                                current = await storage.get(NAMESPACE, GREETER_COUNTER_KEY) or 0
                                await storage.set(NAMESPACE, GREETER_COUNTER_KEY, current + 1)

                        return  # Don't process auto-response rules for #introductions
                except Exception as exc:
                    logger.error("AutoResponder introduction handler error: %s", exc)

            # Process normal auto-response rules
            text = message.get("text") or ""
            rules = await get_rules()
            for rule in rules:
                regex = rule.compiled()
                if regex and regex.search(text):
                    thread_ts = message.get("thread_ts") or message.get("ts")
                    user = message.get("user", "someone")
                    response_text = rule.response.replace("{mention}", f"<@{user}>")
                    await say(text=response_text, thread_ts=thread_ts)
                    break

        async def rules_tab_context(request: Request, plugin_ctx: PluginContext) -> Dict[str, Any]:
            rules = await get_rules()
            error = request.query_params.get("error", "")
            return {"rules": rules, "error": error}

        async def greeter_tab_context(request: Request, plugin_ctx: PluginContext) -> Dict[str, Any]:
            greeter_settings = await get_greeter_settings()
            ai_settings = await get_ai_greeter_settings()
            greeter_count = await storage.get(NAMESPACE, GREETER_COUNTER_KEY) or 0
            ai_greeting_count = await storage.get(NAMESPACE, AI_GREETER_COUNTER_KEY) or 0
            channels_text = "\n".join(ai_settings.get("channel_suggestions", []))
            if ai_settings.get("enabled"):
                active_mode = "ai"
            elif greeter_settings.get("enabled"):
                active_mode = "template"
            else:
                active_mode = "disabled"
            # Extract error from query params if present
            error = request.query_params.get("error", "")
            return {
                "greeter_settings": greeter_settings,
                "greeter_count": greeter_count,
                "ai_settings": ai_settings,
                "ai_greeting_count": ai_greeting_count,
                "channels_text": channels_text,
                "active_mode": active_mode,
                "error": error,
            }

        context.dashboard.register_tab(
            AdminTab(
                slug=self.key,
                label="AutoResponder",
                template=f"{self.key}/tab.html",
                description="Configure greetings and automatic responses.",
                order=20,
                context_provider=rules_tab_context,
            )
        )

        context.dashboard.register_tab(
            AdminTab(
                slug=f"{self.key}_greeter",
                label="AutoResponder: Greetings",
                template=f"{self.key}/greeter_tab.html",
                description="Manage #introductions greetings and AI settings.",
                order=21,
                context_provider=greeter_tab_context,
            )
        )

        self._get_rules = get_rules

    def register_routes(self, context: PluginContext) -> None:
        storage = context.storage
        logger = context.get_logger(self.key)

        @context.fastapi_app.post("/admin/tabs/autoresponder/rules")
        async def create_rule(request: Request, user: dict = Depends(require_auth)):
            form = await request.form()
            raw_pattern = str(form.get("pattern", ""))
            raw_response = str(form.get("response", ""))

            # Validate pattern and sanitize response
            try:
                cleaned_pattern = validate_autoresponder_regex(raw_pattern, max_length=500)
                cleaned_response = sanitize_autoresponder_response(raw_response, max_length=1000)
            except ValueError as exc:
                logger.warning("Invalid autoresponder rule from %s: %s", user.get("email"), exc)
                error_msg = quote(str(exc))
                return RedirectResponse(f"/admin/tabs/autoresponder?error={error_msg}", status_code=status.HTTP_303_SEE_OTHER)

            try:
                compiled = re.compile(cleaned_pattern)
            except re.error:
                error_msg = quote("Invalid regex syntax (this should not happen after validation)")
                return RedirectResponse(
                    f"/admin/tabs/autoresponder?error={error_msg}", status_code=status.HTTP_303_SEE_OTHER
                )

            rules = await storage.get(NAMESPACE, RULES_KEY) or []
            rules.append({
                "pattern": compiled.pattern,
                "response": cleaned_response,
                "flags": compiled.flags or re.IGNORECASE,
            })
            await storage.set(NAMESPACE, RULES_KEY, rules)
            return RedirectResponse("/admin/tabs/autoresponder", status_code=status.HTTP_303_SEE_OTHER)

        @context.fastapi_app.post("/admin/tabs/autoresponder/rules/delete")
        async def delete_rule(request: Request, user: dict = Depends(require_auth)):
            form = await request.form()
            index_raw = form.get("index")
            try:
                index = int(index_raw)
            except (TypeError, ValueError):
                return RedirectResponse("/admin/tabs/autoresponder", status_code=status.HTTP_303_SEE_OTHER)

            rules = await storage.get(NAMESPACE, RULES_KEY) or []
            if 0 <= index < len(rules):
                del rules[index]
                await storage.set(NAMESPACE, RULES_KEY, rules)
            return RedirectResponse("/admin/tabs/autoresponder", status_code=status.HTTP_303_SEE_OTHER)

        @context.fastapi_app.post("/admin/tabs/autoresponder_greeter/greeter/settings")
        async def update_greeter_settings(request: Request, user: dict = Depends(require_auth)):
            form = await request.form()

            raw_template = str(form.get("greeting_template", DEFAULT_GREETER_SETTINGS["greeting_template"]))
            
            # Sanitize greeting template
            try:
                greeting_template = sanitize_greeting_template(raw_template, max_length=2000)
            except ValueError as exc:
                logger.warning("Invalid greeter template from %s: %s", user.get("email"), exc)
                error_msg = quote(str(exc))
                return RedirectResponse(f"/admin/tabs/autoresponder_greeter?error={error_msg}", status_code=status.HTTP_303_SEE_OTHER)
            
            enabled = form.get("enabled") == "on"
            await storage.set(
                NAMESPACE,
                GREETER_SETTINGS_KEY,
                {"greeting_template": greeting_template, "enabled": enabled},
            )
            if enabled:
                ai_settings = await storage.get(NAMESPACE, AI_GREETER_SETTINGS_KEY) or {}
                if not isinstance(ai_settings, dict):
                    ai_settings = {}
                if ai_settings.get("enabled"):
                    ai_settings["enabled"] = False
                    await storage.set(NAMESPACE, AI_GREETER_SETTINGS_KEY, ai_settings)
            return RedirectResponse("/admin/tabs/autoresponder_greeter", status_code=status.HTTP_303_SEE_OTHER)

        @context.fastapi_app.post("/admin/tabs/autoresponder_greeter/ai/settings")
        async def update_ai_greeter_settings(request: Request, user: dict = Depends(require_auth)):
            form = await request.form()
            
            enabled = form.get("enabled") == "on"
            raw_api_key = str(form.get("openai_api_key", ""))
            raw_model = str(form.get("model", DEFAULT_AI_GREETER_SETTINGS["model"]))
            raw_system_prompt = str(form.get("system_prompt", ""))
            raw_channel_suggestions = str(form.get("channel_suggestions", ""))

            # Sanitize all inputs
            try:
                openai_api_key = sanitize_openai_api_key(raw_api_key, max_length=200)

                if raw_model.strip():
                    model = sanitize_model_identifier(raw_model, max_length=50)
                else:
                    model = DEFAULT_AI_GREETER_SETTINGS["model"]
                if raw_system_prompt.strip():
                    system_prompt = sanitize_system_prompt(raw_system_prompt, max_length=5000)
                else:
                    system_prompt = DEFAULT_AI_GREETER_SETTINGS["system_prompt"]
                cleaned_channel_text = sanitize_channel_suggestions(raw_channel_suggestions, max_length=2000)
                
                channel_suggestions = [
                    line.strip()
                    for line in cleaned_channel_text.split("\n")
                    if line.strip()
                ] if cleaned_channel_text else []
                
            except ValueError as exc:
                logger.warning("Invalid AI greeter settings from %s: %s", user.get("email"), exc)
                error_msg = quote(str(exc))
                return RedirectResponse(f"/admin/tabs/autoresponder_greeter?error={error_msg}", status_code=status.HTTP_303_SEE_OTHER)

            await storage.set(
                NAMESPACE,
                AI_GREETER_SETTINGS_KEY,
                {
                    "enabled": enabled,
                    "openai_api_key": openai_api_key,
                    "model": model,
                    "system_prompt": system_prompt,
                    "channel_suggestions": channel_suggestions,
                },
            )
            if enabled:
                greeter_settings = await storage.get(NAMESPACE, GREETER_SETTINGS_KEY) or {}
                if not isinstance(greeter_settings, dict):
                    greeter_settings = {}
                if greeter_settings.get("enabled"):
                    greeter_settings["enabled"] = False
                    await storage.set(NAMESPACE, GREETER_SETTINGS_KEY, greeter_settings)
            return RedirectResponse("/admin/tabs/autoresponder_greeter", status_code=status.HTTP_303_SEE_OTHER)

    async def on_shutdown(self, context: PluginContext) -> None:
        # Reset cached rules loader if needed
        if hasattr(self, "_get_rules"):
            delattr(self, "_get_rules")


plugin = AutoResponderPlugin()

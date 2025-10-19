"""Auto-responder plugin: greets users in #introductions and handles pattern-based responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette import status

from core.plugins import BasePlugin, PluginContext
from dashboards import AdminTab

NAMESPACE = "autoresponder"
RULES_KEY = "rules"
GREETER_SETTINGS_KEY = "greeter_settings"
GREETER_COUNTER_KEY = "greeter_count"
DEFAULT_RULES: List["AutoResponseRule"] = []
DEFAULT_GREETER_SETTINGS = {
    "greeting_template": "Welcome to the community, {mention}! We're excited to have you here.\n\nFeel free to take a look at our code of conduct: https://github.com/zatech/code-of-conduct\n\nand our wiki: https://wiki.zatech.co.za/",
    "enabled": True,
}


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
                        if greeter_settings.get("enabled", True):
                            # Only greet top-level messages (not thread replies)
                            if not message.get("thread_ts"):
                                user = message.get("user", "someone")
                                mention = f"<@{user}>"
                                greeting_text = greeter_settings["greeting_template"].replace("{mention}", mention)
                                thread_ts = message.get("ts")
                                await say(text=greeting_text, thread_ts=thread_ts)
                                logger.info("Greeted user %s in #introductions", user)

                                # Increment greeting counter
                                current = await storage.get(NAMESPACE, GREETER_COUNTER_KEY) or 0
                                await storage.set(NAMESPACE, GREETER_COUNTER_KEY, current + 1)
                        return  # Don't process automod rules for #introductions
                except Exception:
                    pass  # Continue processing if channel lookup fails

            # Process normal automod rules
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

        async def tab_context(request: Request, plugin_ctx: PluginContext) -> Dict[str, Any]:
            rules = await get_rules()
            greeter_settings = await get_greeter_settings()
            greeter_count = await storage.get(NAMESPACE, GREETER_COUNTER_KEY) or 0
            return {
                "rules": rules,
                "greeter_settings": greeter_settings,
                "greeter_count": greeter_count,
            }

        context.dashboard.register_tab(
            AdminTab(
                slug=self.key,
                label="AutoResponder",
                template=f"{self.key}/tab.html",
                description="Configure greetings and automatic responses.",
                order=20,
                context_provider=tab_context,
            )
        )

        self._get_rules = get_rules

    def register_routes(self, context: PluginContext) -> None:
        storage = context.storage

        @context.fastapi_app.post("/admin/tabs/autoresponder/rules")
        async def create_rule(request: Request):
            form = await request.form()
            pattern = str(form.get("pattern", "")).strip()
            response = str(form.get("response", "")).strip()
            try:
                compiled = re.compile(pattern)
            except re.error:
                return RedirectResponse("/admin/tabs/autoresponder", status_code=status.HTTP_303_SEE_OTHER)

            if not response:
                return RedirectResponse("/admin/tabs/autoresponder", status_code=status.HTTP_303_SEE_OTHER)

            rules = await storage.get(NAMESPACE, RULES_KEY) or []
            rules.append({"pattern": compiled.pattern, "response": response, "flags": compiled.flags or re.IGNORECASE})
            await storage.set(NAMESPACE, RULES_KEY, rules)
            return RedirectResponse("/admin/tabs/autoresponder", status_code=status.HTTP_303_SEE_OTHER)

        @context.fastapi_app.post("/admin/tabs/autoresponder/rules/delete")
        async def delete_rule(request: Request):
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

        @context.fastapi_app.post("/admin/tabs/autoresponder/greeter/settings")
        async def update_greeter_settings(request: Request):
            form = await request.form()
            raw_template = form.get("greeting_template", DEFAULT_GREETER_SETTINGS["greeting_template"])
            greeting_template = str(raw_template).strip()
            if not greeting_template:
                greeting_template = DEFAULT_GREETER_SETTINGS["greeting_template"]
            enabled = form.get("enabled") == "on"
            await storage.set(
                NAMESPACE,
                GREETER_SETTINGS_KEY,
                {"greeting_template": greeting_template, "enabled": enabled},
            )
            return RedirectResponse("/admin/tabs/autoresponder", status_code=status.HTTP_303_SEE_OTHER)

    async def on_shutdown(self, context: PluginContext) -> None:
        # Reset cached rules loader if needed
        if hasattr(self, "_get_rules"):
            delattr(self, "_get_rules")


plugin = AutoResponderPlugin()

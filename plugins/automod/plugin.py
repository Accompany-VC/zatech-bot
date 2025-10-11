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

NAMESPACE = "automod"
RULES_KEY = "rules"
DEFAULT_RULES: List["AutoModRule"] = []


@dataclass
class AutoModRule:
    pattern: str
    response: str
    flags: int = re.IGNORECASE

    def compiled(self) -> Optional[re.Pattern[str]]:
        try:
            return re.compile(self.pattern, self.flags)
        except re.error:
            return None


class AutoModPlugin(BasePlugin):
    key = "automod"
    name = "Automoderator"
    description = "Auto-responds when messages match configured patterns."

    def register(self, context: PluginContext) -> None:
        app = context.slack_app
        storage = context.storage
        templates_path = Path(__file__).parent / "templates"
        context.dashboard.add_template_dir(self.key, templates_path)

        async def get_rules() -> List[AutoModRule]:
            stored = await storage.get(NAMESPACE, RULES_KEY)
            if not stored:
                return list(DEFAULT_RULES)
            rules: List[AutoModRule] = []
            for item in stored:
                try:
                    pattern = str(item["pattern"])
                    response = str(item["response"])
                    flags = int(item.get("flags", re.IGNORECASE))
                except (KeyError, TypeError, ValueError):
                    continue
                candidate = AutoModRule(pattern=pattern, response=response, flags=flags)
                if candidate.compiled() is not None:
                    rules.append(candidate)
            return rules

        @app.message(re.compile(".+"))
        async def automod_handler(message, say, context):  # type: ignore[override]
            if message.get("bot_id") or message.get("user") == context.get("bot_user_id"):
                return
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
            return {"rules": rules}

        context.dashboard.register_tab(
            AdminTab(
                slug=self.key,
                label="AutoMod",
                template=f"{self.key}/tab.html",
                description="Configure keyword responses for moderators.",
                order=20,
                context_provider=tab_context,
            )
        )

        self._get_rules = get_rules

    def register_routes(self, context: PluginContext) -> None:
        storage = context.storage

        @context.fastapi_app.post("/admin/tabs/automod/rules")
        async def create_rule(request: Request):
            form = await request.form()
            pattern = str(form.get("pattern", "")).strip()
            response = str(form.get("response", "")).strip()
            try:
                compiled = re.compile(pattern)
            except re.error:
                return RedirectResponse("/admin/tabs/automod", status_code=status.HTTP_303_SEE_OTHER)

            if not response:
                return RedirectResponse("/admin/tabs/automod", status_code=status.HTTP_303_SEE_OTHER)

            rules = await storage.get(NAMESPACE, RULES_KEY) or []
            rules.append({"pattern": compiled.pattern, "response": response, "flags": compiled.flags or re.IGNORECASE})
            await storage.set(NAMESPACE, RULES_KEY, rules)
            return RedirectResponse("/admin/tabs/automod", status_code=status.HTTP_303_SEE_OTHER)

        @context.fastapi_app.post("/admin/tabs/automod/rules/delete")
        async def delete_rule(request: Request):
            form = await request.form()
            index_raw = form.get("index")
            try:
                index = int(index_raw)
            except (TypeError, ValueError):
                return RedirectResponse("/admin/tabs/automod", status_code=status.HTTP_303_SEE_OTHER)

            rules = await storage.get(NAMESPACE, RULES_KEY) or []
            if 0 <= index < len(rules):
                del rules[index]
                await storage.set(NAMESPACE, RULES_KEY, rules)
            return RedirectResponse("/admin/tabs/automod", status_code=status.HTTP_303_SEE_OTHER)

    async def on_shutdown(self, context: PluginContext) -> None:
        # Reset cached rules loader if needed
        if hasattr(self, "_get_rules"):
            delattr(self, "_get_rules")


plugin = AutoModPlugin()

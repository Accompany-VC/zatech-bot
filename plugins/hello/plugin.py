from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette import status

from core.plugins import BasePlugin, PluginContext
from dashboards import AdminTab


NAMESPACE = "hello"
COUNTER_KEY = "greetings_sent"
SETTINGS_KEY = "settings"
DEFAULT_SETTINGS = {
    "greeting_template": "Hey there {mention}!",
    "broadcast": False,
}


class HelloPlugin(BasePlugin):
    key = "hello"
    name = "Hello Responder"
    description = "Greets users when they say hello."

    def register(self, context: PluginContext) -> None:
        logger = context.get_logger(self.key)
        app = context.slack_app
        storage = context.storage
        templates_path = Path(__file__).parent / "templates"
        context.dashboard.add_template_dir("hello", templates_path)
        async def get_settings() -> Dict[str, Any]:
            stored = await storage.get(NAMESPACE, SETTINGS_KEY) or {}
            if not isinstance(stored, dict):
                stored = {}
            return {**DEFAULT_SETTINGS, **stored}

        @app.message(re.compile(r"\bhello\b", flags=re.IGNORECASE))
        async def handle_hello(message, say, context):  # type: ignore[override]
            if message.get("bot_id") or message.get("user") == context.get("bot_user_id"):
                return
            user = message.get("user", "someone")
            thread_ts = message.get("thread_ts") or message.get("ts")
            settings = await get_settings()
            mention = f"<@{user}>"
            text = settings["greeting_template"].replace("{mention}", mention).replace("{user}", mention)
            await say(
                text=text,
                thread_ts=thread_ts,
                reply_broadcast=settings.get("broadcast", False),
            )
            logger.debug("Responded to hello from %s", user)
            current = await storage.get(NAMESPACE, COUNTER_KEY) or 0
            await storage.set(NAMESPACE, COUNTER_KEY, current + 1)

        async def hello_tab_context(request, plugin_ctx: PluginContext) -> Dict[str, Any]:
            count = await storage.get(NAMESPACE, COUNTER_KEY) or 0
            settings = await get_settings()
            return {
                "stats": {"greetings_sent": count},
                "settings": settings,
            }

        context.dashboard.register_tab(
            AdminTab(
                slug="hello",
                label="Hello Plugin",
                template="hello/tab.html",
                description="Monitor greetings sent by the Hello responder.",
                order=10,
                context_provider=hello_tab_context,
            )
        )

    def register_routes(self, context: PluginContext) -> None:
        storage = context.storage

        @context.fastapi_app.post("/admin/tabs/hello/settings")
        async def update_settings(request: Request):
            form = await request.form()
            raw_template = form.get("greeting_template", DEFAULT_SETTINGS["greeting_template"])
            greeting_template = str(raw_template).strip()
            if not greeting_template:
                greeting_template = DEFAULT_SETTINGS["greeting_template"]
            broadcast = form.get("broadcast") == "on"
            await storage.set(
                NAMESPACE,
                SETTINGS_KEY,
                {"greeting_template": greeting_template, "broadcast": broadcast},
            )
            return RedirectResponse("/admin/tabs/hello", status_code=status.HTTP_303_SEE_OTHER)


plugin = HelloPlugin()

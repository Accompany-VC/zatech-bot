from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette import status

try:  # pragma: no cover - optional dependency fallback for tests
    from slack_sdk.errors import SlackApiError
except ImportError:  # pragma: no cover
    class SlackApiError(Exception):
        """Fallback Slack error when slack_sdk is unavailable."""

from core.plugins import BasePlugin, PluginContext
from dashboards import AdminTab
from .utils import (
    format_channel_archive_event,
    format_channel_created_event,
    format_channel_deleted_event,
    format_channel_reference,
    format_channel_rename_event,
    format_message_changed_event,
    format_message_deleted_event,
    format_team_join_event,
    format_user_change_event,
    normalize_channel_identifier,
)

NAMESPACE = "modlog"
SETTINGS_KEY = "settings"
DEFAULT_SETTINGS: Dict[str, str] = {"channel_id": ""}


class ModLogPlugin(BasePlugin):
    key = "modlog"
    name = "Moderation Log"
    description = "Captures key moderation events and forwards them to a configured channel."

    def register(self, context: PluginContext) -> None:
        logger = context.get_logger(self.key)
        app = context.slack_app
        storage = context.storage
        templates_path = Path(__file__).parent / "templates"
        context.dashboard.add_template_dir(self.key, templates_path)

        async def get_settings() -> Dict[str, str]:
            stored = await storage.get(NAMESPACE, SETTINGS_KEY) or {}
            if not isinstance(stored, dict):
                stored = {}
            return {**DEFAULT_SETTINGS, **stored}

        async def get_channel_id() -> Optional[str]:
            settings = await get_settings()
            channel_id = settings.get("channel_id", "").strip()
            return channel_id or None

        async def post_log(text: Optional[str]) -> None:
            if not text:
                return
            channel_id = await get_channel_id()
            if not channel_id:
                logger.debug("Skipping mod log message because no channel is configured")
                return
            try:
                await app.client.chat_postMessage(channel=channel_id, text=text)
            except SlackApiError as exc:  # pragma: no cover - depends on Slack API response
                logger.warning("Failed to send moderation log message: %s", exc)

        @app.event("team_join")
        async def handle_team_join(event: Dict[str, Any], **kwargs: Any) -> None:
            await post_log(format_team_join_event(event))

        @app.event("user_change")
        async def handle_user_change(event: Dict[str, Any], **kwargs: Any) -> None:
            await post_log(format_user_change_event(event))

        @app.event("channel_created")
        async def handle_channel_created(event: Dict[str, Any], **kwargs: Any) -> None:
            await post_log(format_channel_created_event(event))

        @app.event("channel_rename")
        async def handle_channel_rename(event: Dict[str, Any], **kwargs: Any) -> None:
            await post_log(format_channel_rename_event(event))

        @app.event("channel_deleted")
        async def handle_channel_deleted(event: Dict[str, Any], **kwargs: Any) -> None:
            await post_log(format_channel_deleted_event(event))

        @app.event("channel_archive")
        async def handle_channel_archive(event: Dict[str, Any], **kwargs: Any) -> None:
            await post_log(format_channel_archive_event(event, archived=True))

        @app.event("channel_unarchive")
        async def handle_channel_unarchive(event: Dict[str, Any], **kwargs: Any) -> None:
            await post_log(format_channel_archive_event(event, archived=False))

        @app.event("message")
        async def handle_message_events(event: Dict[str, Any], **kwargs: Any) -> None:
            subtype = event.get("subtype")
            if subtype == "message_deleted":
                await post_log(format_message_deleted_event(event))
            elif subtype == "message_changed":
                await post_log(format_message_changed_event(event))

        async def tab_context(request: Request, plugin_ctx: PluginContext) -> Dict[str, Any]:
            settings = await get_settings()
            channel_id = settings.get("channel_id") or ""
            preview = format_channel_reference(channel_id) if channel_id else None
            return {
                "settings": settings,
                "channel_preview": preview,
            }

        context.dashboard.register_tab(
            AdminTab(
                slug=self.key,
                label="Mod Log",
                template=f"{self.key}/tab.html",
                description="Configure moderation event logging.",
                order=30,
                context_provider=tab_context,
            )
        )

    def register_routes(self, context: PluginContext) -> None:
        storage = context.storage

        @context.fastapi_app.post("/admin/tabs/modlog/settings")
        async def update_settings(request: Request):
            form = await request.form()
            raw_channel = str(form.get("channel_id", "")).strip()
            channel_id = normalize_channel_identifier(raw_channel)
            settings = await storage.get(NAMESPACE, SETTINGS_KEY) or {}
            if not isinstance(settings, dict):
                settings = {}
            settings["channel_id"] = channel_id
            await storage.set(NAMESPACE, SETTINGS_KEY, settings)
            return RedirectResponse("/admin/tabs/modlog", status_code=status.HTTP_303_SEE_OTHER)


plugin = ModLogPlugin()

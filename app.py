import asyncio
import logging
import os
from contextlib import suppress

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler

from core.config import AppConfig
from core.events import EventRouter
from core.logging import setup_logging
from core.plugins import PluginContext, PluginManager
from core.slack import create_slack_app
from core.storage import InMemoryStorage
from dashboards import AdminTab, DashboardRegistry

# Load environment variables from .env if present
load_dotenv()


config = AppConfig.from_env()
setup_logging(config.log_level)
logger = logging.getLogger(__name__)

slack_app = create_slack_app(config)
api = FastAPI()
slack_handler = AsyncSlackRequestHandler(slack_app)
socket_mode_handler = AsyncSocketModeHandler(slack_app, config.slack_app_token)

event_router = EventRouter()
storage = InMemoryStorage()
plugin_manager = PluginManager()
templates = Jinja2Templates(directory="templates")
dashboard = DashboardRegistry(templates)

plugin_context = PluginContext(
    slack_app=slack_app,
    fastapi_app=api,
    config=config,
    event_router=event_router,
    storage=storage,
    dashboard=dashboard,
)
dashboard.attach_context(plugin_context)

for package in config.plugin_packages:
    plugin_manager.discover(package, enabled=config.enabled_plugins)

plugin_manager.register_all(plugin_context)


async def overview_context_provider(request: Request, ctx: PluginContext):
    return {
        "plugins": plugin_manager.plugins,
        "socket_status": "running",
        "workspace": os.getenv("SLACK_TEAM_NAME", "Unknown workspace"),
    }


dashboard.register_tab(
    AdminTab(
        slug="overview",
        label="Overview",
        template="admin/overview.html",
        description="System health summary and plugin list.",
        order=0,
        context_provider=overview_context_provider,
    )
)


@api.on_event("startup")
async def start_services() -> None:
    logger.info("Starting Socket Mode handler")
    api.state.socket_task = asyncio.create_task(socket_mode_handler.start_async())
    await plugin_manager.startup(plugin_context)


@api.on_event("shutdown")
async def stop_services() -> None:
    logger.info("Stopping Socket Mode handler")
    await plugin_manager.shutdown(plugin_context)
    await socket_mode_handler.close_async()
    task = getattr(api.state, "socket_task", None)
    if task:
        with suppress(asyncio.CancelledError):
            await task


@api.post("/slack/events")
async def slack_events(req: Request):
    return await slack_handler.handle(req)


@api.get("/health")
async def health_check() -> dict:
    return {"ok": True}


@api.get("/admin", response_class=HTMLResponse)
async def admin_index(request: Request):
    return await dashboard.render_index(request)


@api.get("/admin/tabs/{slug}", response_class=HTMLResponse)
async def admin_tab(slug: str, request: Request):
    return await dashboard.render_tab(slug, request)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:api",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "3000")),
        reload=False,
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"),
    )

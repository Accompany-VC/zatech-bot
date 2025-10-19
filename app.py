"""FastAPI + Slack Socket Mode bootstrap, plugin wiring, and admin dashboard."""

import asyncio
import logging
import os
from contextlib import suppress
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler

from core.config import AppConfig
from core.events import EventRouter
from core.logging import setup_logging
from core.plugins import PluginContext, PluginManager
from core.slack import create_slack_app
from core.storage import InMemoryStorage, SQLModelStorage, Storage
from security.auth import FirebaseAuth, require_auth
from security.cookies import set_auth_cookie, clear_auth_cookie
from security.rate_limit import rate_limiter
from security.csp import CSPMiddleware
from sqlalchemy.engine.url import make_url
from dashboards import AdminTab, DashboardRegistry

# Load environment variables from .env if present
load_dotenv()


config = AppConfig.from_env()
setup_logging(config.log_level)
logger = logging.getLogger(__name__)

slack_app = create_slack_app(config)
api = FastAPI()
api.add_middleware(CSPMiddleware)
slack_handler = AsyncSlackRequestHandler(slack_app)
socket_mode_handler = AsyncSocketModeHandler(slack_app, config.slack_app_token)
api.mount("/static", StaticFiles(directory="static"), name="static")

event_router = EventRouter()

if config.database_url:
    try:
        url = make_url(config.database_url)
        backend = url.get_backend_name()
    except Exception:  # pragma: no cover - invalid URLs fall back
        backend = None

    if backend in {"sqlite", "postgresql"}:
        storage = SQLModelStorage(config.database_url)
    else:
        logger.warning(
            "Unsupported DATABASE_URL backend '%s'; falling back to in-memory storage",
            backend,
        )
        storage = InMemoryStorage()
else:
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
    try:
        FirebaseAuth.initialize()
        logger.info("Firebase Auth Initialized.")
    except Exception as e:
        raise RuntimeError("Startup aborted: Firebase Auth initialization failed") from e
    await storage.init()
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
    await storage.close()


@api.post("/slack/events")
async def slack_events(req: Request):
    return await slack_handler.handle(req)


@api.get("/health")
async def health_check() -> dict:
    return {"ok": True}


@api.get("/admin/login", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})


@api.post("/admin/auth/set-token")
async def set_auth_token(request: Request):
    """Receive Firebase ID token from client and set secure cookie."""
    client_ip = request.client.host
    
    # Check rate limiting
    is_limited, seconds_remaining = rate_limiter.is_rate_limited(client_ip)
    if is_limited:
        logger.warning(f"Rate limit exceeded for IP {client_ip}, Lockout remaining: {seconds_remaining}s")
        raise HTTPException(status_code=429, detail=f"Too many login attempts. Try again in {seconds_remaining} seconds.")
    
    try:
        data = await request.json()
        id_token = data.get("token")
        
        if not id_token:
            raise HTTPException(status_code=400, detail="Token required")
        
        # Verify token and check user exists
        user_data = await FirebaseAuth.verify_token(id_token)
        if not user_data:
            rate_limiter.record_failure(client_ip)
            logger.warning(f"Failed login attempt from IP {client_ip} with invalid token")
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        user_exists = await FirebaseAuth.check_user_exists(user_data.get("uid"))
        if not user_exists:
            rate_limiter.record_failure(client_ip)
            logger.warning(f"Login attempt failed from IP {client_ip}, Reason: User not registered")
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Successful login - clear rate limit
        rate_limiter.reset_attempts(client_ip)
        logger.info(f"Login successful - User: {user_data.get('email')}, UID: {user_data.get('uid')}, IP: {client_ip}")
        
        # Set secure cookie
        response = JSONResponse(content={"status": "ok", "user": user_data.get("email")})
        set_auth_cookie(response, id_token)
        
        return response
        
    except HTTPException:
        raise

    except ValueError as json_error:
        logger.error(f"Invalid JSON from IP {client_ip}: {json_error}")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    except Exception as e:
        logger.error(f"Error setting auth token: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication failed")


@api.post("/admin/logout")
async def admin_logout(request: Request, user: dict = Depends(require_auth)):
    logger.info(f"User logged out - User: {user.get('email')}, UID: {user.get('uid')}")
    response = RedirectResponse(url="/admin/login", status_code=303)
    clear_auth_cookie(response)
    return response


@api.get("/admin", response_class=HTMLResponse)
async def admin_index(request: Request, _user: dict = Depends(require_auth)):
    return await dashboard.render_index(request)


@api.get("/admin/tabs/{slug}", response_class=HTMLResponse)
async def admin_tab(slug: str, request: Request, _user: dict = Depends(require_auth)):
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

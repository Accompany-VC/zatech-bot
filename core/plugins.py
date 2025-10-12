"""Plugin infrastructure: discovery, context wiring, and lifecycle helpers."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from abc import ABC
from dataclasses import dataclass
from types import ModuleType
from typing import Iterable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import FastAPI
    from slack_bolt.async_app import AsyncApp

from core.config import AppConfig
from core.events import EventRouter
from dashboards import DashboardRegistry
from core.storage import Storage


@dataclass(slots=True)
class PluginContext:
    slack_app: "AsyncApp"
    fastapi_app: "FastAPI"
    config: AppConfig
    event_router: EventRouter
    storage: Storage
    dashboard: DashboardRegistry

    def get_logger(self, key: str) -> logging.Logger:
        return logging.getLogger(f"plugins.{key}")


class BasePlugin(ABC):
    key: str = "base"
    name: str = "Base Plugin"
    description: str = ""
    version: str = "0.1.0"
    enabled_by_default: bool = True

    def register(self, context: PluginContext) -> None:
        """Register Slack listeners, event subscribers, etc."""

    def register_routes(self, context: PluginContext) -> None:
        """Register FastAPI routes for admin/dashboard integrations."""

    async def on_startup(self, context: PluginContext) -> None:
        """Async hook when FastAPI app starts."""

    async def on_shutdown(self, context: PluginContext) -> None:
        """Async hook when FastAPI app shuts down."""


class PluginLoadError(RuntimeError):
    pass


class PluginManager:
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger("plugins")
        self.plugins: List[BasePlugin] = []

    def discover(self, package: str, enabled: Optional[Iterable[str]] = None) -> None:
        enabled_set = {slug for slug in enabled or []}
        pkg = importlib.import_module(package)
        pkg_paths = getattr(pkg, "__path__", None)
        if not pkg_paths:
            self.logger.warning("Package %s has no __path__; skipping discovery", package)
            return

        for _, name, is_pkg in pkgutil.iter_modules(pkg_paths):
            if not is_pkg or name.startswith("_"):
                continue
            module_name = f"{package}.{name}.plugin"
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError as exc:
                self.logger.warning("Skipping plugin %s: %s", module_name, exc)
                continue

            plugin = self._extract_plugin(module)
            if plugin is None:
                self.logger.warning("Module %s does not expose a plugin instance", module_name)
                continue

            if enabled_set and plugin.key not in enabled_set:
                self.logger.info("Plugin %s disabled via configuration", plugin.key)
                continue

            if not enabled_set and not plugin.enabled_by_default:
                self.logger.info("Plugin %s disabled by default", plugin.key)
                continue

            self.logger.info("Loaded plugin %s (%s)", plugin.key, plugin.name)
            self.plugins.append(plugin)

    def _extract_plugin(self, module: ModuleType) -> Optional[BasePlugin]:
        plugin = getattr(module, "plugin", None)
        if isinstance(plugin, BasePlugin):
            return plugin
        for attr in ("Plugin", "get_plugin"):
            candidate = getattr(module, attr, None)
            if isinstance(candidate, BasePlugin):
                return candidate
            if callable(candidate):
                candidate_instance = candidate()  # type: ignore[misc]
                if isinstance(candidate_instance, BasePlugin):
                    return candidate_instance
        return None

    def register_all(self, context: PluginContext) -> None:
        for plugin in self.plugins:
            logger = context.get_logger(plugin.key)
            logger.debug("Registering plugin %s", plugin.key)
            plugin.register(context)
            plugin.register_routes(context)

    async def startup(self, context: PluginContext) -> None:
        for plugin in self.plugins:
            logger = context.get_logger(plugin.key)
            logger.debug("Starting plugin %s", plugin.key)
            await plugin.on_startup(context)

    async def shutdown(self, context: PluginContext) -> None:
        for plugin in self.plugins:
            logger = context.get_logger(plugin.key)
            logger.debug("Shutting down plugin %s", plugin.key)
            await plugin.on_shutdown(context)

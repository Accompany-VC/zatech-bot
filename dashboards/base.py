from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader, PrefixLoader

if False:  # pragma: no cover - typing hints
    from core.plugins import PluginContext


AdminContextProvider = Callable[[Request, "PluginContext"], Any]


@dataclass(slots=True)
class AdminTab:
    slug: str
    label: str
    template: str
    description: str = ""
    icon: Optional[str] = None
    context_provider: Optional[AdminContextProvider] = None
    order: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)


class DashboardRegistry:
    def __init__(self, templates: Jinja2Templates) -> None:
        self.templates = templates
        self.tabs: List[AdminTab] = []
        self._context: Optional["PluginContext"] = None
        self._prefix_loaders: Dict[str, PrefixLoader] = {}

    def attach_context(self, context: "PluginContext") -> None:
        self._context = context

    def register_tab(self, tab: AdminTab) -> None:
        if any(existing.slug == tab.slug for existing in self.tabs):
            raise ValueError(f"Dashboard tab with slug '{tab.slug}' already registered")
        self.tabs.append(tab)
        self.tabs.sort(key=lambda t: (t.order, t.label.lower()))

    def add_template_dir(self, namespace: str, path: Path) -> None:
        path = path.resolve()
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Template directory {path} does not exist")
        if namespace in self._prefix_loaders:
            return
        namespace_loader = PrefixLoader({namespace: FileSystemLoader(str(path))})
        self._prefix_loaders[namespace] = namespace_loader

        env = self.templates.env
        loader = env.loader
        if loader is None:
            env.loader = namespace_loader
        elif isinstance(loader, ChoiceLoader):
            loader.loaders.append(namespace_loader)
        else:
            env.loader = ChoiceLoader([loader, namespace_loader])

    async def _resolve_context(self, tab: AdminTab, request: Request) -> Dict[str, Any]:
        provider = tab.context_provider
        plugin_context = self._context
        if provider is None:
            return {}
        if plugin_context is None:
            raise RuntimeError("DashboardRegistry missing plugin context")
        result = provider(request, plugin_context)
        if inspect.isawaitable(result):
            result = await result  # type: ignore[assignment]
        if not isinstance(result, dict):
            raise TypeError("Admin tab context provider must return a mapping")
        return result

    async def render_index(self, request: Request) -> HTMLResponse:
        if self.tabs:
            first_tab = self.tabs[0]
            return await self.render_tab(first_tab.slug, request)
        context = {
            "request": request,
            "tabs": self.tabs,
        }
        return self.templates.TemplateResponse("admin/index.html", context)

    async def render_tab(self, slug: str, request: Request) -> HTMLResponse:
        for tab in self.tabs:
            if tab.slug == slug:
                template_context = await self._resolve_context(tab, request)
                template_context.update(
                    {
                        "request": request,
                        "tabs": self.tabs,
                        "active_tab": tab,
                    }
                )
                return self.templates.TemplateResponse(tab.template, template_context)
        raise HTTPException(status_code=404, detail="Tab not found")

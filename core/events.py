from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, Dict, List, Optional

EventHandler = Callable[[str, dict], Awaitable[None]]


class EventRouter:
    """Minimal async pub/sub router for internal events."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        async with self._lock:
            self._subscribers[event_type].append(handler)

    async def dispatch(self, event_type: str, payload: dict) -> None:
        listeners = list(self._subscribers.get(event_type, ()))
        for handler in listeners:
            await handler(event_type, payload)

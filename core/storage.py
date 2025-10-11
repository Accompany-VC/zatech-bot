from __future__ import annotations

import asyncio
from typing import Any, Dict, Tuple


class Storage:
    """Abstract storage API."""

    async def get(self, namespace: str, key: str) -> Any:  # pragma: no cover - interface
        raise NotImplementedError

    async def set(self, namespace: str, key: str, value: Any) -> None:  # pragma: no cover
        raise NotImplementedError

    async def delete(self, namespace: str, key: str) -> None:  # pragma: no cover
        raise NotImplementedError


class InMemoryStorage(Storage):
    """Simple in-memory storage for development and tests."""

    def __init__(self) -> None:
        self._data: Dict[Tuple[str, str], Any] = {}
        self._lock = asyncio.Lock()

    async def get(self, namespace: str, key: str) -> Any:
        async with self._lock:
            return self._data.get((namespace, key))

    async def set(self, namespace: str, key: str, value: Any) -> None:
        async with self._lock:
            self._data[(namespace, key)] = value

    async def delete(self, namespace: str, key: str) -> None:
        async with self._lock:
            self._data.pop((namespace, key), None)

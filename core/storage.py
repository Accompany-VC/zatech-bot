from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel


class Storage:
    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def get(self, namespace: str, key: str) -> Any:
        raise NotImplementedError

    async def set(self, namespace: str, key: str, value: Any) -> None:
        raise NotImplementedError

    async def delete(self, namespace: str, key: str) -> None:
        raise NotImplementedError


class InMemoryStorage(Storage):
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


class KeyValue(SQLModel, table=True):
    namespace: str = Field(primary_key=True)
    key: str = Field(primary_key=True)
    value: str


class SQLModelStorage(Storage):
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._initialised = False
        self._init_lock = asyncio.Lock()

    async def init(self) -> None:
        async with self._init_lock:
            if self._initialised:
                return
            if not self.database_url:
                raise RuntimeError("DATABASE_URL must be set for SQLModelStorage")

            # Lazily create engine + session factory
            if self._engine is None:
                try:
                    self._engine = create_async_engine(self.database_url, future=True)
                except ModuleNotFoundError as exc:  # pragma: no cover
                    raise RuntimeError(
                        "Missing database driver for URL '%s'. Install asyncpg/psycopg." % self.database_url
                    ) from exc
                self._session_factory = sessionmaker(
                    self._engine, class_=AsyncSession, expire_on_commit=False
                )

            # Retry table creation until DB is ready
            await self._create_tables_with_retry()
            self._initialised = True

    async def _create_tables_with_retry(self) -> None:
        assert self._engine is not None
        max_attempts = 12
        delay = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                async with self._engine.begin() as conn:
                    await conn.run_sync(SQLModel.metadata.create_all)
            except Exception as exc:
                if attempt == max_attempts:
                    raise
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10.0)
                continue
            else:
                break

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._initialised = False

    def _session(self) -> AsyncSession:
        if not self._session_factory:
            raise RuntimeError("SQLModelStorage not initialised; call init() first")
        return self._session_factory()

    async def get(self, namespace: str, key: str) -> Any:
        async with self._session() as session:
            record = await session.get(KeyValue, (namespace, key))
            if record is None:
                return None
            return json.loads(record.value)

    async def set(self, namespace: str, key: str, value: Any) -> None:
        async with self._session() as session:
            payload = json.dumps(value)
            record = await session.get(KeyValue, (namespace, key))
            if record is None:
                record = KeyValue(namespace=namespace, key=key, value=payload)
                session.add(record)
            else:
                record.value = payload
            await session.commit()

    async def delete(self, namespace: str, key: str) -> None:
        async with self._session() as session:
            record = await session.get(KeyValue, (namespace, key))
            if record is not None:
                await session.delete(record)
                await session.commit()

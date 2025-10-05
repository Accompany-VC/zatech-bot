from __future__ import annotations

from typing import List, Optional
from datetime import datetime, timezone

from sqlalchemy import insert, select, update, delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ...storage.models import AutoResponderRule


class AutoResponderRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def add(self, *, phrase: str, response_text: str, match_type: str = "contains", case_sensitive: bool = False, channel_id: Optional[str] = None) -> int:
        now = datetime.now(timezone.utc)
        async with self.engine.begin() as conn:
            res = await conn.execute(
                insert(AutoResponderRule)
                .values(
                    phrase=phrase,
                    response_text=response_text,
                    match_type=match_type,
                    case_sensitive=case_sensitive,
                    channel_id=channel_id,
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                )
                .returning(AutoResponderRule.id)
            )
            rid = res.scalar_one()
            return int(rid)

    async def list(self, *, channel_id: Optional[str] = None, limit: int = 50) -> List[dict]:
        async with self.engine.connect() as conn:
            stmt = select(
                AutoResponderRule.id,
                AutoResponderRule.enabled,
                AutoResponderRule.match_type,
                AutoResponderRule.case_sensitive,
                AutoResponderRule.channel_id,
                AutoResponderRule.phrase,
                AutoResponderRule.response_text,
            ).order_by(AutoResponderRule.id.desc()).limit(limit)
            if channel_id is None:
                stmt = stmt.where(AutoResponderRule.channel_id.is_(None))
            else:
                stmt = stmt.where((AutoResponderRule.channel_id == channel_id) | (AutoResponderRule.channel_id.is_(None)))
            res = await conn.execute(stmt)
            return [dict(row._mapping) for row in res.all()]

    async def enabled_for_channel(self, channel_id: str) -> List[AutoResponderRule]:
        async with AsyncSession(self.engine) as session:
            stmt = select(AutoResponderRule).where(
                (AutoResponderRule.enabled == True) & ((AutoResponderRule.channel_id == channel_id) | (AutoResponderRule.channel_id.is_(None)))  # noqa: E712
            ).order_by(AutoResponderRule.id.asc())
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def toggle(self, rid: int, enabled: bool) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                update(AutoResponderRule)
                .where(AutoResponderRule.id == rid)
                .values(enabled=enabled, updated_at=datetime.now(timezone.utc))
            )

    async def remove(self, rid: int) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(delete(AutoResponderRule).where(AutoResponderRule.id == rid))

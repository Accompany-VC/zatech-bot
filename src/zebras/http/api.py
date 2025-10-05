from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..app_context import get_context
from ..plugins.autoresponder.repository import AutoResponderRepository
from ..rules.repository import ChannelRuleRepository
from ..plugins.invite.repository import InviteSettingsRepository


# API Router
router = APIRouter(prefix="/api/v1")


# ============================================================================
# Auto Responder Models
# ============================================================================
class AutoResponderRuleCreate(BaseModel):
    phrase: str
    response_text: str
    match_type: str = "contains"
    case_sensitive: bool = False
    channel_id: Optional[str] = None


class AutoResponderRuleUpdate(BaseModel):
    enabled: Optional[bool] = None
    phrase: Optional[str] = None
    response_text: Optional[str] = None
    match_type: Optional[str] = None
    case_sensitive: Optional[bool] = None


class AutoResponderRuleResponse(BaseModel):
    id: int
    enabled: bool
    match_type: str
    case_sensitive: bool
    channel_id: Optional[str]
    phrase: str
    response_text: str


# ============================================================================
# Auto Responder Endpoints
# ============================================================================
@router.get("/autoresponder/rules", response_model=List[AutoResponderRuleResponse])
async def list_autoresponder_rules(channel_id: Optional[str] = None, limit: int = 100):
    """List all autoresponder rules, optionally filtered by channel."""
    ctx = get_context()
    repo = AutoResponderRepository(ctx.engine)
    rules = await repo.list(channel_id=channel_id, limit=limit)
    return rules


@router.post("/autoresponder/rules", response_model=Dict[str, Any])
async def create_autoresponder_rule(rule: AutoResponderRuleCreate):
    """Create a new autoresponder rule."""
    ctx = get_context()
    repo = AutoResponderRepository(ctx.engine)

    if rule.match_type not in ("contains", "exact", "regex"):
        raise HTTPException(status_code=400, detail="Invalid match_type")

    rule_id = await repo.add(
        phrase=rule.phrase,
        response_text=rule.response_text,
        match_type=rule.match_type,
        case_sensitive=rule.case_sensitive,
        channel_id=rule.channel_id
    )
    return {"id": rule_id, "message": "Rule created successfully"}


@router.patch("/autoresponder/rules/{rule_id}")
async def update_autoresponder_rule(rule_id: int, updates: AutoResponderRuleUpdate):
    """Update an autoresponder rule (currently supports toggling enabled)."""
    ctx = get_context()
    repo = AutoResponderRepository(ctx.engine)

    if updates.enabled is not None:
        await repo.toggle(rule_id, updates.enabled)

    return {"message": "Rule updated successfully"}


@router.delete("/autoresponder/rules/{rule_id}")
async def delete_autoresponder_rule(rule_id: int):
    """Delete an autoresponder rule."""
    ctx = get_context()
    repo = AutoResponderRepository(ctx.engine)
    await repo.remove(rule_id)
    return {"message": "Rule deleted successfully"}


@router.post("/autoresponder/rules/{rule_id}/test")
async def test_autoresponder_rule(rule_id: int, test_text: str):
    """Test if a rule matches a given text."""
    ctx = get_context()
    repo = AutoResponderRepository(ctx.engine)
    # This is a placeholder - actual matching logic is in the plugin
    # For now, return a simple response
    return {"matches": False, "message": "Test functionality coming soon"}


# ============================================================================
# Channel Rules Models
# ============================================================================
class ChannelRuleUpdate(BaseModel):
    allow_bots: Optional[bool] = None
    allow_top_level_posts: Optional[bool] = None
    allow_thread_replies: Optional[bool] = None


class ChannelRuleResponse(BaseModel):
    channel_id: str
    allow_bots: bool
    allow_top_level_posts: bool
    allow_thread_replies: bool


# ============================================================================
# Channel Rules Endpoints
# ============================================================================
@router.get("/rules/{channel_id}", response_model=Optional[ChannelRuleResponse])
async def get_channel_rules(channel_id: str):
    """Get rules for a specific channel."""
    ctx = get_context()
    repo = ChannelRuleRepository(ctx.engine)
    rules = await repo.get(channel_id)

    if not rules or not hasattr(rules, "allow_bots"):
        return None

    return {
        "channel_id": channel_id,
        "allow_bots": rules.allow_bots,
        "allow_top_level_posts": rules.allow_top_level_posts,
        "allow_thread_replies": rules.allow_thread_replies
    }


@router.put("/rules/{channel_id}", response_model=Dict[str, Any])
async def update_channel_rules(channel_id: str, rule_updates: ChannelRuleUpdate):
    """Update rules for a specific channel."""
    ctx = get_context()
    repo = ChannelRuleRepository(ctx.engine)

    await repo.upsert(
        channel_id,
        allow_bots=rule_updates.allow_bots,
        allow_top_level_posts=rule_updates.allow_top_level_posts,
        allow_thread_replies=rule_updates.allow_thread_replies
    )

    return {"message": "Channel rules updated successfully"}


# ============================================================================
# Invite Helper Models
# ============================================================================
class InviteSettingsUpdate(BaseModel):
    admin_channel_id: Optional[str] = None
    audit_channel_id: Optional[str] = None
    notify_on_join: Optional[bool] = None
    dm_message: Optional[str] = None


class InviteSettingsResponse(BaseModel):
    admin_channel_id: Optional[str]
    audit_channel_id: Optional[str]
    notify_on_join: bool
    dm_message: Optional[str]


# ============================================================================
# Invite Helper Endpoints
# ============================================================================
@router.get("/invite/settings", response_model=Optional[InviteSettingsResponse])
async def get_invite_settings():
    """Get invite helper settings."""
    ctx = get_context()
    repo = InviteSettingsRepository(ctx.engine)
    settings = await repo.get()

    if not settings:
        return None

    return {
        "admin_channel_id": settings.admin_channel_id,
        "audit_channel_id": settings.audit_channel_id,
        "notify_on_join": settings.notify_on_join if hasattr(settings, "notify_on_join") else False,
        "dm_message": settings.dm_message if hasattr(settings, "dm_message") else None
    }


@router.put("/invite/settings", response_model=Dict[str, Any])
async def update_invite_settings(settings_update: InviteSettingsUpdate):
    """Update invite helper settings."""
    ctx = get_context()
    repo = InviteSettingsRepository(ctx.engine)

    await repo.upsert(
        admin_channel_id=settings_update.admin_channel_id,
        audit_channel_id=settings_update.audit_channel_id,
        notify_on_join=settings_update.notify_on_join,
        dm_message=settings_update.dm_message
    )

    return {"message": "Invite settings updated successfully"}


# ============================================================================
# Channels Endpoint
# ============================================================================
@router.get("/channels")
async def list_channels():
    """List all available channels."""
    try:
        client = await get_context().web_client()
    except Exception:
        return []

    channels: list[dict] = []
    cursor = None
    types = "public_channel,private_channel"

    for _ in range(5):  # Fetch up to 5 pages
        resp = await client.conversations_list(limit=200, cursor=cursor, types=types)
        channels.extend([
            {"id": c.get("id"), "name": c.get("name")}
            for c in resp.get("channels", [])
        ])
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    channels.sort(key=lambda x: (x.get("name") or "").lower())
    return channels


# ============================================================================
# Stats Endpoint (for Dashboard)
# ============================================================================
@router.get("/stats")
async def get_stats():
    """Get dashboard statistics."""
    ctx = get_context()
    auto_repo = AutoResponderRepository(ctx.engine)
    rules_repo = ChannelRuleRepository(ctx.engine)
    invite_repo = InviteSettingsRepository(ctx.engine)

    # Get autoresponder stats
    all_rules = await auto_repo.list(limit=1000)
    active_rules = [r for r in all_rules if r.get("enabled")]
    global_rules = [r for r in all_rules if r.get("channel_id") is None]

    # Get channel rules stats (count channels with rules)
    from sqlalchemy import select, func
    from zebras.storage.models import ChannelRule
    async with ctx.engine.connect() as conn:
        result = await conn.execute(
            select(func.count()).select_from(ChannelRule)
        )
        channels_with_rules = result.scalar() or 0

    # Get invite helper status
    invite_settings = await invite_repo.get()
    invite_configured = bool(
        invite_settings and
        (invite_settings.admin_channel_id or invite_settings.audit_channel_id)
    )

    return {
        "autoresponder": {
            "total_rules": len(all_rules),
            "active_rules": len(active_rules),
            "global_rules": len(global_rules)
        },
        "channels": {
            "total": 0,
            "with_rules": channels_with_rules
        },
        "invite": {
            "configured": invite_configured
        }
    }

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from slack_sdk.web.async_client import AsyncWebClient

from ...plugin import Registry
from ...app_context import get_context
from .repository import AutoResponderRepository


async def _client() -> AsyncWebClient:
    ctx = get_context()
    return await ctx.web_client()


def _matches(rule, text: str) -> bool:
    if not rule.case_sensitive:
        text_cmp = text.lower()
        phrase = (rule.phrase or "").lower()
    else:
        text_cmp = text
        phrase = rule.phrase or ""
    if rule.match_type == "contains":
        return phrase in text_cmp
    if rule.match_type == "exact":
        return text_cmp == phrase
    if rule.match_type == "regex":
        flags = 0 if rule.case_sensitive else re.IGNORECASE
        try:
            return re.search(rule.phrase, text, flags) is not None
        except re.error:
            return False
    return False


def register(reg: Registry) -> None:
    import logging
    log = logging.getLogger("zebras.plugins.autoresponder")

    async def repo() -> AutoResponderRepository:
        return AutoResponderRepository(get_context().engine)

    @reg.events.on("message")
    async def on_message(payload: Dict[str, Any]) -> None:
        e = payload.get("event", payload)
        log.debug(f"Autoresponder received message event: {e}")

        if e.get("subtype"):
            log.debug(f"Skipping message with subtype: {e.get('subtype')}")
            return
        text = e.get("text") or ""
        if not text:
            log.debug("Skipping message with no text")
            return
        channel = e.get("channel")
        ts = e.get("ts")
        rules = await (await repo()).enabled_for_channel(channel)
        log.debug(f"Found {len(rules)} enabled rules for channel {channel}")

        for r in rules:
            # Defensive: ensure we have a rule object with expected attrs
            if not hasattr(r, "phrase") or not hasattr(r, "response_text") or not hasattr(r, "match_type") or not hasattr(r, "case_sensitive"):
                log.warning(f"Rule {r.id if hasattr(r, 'id') else 'unknown'} missing required attributes")
                continue
            log.debug(f"Checking rule {r.id}: phrase='{r.phrase}', match_type={r.match_type}, text='{text}'")
            if _matches(r, text):
                log.info(f"Rule {r.id} matched! Sending response: {r.response_text}")
                client = await _client()
                await client.chat_postMessage(channel=channel, text=r.response_text, thread_ts=ts)
                break  # respond once per message
        else:
            log.debug(f"No rules matched for text: '{text}'")

    @reg.commands.slash("/auto")
    async def auto_cmd(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Manage auto-responder rules.

        Usage:
        /auto add phrase:"hello" reply:"Hi there" match:contains scope:here case:off
        /auto list [here|global]
        /auto enable <id> | disable <id> | delete <id>
        """
        text = (payload.get("text") or "").strip()
        channel_id = payload.get("channel_id")
        r = await repo()

        def parse_kv(s: str) -> dict:
            out = {}
            # very simple parser for key:"value with spaces"
            for m in re.finditer(r"(\w+):\"([^\"]*)\"", s):
                out[m.group(1)] = m.group(2)
            # and key:value
            for m in re.finditer(r"(\w+):([^\s\"]+)", s):
                out.setdefault(m.group(1), m.group(2))
            return out

        if text.startswith("add "):
            args = parse_kv(text[4:])
            phrase = args.get("phrase") or args.get("p")
            reply = args.get("reply") or args.get("r")
            match = (args.get("match") or "contains").lower()
            case = (args.get("case") or "off").lower() in ("on", "true", "1")
            scope = (args.get("scope") or "here").lower()
            if match not in ("contains", "exact", "regex"):
                return {"response_type": "ephemeral", "text": "match must be one of: contains|exact|regex"}
            if not phrase or not reply:
                return {"response_type": "ephemeral", "text": "Provide phrase:" + '".."' + " and reply:" + '".."'}
            target = None if scope == "global" else channel_id
            rid = await r.add(phrase=phrase, response_text=reply, match_type=match, case_sensitive=case, channel_id=target)
            scope_label = "global" if target is None else f"<#{channel_id}>"
            return {"response_type": "ephemeral", "text": f"Added rule #{rid} ({match}, case={'on' if case else 'off'}) in {scope_label}"}

        if text.startswith("list"):
            scope = text.split(" ", 1)[1].strip() if " " in text else "here"
            target = None if scope == "global" else channel_id
            rules = await r.list(channel_id=target)
            if not rules:
                return {"response_type": "ephemeral", "text": "No rules found."}
            lines = [f"#{x.id} [{'on' if x.enabled else 'off'}] ({x.match_type}) {'GLOBAL' if x.channel_id is None else '<#'+x.channel_id+'>'} — {x.phrase!r} -> {x.response_text!r}" for x in rules]
            return {"response_type": "ephemeral", "text": "\n".join(lines)}

        m = re.match(r"^(enable|disable)\s+(\d+)$", text)
        if m:
            action, sid = m.group(1), int(m.group(2))
            await r.toggle(sid, enabled=(action == "enable"))
            return {"response_type": "ephemeral", "text": f"{action.title()}d rule #{sid}"}

        m = re.match(r"^delete\s+(\d+)$", text)
        if m:
            sid = int(m.group(1))
            await r.remove(sid)
            return {"response_type": "ephemeral", "text": f"Deleted rule #{sid}"}

        return {
            "response_type": "ephemeral",
            "text": "Usage:\n/auto add phrase:\"hello\" reply:\"Hi\" match:contains scope:here case:off\n/auto list [here|global]\n/auto enable <id> | disable <id> | delete <id>",
        }

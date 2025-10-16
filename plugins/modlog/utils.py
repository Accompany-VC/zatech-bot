from __future__ import annotations

from typing import Any, Mapping, Optional

DEFAULT_SNIPPET_LIMIT = 200


def normalize_channel_identifier(raw: str) -> str:
    candidate = raw.strip()
    if not candidate:
        return ""
    if candidate.startswith("<#") and candidate.endswith(">"):
        inner = candidate[2:-1]
        if "|" in inner:
            inner = inner.split("|", 1)[0]
        return inner.strip()
    if candidate.startswith("#"):
        return candidate
    if candidate.startswith("C") or candidate.startswith("G"):
        return candidate
    return f"#{candidate}"


def format_channel_reference(channel_id: Optional[str], fallback_name: Optional[str] = None) -> str:
    if not channel_id:
        return fallback_name or "an unknown channel"
    if channel_id.startswith("C") or channel_id.startswith("G"):
        if fallback_name:
            return f"<#{channel_id}|{fallback_name}>"
        return f"<#{channel_id}>"
    if channel_id.startswith("#"):
        return channel_id
    return f"#{channel_id}"


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def make_snippet(value: Optional[str], limit: int = DEFAULT_SNIPPET_LIMIT) -> Optional[str]:
    if not value:
        return None
    collapsed = _collapse_whitespace(value)
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + "…"


def describe_user(user: Mapping[str, Any]) -> str:
    user_id = user.get("id") or user.get("user")
    profile = user.get("profile") or {}
    display_name = profile.get("display_name") or profile.get("display_name_normalized")
    real_name = profile.get("real_name") or user.get("real_name")
    label = display_name or real_name
    if user_id:
        if label and label != user_id:
            return f"<@{user_id}> ({label})"
        return f"<@{user_id}>"
    return label or "Unknown user"


def format_team_join_event(event: Mapping[str, Any]) -> Optional[str]:
    user = event.get("user")
    if not isinstance(user, Mapping):
        return None
    return f":tada: {describe_user(user)} joined the workspace."


def format_user_change_event(event: Mapping[str, Any]) -> Optional[str]:
    user = event.get("user")
    if not isinstance(user, Mapping):
        return None
    profile = user.get("profile") or {}
    bits = []
    for key, label in (
        ("display_name", "display name"),
        ("title", "title"),
        ("status_text", "status"),
    ):
        value = profile.get(key)
        if value:
            bits.append(f"{label}: *{_collapse_whitespace(str(value))}*")
    details = "; ".join(bits)
    base = f":memo: Updated profile for {describe_user(user)}."
    if details:
        return f"{base} ({details})"
    return base


def format_channel_created_event(event: Mapping[str, Any]) -> Optional[str]:
    channel = event.get("channel")
    if isinstance(channel, Mapping):
        channel_id = channel.get("id") or channel.get("channel_id")
        name = channel.get("name")
        creator = channel.get("creator")
    else:
        channel_id = event.get("channel")
        name = None
        creator = event.get("creator")
    pieces = [f":sparkles: Channel created: {format_channel_reference(channel_id, name)}"]
    if creator:
        pieces.append(f"by <@{creator}>")
    return " ".join(pieces)


def format_channel_rename_event(event: Mapping[str, Any]) -> Optional[str]:
    channel = event.get("channel")
    if not isinstance(channel, Mapping):
        return None
    channel_id = channel.get("id")
    new_name = channel.get("name")
    previous_name = channel.get("previous_name") or event.get("old_name")
    ref = format_channel_reference(channel_id, new_name)
    if previous_name:
        return f":label: Channel renamed: {ref} (was #{previous_name})."
    return f":label: Channel renamed: {ref}."


def format_channel_deleted_event(event: Mapping[str, Any]) -> Optional[str]:
    channel_id = event.get("channel") or event.get("channel_id")
    actor = event.get("actor") or event.get("user")
    pieces = [f":no_entry_sign: Channel deleted: {format_channel_reference(channel_id)}"]
    if actor:
        pieces.append(f"by <@{actor}>")
    return " ".join(pieces)


def format_channel_archive_event(event: Mapping[str, Any], archived: bool) -> Optional[str]:
    channel_id = event.get("channel") or event.get("channel_id")
    actor = event.get("user") or event.get("actor")
    action = "archived" if archived else "unarchived"
    pieces = [f":file_folder: Channel {action}: {format_channel_reference(channel_id)}"]
    if actor:
        pieces.append(f"by <@{actor}>")
    return " ".join(pieces)


def format_message_deleted_event(event: Mapping[str, Any]) -> Optional[str]:
    channel_id = event.get("channel")
    previous = event.get("previous_message") or {}
    actor = event.get("user")
    author = previous.get("user")
    base_pieces = [f":wastebasket: Message deleted in {format_channel_reference(channel_id)}"]
    if author:
        base_pieces.append(f"from <@{author}>")
    if actor and actor != author:
        base_pieces.append(f"by <@{actor}>")
    text = " ".join(base_pieces)
    snippet = make_snippet(previous.get("text"))
    if snippet:
        return f"{text}\n> {snippet}"
    return text


def format_message_changed_event(event: Mapping[str, Any]) -> Optional[str]:
    channel_id = event.get("channel")
    message = event.get("message") or {}
    previous = event.get("previous_message") or {}
    author = message.get("user") or previous.get("user")
    editor = message.get("edited", {}).get("user") or event.get("user")
    pieces = [f":pencil2: Message edited in {format_channel_reference(channel_id)}"]
    if author:
        pieces.append(f"by <@{author}>")
    if editor and editor != author:
        pieces.append(f"(edited by <@{editor}>)")
    header = " ".join(pieces)
    before_snippet = make_snippet(previous.get("text"))
    after_snippet = make_snippet(message.get("text"))
    lines = [header]
    if before_snippet:
        lines.append(f"> *Before:* {before_snippet}")
    if after_snippet:
        lines.append(f"> *After:* {after_snippet}")
    return "\n".join(lines)


__all__ = [
    "normalize_channel_identifier",
    "format_channel_reference",
    "make_snippet",
    "describe_user",
    "format_team_join_event",
    "format_user_change_event",
    "format_channel_created_event",
    "format_channel_rename_event",
    "format_channel_deleted_event",
    "format_channel_archive_event",
    "format_message_deleted_event",
    "format_message_changed_event",
]


"""Input validation and sanitization utilities for the modlog plugin."""

from __future__ import annotations

import re


def sanitize_channel_input(value: str, max_length: int = 50) -> str:
    """Sanitize the raw channel id input from the ModLog settings form."""

    if not isinstance(value, str):
        raise ValueError("Value must be a string")
    
    # Remove null bytes and trim whitespace
    value = value.replace("\x00", "").strip()

    if not value:
        return ""
    
    # Enforce length limit
    if len(value) > max_length:
        raise ValueError(f"Value too long (max {max_length} characters)")
    
    return value


def validate_slack_channel_identifier(value: str) -> bool:
    """
    Validate a normalized Slack channel identifier.
    Accepts:
      - Slack channel/group IDs: C[A-Z0-9]+ or G[A-Z0-9]+
      - Channel names with leading #: #[A-Za-z0-9._-]+
    """
    if not isinstance(value, str):
        raise ValueError("Channel identifier must be a string")
    
    if not value:
        return True  # empty allowed (means unset)

    # Validate against allowed patterns
    if re.match(r"^(?:[CG][A-Z0-9]+|#[A-Za-z0-9._-]+)$", value):
        return True

    raise ValueError("Invalid channel identifier")

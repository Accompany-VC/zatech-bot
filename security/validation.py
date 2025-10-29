"""Input validation and sanitization utilities for plugins."""

from __future__ import annotations

import re


# ---- ModLog ----

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
        return True 

    # Validate against allowed patterns
    if re.match(r"^(?:[CG][A-Z0-9]+|#[A-Za-z0-9._-]+)$", value):
        return True

    raise ValueError("Invalid channel identifier")


# ---- AutoResponder ----

def validate_autoresponder_regex(pattern: str, max_length: int = 500) -> str:
    """Validate an AutoResponder rule regex pattern."""

    if not isinstance(pattern, str) or not pattern:
        raise ValueError("Pattern cannot be empty")
    
    # Remove null bytes
    pattern = pattern.replace("\x00", "")

    # Enforce length limit
    if len(pattern) > max_length:
        raise ValueError(f"Pattern too long (max {max_length} characters)")
    
    # Validate regex syntax
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex syntax: {str(exc)}")
    
    return pattern


def sanitize_autoresponder_response(text: str, max_length: int = 1000) -> str:
    """Sanitize AutoResponder response text."""

    if not isinstance(text, str):
        raise ValueError("Response cannot be empty")
    
    # Remove null bytes and trim whitespace
    text = text.replace("\x00", "").strip()

    if not text:
        raise ValueError("Response cannot be empty")
    # Enforce length limit
    if len(text) > max_length:
        raise ValueError(f"Response too long (max {max_length} characters)")
    
    return text


# ---- AutoResponder:Greetings ----

def sanitize_greeting_template(text: str, max_length: int = 2000) -> str:
    """Sanitize greeting template text."""

    if not isinstance(text, str):
        raise ValueError("Greeting template must be a string")
    
    # Remove null bytes and trim whitespace
    text = text.replace("\x00", "").strip()

    if not text:
        raise ValueError("Greeting template cannot be empty")
    
    # Enforce length limit
    if len(text) > max_length:
        raise ValueError(f"Greeting template too long (max {max_length} characters)")
    
    return text


def sanitize_openai_api_key(key: str, max_length: int = 200) -> str:
    """Sanitize OpenAI API key input."""

    if not isinstance(key, str):
        raise ValueError("API key must be a string")
    
    # Remove null bytes and trim whitespace
    key = key.replace("\x00", "").strip()

    if not key:
        return ""
    
    # Enforce length limit
    if len(key) > max_length:
        raise ValueError(f"API key too long (max {max_length} characters)")
    return key


def sanitize_model_identifier(value: str, max_length: int = 50) -> str:
    """Sanitize model identifier"""

    if not isinstance(value, str):
        raise ValueError("Model identifier must be a string")
    
    # Remove null bytes and trim whitespace
    value = value.replace("\x00", "").strip()

    if not value:
        raise ValueError("Model identifier cannot be empty")
    
    # Enforce length limit
    if len(value) > max_length:
        raise ValueError(f"Model identifier too long (max {max_length} characters)")
    
    # Validate allowed characters
    if not re.match(r"^[a-zA-Z0-9._-]+$", value):
        raise ValueError("Model identifier contains invalid characters (use only letters, numbers, dots, hyphens, underscores)")
    
    return value


def sanitize_system_prompt(text: str, max_length: int = 5000) -> str:
    """Sanitize system prompt."""

    if not isinstance(text, str):
        raise ValueError("System prompt must be a string")
    
    # Remove null bytes and trim whitespace
    text = text.replace("\x00", "").strip()

    if not text:
        raise ValueError("System prompt cannot be empty")
    
    # Enforce length limit
    if len(text) > max_length:
        raise ValueError(f"System prompt too long (max {max_length} characters)")
    return text


def sanitize_channel_suggestions(text: str, max_length: int = 2000) -> str:
    """Sanitize channel suggestions."""

    if not isinstance(text, str):
        raise ValueError("Channel suggestions must be a string")
    
    # Remove null bytes and trim whitespace
    text = text.replace("\x00", "").strip()

    if not text:
        return ""
    
    # Enforce length limit
    if len(text) > max_length:
        raise ValueError(f"Channel suggestions too long (max {max_length} characters)")
    
    return text

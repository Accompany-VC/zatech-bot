from __future__ import annotations

from slack_bolt.async_app import AsyncApp

from core.config import AppConfig


def create_slack_app(config: AppConfig) -> AsyncApp:
    """Instantiate the AsyncApp with configuration."""

    return AsyncApp(token=config.slack_bot_token, signing_secret=config.signing_secret)

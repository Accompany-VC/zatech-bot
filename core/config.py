from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(slots=True)
class AppConfig:
    """Runtime configuration derived from environment variables."""

    slack_bot_token: str
    slack_app_token: str
    signing_secret: Optional[str] = None
    log_level: str = "INFO"
    plugin_packages: List[str] = field(default_factory=lambda: ["plugins"])
    enabled_plugins: List[str] = field(default_factory=list)
    database_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> "AppConfig":
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        app_token = os.getenv("SLACK_APP_TOKEN")
        if not bot_token or not app_token:
            pairs = [
                ("SLACK_BOT_TOKEN", bot_token),
                ("SLACK_APP_TOKEN", app_token),
            ]
            missing = [name for name, value in pairs if not value]
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )

        signing_secret = os.getenv("SLACK_SIGNING_SECRET")
        log_level = os.getenv("LOG_LEVEL", "INFO")

        plugin_packages_raw = os.getenv("PLUGIN_PACKAGES", "plugins")
        plugin_packages = [pkg.strip() for pkg in plugin_packages_raw.split(",") if pkg.strip()]

        enabled_plugins_raw = os.getenv("ENABLED_PLUGINS", "")
        enabled_plugins = [slug.strip() for slug in enabled_plugins_raw.split(",") if slug.strip()]

        raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db")
        database_url = raw_db_url.strip() or None

        return cls(
            slack_bot_token=bot_token,
            slack_app_token=app_token,
            signing_secret=signing_secret,
            log_level=log_level,
            plugin_packages=plugin_packages,
            enabled_plugins=enabled_plugins,
            database_url=database_url,
        )

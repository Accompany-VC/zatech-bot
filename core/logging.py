from __future__ import annotations

import logging
from typing import Optional


def setup_logging(level: str = "INFO") -> None:
    """Configure application-wide logging."""

    # basicConfig is a no-op if already configured; force with handlers reset
    root = logging.getLogger()
    if root.handlers:
        for handler in list(root.handlers):
            root.removeHandler(handler)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)8s | %(name)s | %(message)s",
    )


def get_plugin_logger(key: str) -> logging.Logger:
    return logging.getLogger(f"plugins.{key}")

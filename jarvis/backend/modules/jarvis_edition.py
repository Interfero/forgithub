"""Редакция установки Jarvis."""

from __future__ import annotations

import os


def is_free_edition() -> bool:
    """Устаревший флаг; в Jarvis v1 не используется."""
    return os.getenv("JARVIS_EDITION", "").strip().lower() in (
        "free",
        "1",
        "true",
        "yes",
    )


def edition_label() -> str:
    return "Jarvis"

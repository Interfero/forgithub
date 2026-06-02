"""Редакция установки: pro (полный Jarvis) или free (Jarvis_free)."""

from __future__ import annotations

import os


def is_free_edition() -> bool:
    return os.getenv("JARVIS_EDITION", "").strip().lower() in (
        "free",
        "1",
        "true",
        "yes",
    )


def edition_label() -> str:
    return "Jarvis Free" if is_free_edition() else "Jarvis"

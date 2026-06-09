"""
Локальный ключ DeepSeek (файл config/deepseek.key или настройки UI).
Не коммитьте реальный ключ — только *.example.
"""

from __future__ import annotations

import os
from pathlib import Path

from modules.jarvis_edition import is_free_edition


def _key_paths() -> list[Path]:
    root = Path(__file__).resolve().parent.parent
    return [
        root / "config" / "deepseek_free.key",
        root / "data" / "deepseek_free.key",
    ]


def bundled_deepseek_key() -> str:
    if not is_free_edition():
        return ""
    env = (os.getenv("JARVIS_FREE_DEEPSEEK_KEY") or "").strip()
    if env.startswith("sk-"):
        return env
    for path in _key_paths():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if text.startswith("sk-"):
            return text
    return ""


def apply_free_settings(raw: dict) -> dict:
    if not is_free_edition():
        return raw
    key = bundled_deepseek_key()
    if key:
        out = dict(raw)
        out["deepseek_key"] = key
        out["deepseek_active"] = True
        return out
    return raw


def protect_free_settings_save(incoming: dict, current: dict) -> dict:
    """Не даём перезаписать встроенный DeepSeek пустым полем в UI."""
    if not is_free_edition():
        return incoming
    key = bundled_deepseek_key()
    if not key:
        return incoming
    out = dict(incoming)
    out["deepseek_key"] = key
    out["deepseek_active"] = True
    return out


def deepseek_bundled_for_client() -> bool:
    return bool(is_free_edition() and bundled_deepseek_key())

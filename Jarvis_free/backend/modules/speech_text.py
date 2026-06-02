"""
Текст для озвучки: блоки между разделителями --- только для чтения на экране.
"""

from __future__ import annotations

import re

_DETAIL_SPLIT = re.compile(r"(?:^|\n)\s*---+\s*(?:\n|$)", re.MULTILINE)


def strip_detail_blocks(text: str) -> str:
    """
    Оставляет фрагменты вне пар --- … --- (чётные части после split).
    Пример: «Кратко» + --- + «Подробности» + ---  →  озвучивается только «Кратко».
    """
    if not text or not text.strip():
        return ""
    parts = _DETAIL_SPLIT.split(text.strip())
    if len(parts) == 1:
        return _clean_for_speech(parts[0])
    spoken_parts = [parts[i].strip() for i in range(0, len(parts), 2) if parts[i].strip()]
    return _clean_for_speech("\n".join(spoken_parts))


def _clean_for_speech(text: str) -> str:
    t = text.strip()
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"#{1,6}\s*", "", t)
    t = re.sub(r"[🔊🔑⚠️❌✅📎🎙️📁📊🖼️⚙️💬🗑️✏️📥📱🟠]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def chat_message_with_details(short: str, detail: str | None = None) -> str:
    """Короткая часть в чате + подробности между --- (не озвучиваются)."""
    short = (short or "").strip()
    detail = (detail or "").strip()
    if not detail:
        return short
    return f"{short}\n\n---\n{detail}\n---"

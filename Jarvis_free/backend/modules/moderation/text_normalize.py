"""Нормализация текста для детерминированных правил (регистр, ё, leet)."""

from __future__ import annotations

import re

_LEET_MAP = str.maketrans(
    {
        "@": "а",
        "4": "а",
        "0": "о",
        "3": "з",
        "6": "б",
        "1": "и",
        "$": "с",
        "7": "т",
        "8": "в",
        "9": "д",
        "5": "с",
    }
)

_REPEAT_RE = re.compile(r"(.)\1{2,}", re.UNICODE)


def normalize_for_rules(text: str) -> str:
    t = (text or "").lower().replace("ё", "е")
    t = t.translate(_LEET_MAP)
    t = _REPEAT_RE.sub(r"\1\1", t)
    return t


def collapse_spaced_letters(text: str) -> str:
    """х у й -> хуй (простые пробелы между одиночными буквами)."""
    parts = text.split()
    if len(parts) < 3:
        return text
    if all(len(p) == 1 for p in parts):
        return "".join(parts)
    return text

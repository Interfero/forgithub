"""
Текст для озвучки: блоки между --- не озвучиваются; ссылки и числа готовятся для TTS.
"""

from __future__ import annotations

import re

_DETAIL_SPLIT = re.compile(r"(?:^|\n)\s*---+\s*(?:\n|$)", re.MULTILINE)
_URL_RE = re.compile(
    r"(?:https?://|ftp://|www\.)[^\s\]\)<>\"']+|"
    r"(?<![@\w])[\w-]+\.(?:ru|com|org|net|io|dev|app|me|ua|by|kz)(?:/[^\s\]\)<>\"']*)?",
    re.IGNORECASE,
)
_INT_RE = re.compile(r"\b\d+\b")
_FLOAT_RE = re.compile(r"\b\d+[.,]\d+\b")


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


def strip_urls_for_speech(text: str) -> str:
    """Убирает URL и markdown-ссылки — Jarvis не зачитывает их вслух."""
    if not text:
        return ""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    t = _URL_RE.sub("", t)
    t = re.sub(r"\(\s*\)", "", t)
    return t


def numbers_to_words_ru(text: str) -> str:
    """Числа в тексте → слова на русском (для естественной озвучки)."""
    if not text:
        return ""

    try:
        from num2words import num2words
    except ImportError:
        return text

    def _float_repl(m: re.Match[str]) -> str:
        raw = m.group(0).replace(",", ".")
        try:
            if "." in raw:
                whole, frac = raw.split(".", 1)
                whole_w = num2words(int(whole), lang="ru") if whole else "ноль"
                frac_w = " ".join(num2words(int(d), lang="ru") for d in frac if d.isdigit())
                return f"{whole_w} целая {frac_w}" if frac_w else whole_w
            return num2words(int(raw), lang="ru")
        except Exception:
            return m.group(0)

    def _int_repl(m: re.Match[str]) -> str:
        try:
            return num2words(int(m.group(0)), lang="ru")
        except Exception:
            return m.group(0)

    t = _FLOAT_RE.sub(_float_repl, text)
    t = _INT_RE.sub(_int_repl, t)
    return t


def apply_custom_stress(text: str, lexicon: dict[str, str] | None = None) -> str:
    """Подставить ручные ударения Silero (+ перед гласной) по словарю пользователя."""
    if not text or not text.strip():
        return text or ""
    if lexicon is None:
        try:
            from modules.silero_tts import get_stress_lexicon

            lexicon = get_stress_lexicon()
        except Exception:
            lexicon = {}
    if not lexicon:
        return text
    out = text
    for plain, marked in sorted(lexicon.items(), key=lambda x: -len(x[0])):
        if not plain:
            continue
        pattern = re.compile(re.escape(plain), re.IGNORECASE)

        def _repl(m: re.Match[str]) -> str:
            src = m.group(0)
            if "+" in src:
                return src
            # Сохраняем регистр первой буквы совпадения
            if src and src[0].isupper() and marked[0].islower():
                return marked[0].upper() + marked[1:]
            return marked

        out = pattern.sub(_repl, out)
    return out


def prepare_text_for_tts(text: str) -> str:
    """Полная подготовка текста перед Silero TTS."""
    t = strip_detail_blocks(text)
    t = strip_urls_for_speech(t)
    t = numbers_to_words_ru(t)
    t = apply_custom_stress(t)
    return t


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

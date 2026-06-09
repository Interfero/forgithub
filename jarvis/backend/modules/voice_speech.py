"""
Короткая речь для TTS — отдельно от текста чата и от блока «рассуждения».
По умолчанию только быстрая эвристика (без LLM), чтобы не тормозить ответ.
"""

from __future__ import annotations

import re

from modules.text_sanitize import (
    _sentence_is_reasoning,
    strip_reasoning_chatter,
    truncate_for_voice_speech,
)

_MARKDOWN_RE = re.compile(r"\*\*([^*]+)\*\*|`([^`]+)`|!\[[^\]]*\]\([^)]+\)")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
_INTERNAL_LINE = re.compile(
    r"(?:^|\b)(?:роутер|маршрут|sse|стрим|runtime|generate_reply|"
    r"runtime-кеш|think|tts|ozvuch|озвуч|qwen.*классиф|deepseek.*путь|"
    r"голос:\s|диалог:\s|старт:\s|ответ чата готов)",
    re.I,
)


def _strip_markdown(s: str) -> str:
    out = s or ""
    out = _MARKDOWN_RE.sub(lambda m: m.group(1) or m.group(2) or "картинка", out)
    out = re.sub(r"^#{1,6}\s+", "", out, flags=re.M)
    out = re.sub(r"^\s*[-•*]\s+", "", out, flags=re.M)
    out = re.sub(r"^\s*\d{1,2}\.\s+", "", out, flags=re.M)
    return re.sub(r"\s+", " ", out).strip()


def _is_voice_meta_sentence(sentence: str) -> bool:
    pl = (sentence or "").strip().lower()
    if not pl:
        return True
    if _sentence_is_reasoning(sentence):
        return True
    if _INTERNAL_LINE.search(pl):
        return True
    if pl.startswith(
        (
            "сначала проанализ",
            "сначала мне",
            "я проанализирую",
            "я проведу",
            "я начну",
            "проанализирую запрос",
            "в чате я",
            "полный ответ",
            "текст в чате",
        )
    ):
        return True
    return False


def _non_reasoning_sentences(text: str, *, max_sentences: int = 3) -> list[str]:
    plain = _strip_markdown(strip_reasoning_chatter(text or ""))
    out: list[str] = []
    for part in _SENTENCE_SPLIT.split(plain):
        s = part.strip()
        if len(s) < 4:
            continue
        if _is_voice_meta_sentence(s):
            continue
        if not s.endswith((".", "!", "?")):
            s += "."
        out.append(s)
        if len(out) >= max_sentences:
            break
    return out


def finalize_speech_for_tts(text: str, user_text: str = "") -> str:
    """Только фразы для уха — без монолога, markdown и служебных строк."""
    parts = _non_reasoning_sentences(text, max_sentences=3)
    if parts:
        s = " ".join(parts)
    else:
        s = truncate_for_voice_speech(
            _strip_markdown(strip_reasoning_chatter(text or "")),
            user_text,
            max_sentences=2,
        )
    s = re.sub(r"\s+", " ", (s or "").strip())
    if _INTERNAL_LINE.search(s):
        s = ""
    if not s or len(s) < 4:
        s = "Готово, Шеф."
    return truncate_speech(s)


def truncate_speech(text: str, *, max_len: int = 420) -> str:
    s = re.sub(r"\s+", " ", (text or "").strip())
    if len(s) <= max_len:
        return s
    cut = s[: max_len - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def build_voice_speech_fast(
    user_text: str,
    chat_reply: str,
    history: list[dict] | None = None,
) -> str:
    """Быстрая озвучка: суть из текста чата, без LLM и без thinking-блока."""
    _ = history
    from modules.dialog_handlers import is_canned_smalltalk_reply

    reply = (chat_reply or "").strip()
    if is_canned_smalltalk_reply(reply):
        return finalize_speech_for_tts(reply, user_text)

    sentences = _non_reasoning_sentences(reply, max_sentences=2)
    if sentences:
        return finalize_speech_for_tts(" ".join(sentences), user_text)

    return finalize_speech_for_tts(reply, user_text)


def generate_voice_speech_text(
    user_text: str,
    chat_reply: str,
    history: list[dict] | None = None,
    *,
    deepseek_key: str = "",
    model: str = "deepseek-chat",
) -> str:
    """Совместимость: всегда быстрый путь (LLM не вызываем — скорость ответа)."""
    _ = deepseek_key, model
    from modules.operation_stream import append_thinking

    speech = build_voice_speech_fast(user_text, chat_reply, history)
    append_thinking(f"Голос (TTS): {speech[:80]}{'…' if len(speech) > 80 else ''}")
    _cache_voice_turn(user_text, speech)
    return speech


def _cache_voice_turn(user_text: str, speech: str) -> None:
    from modules.agent import get_runtime

    rt = get_runtime()
    cache = getattr(rt, "voice_reasoning_cache", None)
    if not isinstance(cache, list):
        rt.voice_reasoning_cache = []
        cache = rt.voice_reasoning_cache
    cache.append({"role": "user", "content": (user_text or "")[:400]})
    cache.append({"role": "assistant", "content": (speech or "")[:400]})
    rt.voice_reasoning_cache = cache[-24:]

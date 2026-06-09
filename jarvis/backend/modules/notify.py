"""Важные уведомления — в чат, контекст LLM и озвучку; служебные — только в индикаторы."""

from __future__ import annotations

import re

IMPORTANT = "important"
ROUTINE = "routine"


def infer_notify_level(content: str) -> str:
    t = (content or "").strip()
    if not t:
        return ROUTINE
    if re.match(r"^[❌⚠️]", t) or re.search(r"ошибк", t, re.I):
        return IMPORTANT
    if re.search(
        r"Backend недоступен|Нужен ключ|требует ключ|sk-",
        t,
        re.I,
    ):
        return IMPORTANT
    if re.match(r"^[🔑📁📊🎙️]", t) or re.search(
        r"загружен|на связи",
        t,
        re.I,
    ):
        return IMPORTANT
    return ROUTINE


def is_important_message(msg: dict) -> bool:
    if msg.get("role") != "system":
        return True
    level = msg.get("notify_level")
    if level in (IMPORTANT, ROUTINE):
        return level == IMPORTANT
    return infer_notify_level(msg.get("content", "")) == IMPORTANT

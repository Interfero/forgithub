"""
Смена режима чата по запросу пользователя («перейди в режим разработчика», «переключись на юриста»).
"""

from __future__ import annotations

import re

from modules.agent import MODE_LABELS, AgentMode, get_mode, get_previous_mode, set_mode

_MODE_PATTERNS: tuple[tuple[AgentMode, tuple[str, ...]], ...] = (
    (
        AgentMode.DEVELOPER,
        (
            "разработчик",
            "разработчика",
            "разработчиком",
            "программист",
            "программиста",
            "developer",
            "режим dev",
            "dev mode",
            "режим кода",
        ),
    ),
    (
        AgentMode.MARKETER,
        (
            "маркетолог",
            "маркетолога",
            "маркетологом",
            "дизайнер",
            "дизайнера",
            "дизайнером",
            "маркетолог+дизайнер",
            "маркетолог и дизайнер",
            "marketer",
        ),
    ),
    (
        AgentMode.ACCOUNTANT,
        (
            "бухгалтер",
            "бухгалтера",
            "бухгалтером",
            "юрист",
            "юриста",
            "юристом",
            "юридическ",
            "правов",
            "lawyer",
            "legal",
            "accountant",
            "бухгалтер+юрист",
            "бухгалтер и юрист",
        ),
    ),
    (
        AgentMode.STANDARD,
        (
            "стандартный чат",
            "стандартный",
            "стандарт",
            "обычный режим",
            "обычный чат",
            "standard",
        ),
    ),
)

_SWITCH_HINTS = re.compile(
    r"(?:"
    r"перейд\w*\s+(?:в\s+)?(?:режим|на\b)|"
    r"переключ\w*\s+(?:в\s+)?(?:режим|на\b)|"
    r"смен\w*\s+(?:на\s+|режим)|"
    r"включ\w*\s+(?:режим|на\b)|"
    r"стань\s+|"
    r"работай\s+как\s+|"
    r"режим\s+(?:чата\s+)?(?:на|в)|"
    r"switch\s+(?:to\s+)?(?:mode|режим)|"
    r"^режим\s+\w+|"
    r"верн\w*\s+(?:в\s+)?(?:режим|обратно|назад)|"
    r"в\s+режим\s+"
    r")",
    re.I,
)

_BACK_ONLY = re.compile(
    r"^(?:теперь\s+)?(?:обратно|назад|как\s+было|верни(?:сь)?\s+обратно)\s*[.!?]*$",
    re.I,
)

_RETURN_STANDARD = re.compile(
    r"(?:верн\w*|переключ\w*|перейд\w*|смен\w*|теперь\s+обратно)"
    r".{0,40}стандарт",
    re.I,
)


def _wants_mode_switch(low: str) -> bool:
    stripped = low.strip()
    if _BACK_ONLY.match(stripped):
        return True
    if _RETURN_STANDARD.search(low):
        return True
    if _SWITCH_HINTS.search(low):
        return True
    if re.search(
        r"(?:переключ|перейд|смен|включ|стань|switch)\w*\s+на\s+\S+",
        low,
    ):
        return True
    if re.match(r"^режим\s+\S+", stripped):
        return True
    return False


def _match_mode_alias(low: str) -> AgentMode | None:
    best: AgentMode | None = None
    best_pos = 10**9
    for mode, keys in _MODE_PATTERNS:
        for key in keys:
            pos = low.find(key)
            if pos >= 0 and pos < best_pos:
                best_pos = pos
                best = mode
    return best


def parse_mode_switch_request(text: str) -> AgentMode | None:
    """Распознать целевой режим из фразы пользователя."""
    raw = (text or "").strip()
    if len(raw) > 200:
        return None
    low = raw.lower()
    if not _wants_mode_switch(low):
        return None

    if _BACK_ONLY.match(low.strip()):
        return get_previous_mode() or AgentMode.STANDARD

    if _RETURN_STANDARD.search(low) or re.search(
        r"в\s+режим\s+стандарт\w*(?:\s+чата)?", low
    ):
        return AgentMode.STANDARD

    return _match_mode_alias(low)


def _mode_gate_error(mode: AgentMode) -> str | None:
    import store
    from modules import nano_banana as nano_banana_module

    s = store.load_settings()
    deepseek = (s.get("deepseek_key") or "").strip()
    pplx = (s.get("perplexity_key") or "").strip()
    nb = (s.get("nanobanana_key") or "").strip()

    def _ok(prefix: str, key: str, min_len: int) -> bool:
        k = (key or "").strip()
        return k.startswith(prefix) and len(k) >= min_len and "•" not in k

    if mode == AgentMode.MARKETER and not nano_banana_module.key_valid(nb):
        from modules.media_generation import has_media_provider

        if not has_media_provider("image") and not _ok("sk-", deepseek, 20):
            return (
                "⚠️ Для маркетинговых задач с картинками нужен ключ **Nano Banana**, **OpenAI** или **xAI** в ⚙️ Настройках."
            )
    if mode == AgentMode.ACCOUNTANT and not _ok("sk-", deepseek, 20):
        return "⚠️ Режим **Бухгалтер + Юрист** нужен ключ **DeepSeek** (`sk-…`) в ⚙️ Настройках."
    if mode == AgentMode.DEVELOPER and not _ok("pplx-", pplx, 12):
        return (
            "⚠️ Режим **Разработчик** нужен ключ **Perplexity** (`pplx-…`) в ⚙️ Настройках."
        )
    return None


def apply_chat_mode(mode: AgentMode) -> tuple[bool, str]:
    """
    Переключить режим на бэкенде и отдать команду UI.
    Возвращает (успех, текст для пользователя).
    """
    current = get_mode()
    label = MODE_LABELS.get(mode, mode.value)

    if mode == current:
        return True, f"Уже активен режим **{label}**."

    err = _mode_gate_error(mode)
    if err:
        return False, err

    set_mode(mode)
    return True, ""


def try_handle_mode_switch(user_text: str) -> tuple[bool, str]:
    """
    Если запрос — смена режима, вернуть (True, ответ).
    Иначе (False, '').
    """
    target = parse_mode_switch_request(user_text)
    if target is None:
        return False, ""
    _ok, reply = apply_chat_mode(target)
    return True, reply

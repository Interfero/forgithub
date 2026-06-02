"""
Ранние ответы без галлюцинаций «универсального ChatGPT»: кто ты, знакомство, умный дом.
"""

from __future__ import annotations

import re

_IDENTITY_Q = re.compile(
    r"^(?:ты\s+)?(?:кто\s+ты|ты\s+кто|who\s+are\s+you)\s*\??\s*$",
    re.I,
)
_INTRO_NAME = re.compile(
    r"меня\s+зовут\s+([а-яёa-z][а-яёa-z\-]{1,24})",
    re.I,
)
_SMART_HOME = re.compile(
    r"умн(?:ый|ого)\s+дом|домашн(?:яя|ей|ю)\s+автоматизац|"
    r"голосов(?:ые|ой)\s+команд|amazon\s+echo|google\s+home|"
    r"apple\s+homepod|philips\s+hue|lifx|умной\s+колонк",
    re.I,
)
_WELLBEING = re.compile(
    r"^(?:"
    r"ты\s+как|как\s+ты|как\s+дела|как\s+поживаешь|"
    r"как\s+сам|как\s+настроение|how\s+are\s+you|what'?s\s+up"
    r")\s*\??\s*$",
    re.I,
)

_TASK_BLOCKERS = (
    "сказ",
    "расскаж",
    "нарисуй",
    "сгенерир",
    "сделай",
    "помог",
    "объясн",
    "напиш",
    "посчит",
    "открой",
    "авито",
    "http",
    "абзац",
)

_GREETING_REFS = (
    "привет",
    "здравствуй",
    "здарова",
    "здаров",
    "салют",
    "hello",
    "hi",
    "hey",
    "хай",
    "ку",
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def is_pure_identity_question(text: str) -> bool:
    t = _norm(text)
    if not t or len(t) > 80:
        return False
    return bool(_IDENTITY_Q.match(t)) or t in ("кто ты", "ты кто", "who are you")


def extract_introduced_name(text: str) -> str | None:
    m = _INTRO_NAME.search(text or "")
    if not m:
        return None
    name = (m.group(1) or "").strip().capitalize()
    if len(name) < 2:
        return None
    return name


def wants_smart_home_advice(text: str) -> bool:
    low = (text or "").lower()
    if len(low) > 2000:
        return False
    if "jarvis" in low and "настро" in low and "голос" in low:
        return False
    return bool(_SMART_HOME.search(low))


def _fuzzy_word(word: str, refs: tuple[str, ...], *, threshold: float = 0.78) -> bool:
    from difflib import SequenceMatcher

    w = re.sub(r"[^\wа-яё]+", "", (word or "").lower(), flags=re.I)
    if len(w) < 2:
        return False
    for ref in refs:
        if w == ref:
            return True
        if len(w) >= 3 and SequenceMatcher(None, w, ref).ratio() >= threshold:
            return True
    return False


def _has_wellbeing_intent(low: str, tokens: list[str]) -> bool:
    return bool(
        _WELLBEING.match(low)
        or "как дела" in low
        or "ты как" in low
        or "как ты" in low
        or "как поживаешь" in low
        or "как настроение" in low
        or ("как" in tokens and ("ты" in tokens or "дела" in tokens))
    )


def is_casual_smalltalk(text: str) -> bool:
    """
    Короткое приветствие / «как дела», в т.ч. с опечаткой 2–3 букв (првиет → привет).
    Не исправлять вслух — просто ответить по смыслу.
    """
    low = _norm(text)
    if not low or len(low) > 56:
        return False
    if any(w in low for w in _TASK_BLOCKERS):
        return False

    tokens = [t for t in low.split() if t]
    if len(tokens) > 6:
        return False

    has_greeting = any(_fuzzy_word(t, _GREETING_REFS) for t in tokens)
    has_wellbeing = _has_wellbeing_intent(low, tokens)

    if has_wellbeing and len(tokens) <= 5:
        return True
    if has_greeting and has_wellbeing:
        return True
    if len(tokens) <= 2 and has_greeting:
        return True
    return False


def is_wellbeing_smalltalk(text: str) -> bool:
    return is_casual_smalltalk(text) and _has_wellbeing_intent(
        _norm(text), [t for t in _norm(text).split() if t]
    )


def wellbeing_reply() -> str:
    return "Нормально.\n\n**Jarvis** на связи — чем помочь?"


def casual_smalltalk_reply(user_text: str) -> str:
    """Ответ на привет / как дела — без разбора опечаток."""
    low = _norm(user_text)
    tokens = [t for t in low.split() if t]
    if _has_wellbeing_intent(low, tokens):
        return wellbeing_reply()
    return "Привет, Шеф.\n\n**Jarvis** на связи — чем помочь?"


def identity_reply() -> str:
    return (
        "Я **Jarvis** — ядро **этого приложения** на вашем ПК: локальная Qwen, инструменты, "
        "Авито, браузер, файлы памяти.\n\n"
        "Не облачный «помощник на всё» и не Alexa/Google Home. "
        "Голос в Jarvis — микрофон внизу чата, команда **«Джарвис»**."
    )


def introduction_reply(name: str, *, also_identity: bool = False) -> str:
    parts = []
    if also_identity:
        parts.append(identity_reply())
        parts.append("")
    parts.append(f"Привет, **{name}**.")
    parts.append("")
    parts.append(
        "Я **Jarvis** в этом приложении. Рад знакомству.\n\n"
        f"Чтобы запомнить имя во всех чатах: **запомни: меня зовут {name}**."
    )
    return "\n\n".join(parts)


def smart_home_redirect_reply() -> str:
    return (
        "**Данных нет** по вашей конкретной проводке и устройствам — я не вижу ваш умный дом.\n\n"
        "Jarvis **не настраивает** Alexa, Google Home, HomePod и лампочки Hue. "
        "Это отдельные экосистемы; инструкции из интернета — через **web_search**, если попросите явно.\n\n"
        "**В Jarvis есть голос:** микрофон в чате → «Джарвис» → вопрос → озвучка ответа. "
        "Это не управление розетками в квартире.\n\n"
        "Задача неясна, пока не назовёте: какое устройство, какой хаб, что уже куплено."
    )


def try_handle_early_dialog(user_text: str) -> tuple[bool, str]:
    """Фиксированные ответы без вызова Qwen."""
    text = (user_text or "").strip()
    if not text:
        return False, ""

    name = extract_introduced_name(text)
    identity = is_pure_identity_question(text)

    if identity and not name:
        return True, identity_reply()

    if name and (_norm(text).startswith("привет") or "познаком" in text.lower() or len(text) < 120):
        return True, introduction_reply(name, also_identity=identity)

    if wants_smart_home_advice(text):
        return True, smart_home_redirect_reply()

    if is_casual_smalltalk(text):
        return True, casual_smalltalk_reply(text)

    if is_wellbeing_smalltalk(text):
        return True, wellbeing_reply()

    if identity:
        return True, identity_reply()

    return False, ""

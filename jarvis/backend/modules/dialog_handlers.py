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
    "здравствуйте",
    "здарова",
    "здаров",
    "салют",
    "приветствую",
    "hello",
    "hi",
    "hey",
    "хай",
    "ку",
    "добрый",
    "доброе",
    "доброй",
    "доброго",
)

_GREETING_FILLERS = frozenset(
    {
        "jarvis",
        "джарвис",
        "жарвис",
        "шеф",
        "эй",
        "йоу",
        "алло",
        "алё",
    }
)

_VOICE_BATCH_RE = re.compile(
    r"^\[Голос[^\]]*\]\s*(?:\n+Ответь[^\n]*\n+)?",
    re.I | re.S,
)
_NUMBERED_LINE_RE = re.compile(r"^\d{1,2}\.\s+", re.M)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def normalize_chat_user_text(text: str) -> str:
    """Голосовая очередь / нумерация — оставить смысл для детекторов."""
    s = (text or "").strip()
    if not s:
        return s
    s = _VOICE_BATCH_RE.sub("", s).strip()
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if lines and all(_NUMBERED_LINE_RE.match(ln) for ln in lines):
        lines = [_NUMBERED_LINE_RE.sub("", ln).strip() for ln in lines]
        if len(lines) == 1:
            return lines[0]
        last = lines[-1]
        if is_casual_smalltalk(last):
            return last
        return lines[0]
    return re.sub(r"\n+", " ", s).strip()


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
    raw = normalize_chat_user_text(text)
    low = _norm(raw)
    if not low or len(low) > 72:
        return False
    if any(w in low for w in _TASK_BLOCKERS):
        return False

    tokens = [t for t in low.split() if t]
    if len(tokens) > 8:
        return False

    has_greeting = any(
        _fuzzy_word(t, _GREETING_REFS) for t in tokens
    ) or any(low.startswith(g) for g in ("привет", "здравств", "добрый", "доброе", "доброй", "салют", "hello", "hi", "hey"))
    has_wellbeing = _has_wellbeing_intent(low, tokens)

    core = [t for t in tokens if t not in _GREETING_FILLERS]

    if has_wellbeing and len(core) <= 5:
        return True
    if has_greeting and has_wellbeing:
        return True
    if has_greeting and len(core) <= 4:
        return True
    if len(core) <= 2 and has_greeting:
        return True
    if low in {"привет", "здравствуй", "здравствуйте", "салют", "hello", "hi", "hey", "хай"}:
        return True
    return False


def is_wellbeing_smalltalk(text: str) -> bool:
    raw = normalize_chat_user_text(text)
    low = _norm(raw)
    return is_casual_smalltalk(raw) and _has_wellbeing_intent(
        low, [t for t in low.split() if t]
    )


def wellbeing_reply() -> str:
    return "Нормально, Шеф. На связи."


def casual_smalltalk_reply(user_text: str) -> str:
    """Ответ на привет / как дела — без разбора опечаток."""
    low = _norm(normalize_chat_user_text(user_text))
    tokens = [t for t in low.split() if t]
    if _has_wellbeing_intent(low, tokens):
        return wellbeing_reply()
    return "Привет, Шеф. На связи."


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


_ACK_WORDS = frozenset(
    {
        "пойдет",
        "пойдёт",
        "ок",
        "окей",
        "okay",
        "ok",
        "ладно",
        "норм",
        "нормально",
        "согласен",
        "согласна",
        "да",
        "yes",
        "хорошо",
        "понял",
        "понятно",
        "ясно",
        "принял",
        "принято",
        "угу",
        "ага",
        "fine",
        "good",
        "cool",
        "нормас",
    }
)

_TASK_VERB_HINTS = (
    "провер",
    "открой",
    "включ",
    "выключ",
    "запуст",
    "найди",
    "сделай",
    "нарисуй",
    "покаж",
    "скачай",
    "отправ",
    "запомни",
    "сгенерир",
)


def _last_assistant_text(history: list[dict] | None) -> str:
    for msg in reversed(history or []):
        if msg.get("role") == "assistant":
            return (msg.get("content") or "").strip()
    return ""


def is_acknowledgment_utterance(text: str) -> bool:
    """«пойдёт», «ок» — согласие с предыдущим ответом, не новая задача."""
    low = _norm(normalize_chat_user_text(text)).rstrip(".!?")
    if not low:
        return False
    tokens = [t for t in low.split() if t and t not in _GREETING_FILLERS]
    if not tokens:
        return False
    if len(tokens) <= 2 and all(t in _ACK_WORDS for t in tokens):
        return True
    return low in _ACK_WORDS


def is_ambiguous_short_task(text: str) -> bool:
    """Короткая реплика без явной задачи — нужно уточнение, не словарь Qwen."""
    raw = normalize_chat_user_text(text)
    low = _norm(raw)
    if not low or len(low) > 48:
        return False
    if any(w in low for w in _TASK_BLOCKERS):
        return False
    if any(w in low for w in _TASK_VERB_HINTS):
        return False
    if is_casual_smalltalk(raw) or is_pure_identity_question(raw):
        return False
    if is_acknowledgment_utterance(raw):
        return False
    tokens = [t for t in low.split() if t and t not in _GREETING_FILLERS]
    if len(tokens) > 3:
        return False
    if "?" in raw and len(tokens) >= 2:
        return False
    return len(tokens) <= 2


def try_handle_clarification_gate(
    user_text: str,
    history: list[dict] | None = None,
) -> tuple[bool, str]:
    """Неясная задача → один уточняющий вопрос; «ок/пойдёт» → принято."""
    text = normalize_chat_user_text(user_text)
    if not text:
        return False, ""

    last_asst = _last_assistant_text(history)

    if is_acknowledgment_utterance(text) and last_asst:
        return True, "Принял, Шеф. Что дальше?"

    if is_ambiguous_short_task(text):
        if last_asst:
            return True, "Не понял, Шеф. Уточните одной конкретной фразой — что сделать?"
        return True, "Задача неясна. Что именно нужно?"

    return False, ""


def is_canned_smalltalk_reply(text: str) -> bool:
    s = (text or "").strip()
    if not s or len(s) > 160:
        return False
    return s in {
        "Привет, Шеф. На связи.",
        "Нормально, Шеф. На связи.",
        wellbeing_reply(),
        casual_smalltalk_reply("привет"),
        "Принял, Шеф. Что дальше?",
        "Не понял, Шеф. Уточните одной конкретной фразой — что сделать?",
        "Задача неясна. Что именно нужно?",
    } or s.startswith(("Привет, Шеф.", "Нормально, Шеф.", "Принял, Шеф."))


def try_handle_early_dialog(user_text: str) -> tuple[bool, str]:
    """Фиксированные ответы без вызова Qwen."""
    text = normalize_chat_user_text(user_text)
    if not text:
        return False, ""

    if is_casual_smalltalk(text):
        return True, casual_smalltalk_reply(text)

    name = extract_introduced_name(text)
    identity = is_pure_identity_question(text)

    if identity and not name:
        return True, identity_reply()

    if name and (_norm(text).startswith("привет") or "познаком" in text.lower() or len(text) < 120):
        return True, introduction_reply(name, also_identity=identity)

    if wants_smart_home_advice(text):
        return True, smart_home_redirect_reply()

    if is_wellbeing_smalltalk(text):
        return True, wellbeing_reply()

    if identity:
        return True, identity_reply()

    return False, ""

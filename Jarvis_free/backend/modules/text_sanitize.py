"""
Очистка обрезанного markdown, утечек промпта и сжатие болтливых ответов.
"""

from __future__ import annotations

import re

_TRAILING_PARTIAL_BOLD = re.compile(r"\*\*[^\s*]{0,3}$")
_LEAKED_TRANSLATE = re.compile(
    r"[*!`]+\s*(?:переведи|translate|translation)\s+"
    r"(?:на\s+)?(?:английский|english|русский|russian)\s*[*!`]*",
    re.I,
)
_LEAKED_TRANSLATE_PLAIN = re.compile(
    r"(?:^|\s)(?:переведи|translate)\s+на\s+(?:английский|english|русский)\s*",
    re.I,
)
_TRANSLATION_HEADER = re.compile(
    r"(?:^|\n)\s*(?:Sure,?\s+here(?:'s| is)[^\n]*translation:?|"
    r"Certainly!?\s+Here is the translation:?)\s*\n?",
    re.I | re.M,
)
_GLUED_SENTENCES = re.compile(r"([а-яё])([А-ЯЁ])")
_GLUED_PUNCT = re.compile(r"([.!?])([А-ЯЁа-яё])")
_LEAKED_MODE_LINE = re.compile(
    r"^\s*\*{0,2}\s*(?:в\s+)?режим\s+(?:стандарт\w*|разработ\w*|бухгалт\w*|"
    r"маркетолог\w*|юрист\w*)(?:\s+чата)?\s*\*{0,2}\s*$",
    re.I | re.M,
)
_WRONG_IDENTITY_BLEED = re.compile(
    r"(?:я\s+)?(?:модель\s+)?(?:от\s+)?Anthropic|"
    r"Claude\s+(?:3|Sonnet|Opus|Haiku)|"
    r"language model developed by Anthropic|"
    r"разработан(?:а|ы)?\s+компани(?:ей|и)\s+Anthropic|"
    r"Epic\s+Games|OpenAI|ChatGPT|Google\s+DeepMind|Meta\s+AI|"
    r"Microsoft\s+Cortana|Amazon\s+Alexa|"
    r"искусственн(?:ый|ого)\s+интеллект.*(?:создан|разработан)|"
    r"(?:создан|разработан)(?:а|ы)?\s+компани(?:ей|и)\s+(?!Jarvis)[\w\s]{3,40}|"
    r"я\s*[-—]?\s*jarvis,?\s*искусственн",
    re.I | re.S,
)
_CONSUMER_IOT = re.compile(
    r"Amazon\s+Echo|Google\s+Home|Apple\s+HomePod|Philips\s+Hue|"
    r"TP-Link\s+Kasa|LIFX|Google\s+Assistant|голосов(?:ые|ой)\s+помощник|"
    r"освещени(?:ем|е)|климат[-\s]?контрол|управлени(?:е|ем)\s+различными\s+устройств",
    re.I,
)
_FAKE_SELF_INTERVIEW = re.compile(
    r"(?:"
    r"давай\s+я\s+тебе\s+задам|задам\s+пар[уы]\s+вопрос|"
    r"готов\s+ответить\s+на\s+ваши\s+вопросы|"
    r"конечно,?\s+шеф,?\s+готов|"
    r"по\s+ключев(?:ому|ое)\s+слов|"
    r"предостав(?:ь|ить)\s+мне\s+топ|"
    r"вот\s+результаты\s+для\s+ключев|"
    r"\d+\)\s*(?:что\s+ты\s+можешь|кто\s+тебя\s+создал|какие\s+у\s+тебя\s+ограничен)"
    r")",
    re.I,
)
_FAKE_USER_TURN = re.compile(
    r"^(?:"
    r"Я\s+хотел\s+(?:узнать|спросить)|"
    r"Какие\s+у\s+меня\s+варианты|"
    r"Мне\s+очень\s+приятно\s+слышать|"
    r"Может\s+быть,\s+у\s+вас\s+есть|"
    r"У\s+меня\s+есть\s+конкретн"
    r")",
    re.I | re.M,
)
# Утечки инструкций из обучения / чужих промптов в текст ответа
_FAKE_BASH_AVITO = re.compile(
    r"```(?:bash|sh|shell)?\s*\n.*?(?:sync_avito|login_avito|list_avito).*?```",
    re.I | re.S,
)
_FAKE_BASH_LINE = re.compile(
    r"^\s*(?:bash\s+)?(?:sync_avito_chats|login_avito_oauth|list_avito_chats)\s*$",
    re.I | re.M,
)

_LEAKED_PROMPT_LINES: list[re.Pattern[str]] = [
    re.compile(
        r"^\s*Представь информацию так, чтобы было понятно новичку\.?\s*",
        re.I | re.M,
    ),
    re.compile(
        r"^\s*Объясни (?:это )?так, чтобы было понятно новичку\.?\s*",
        re.I | re.M,
    ),
    re.compile(
        r"^\s*Изложи (?:это )?так, чтобы было понятно новичку\.?\s*",
        re.I | re.M,
    ),
    re.compile(
        r"Представь информацию так, чтобы было понятно новичку\.?\s*",
        re.I,
    ),
]
_EXPAND_REQUEST = re.compile(
    r"подробн|развёрн|разверн|пошагов|максимум\s+детал|распиши|детально|"
    r"развернуто|в\s+деталях",
    re.I,
)
_BRIEF_REQUEST = re.compile(
    r"кратко|коротко|лаконич|только\s+суть|в\s+двух\s+словах|одним\s+предлож",
    re.I,
)
_PROCESS_PLACEHOLDER = re.compile(r"\(Процесс анализа\.{0,3}\)", re.I)
_REASONING_SENTENCE_STARTS = (
    "продолжим?",
    "продолжай анализ",
    "сначала мне нужно",
    "для анализа мне нужно",
    "я проведу анализ",
    "я сейчас проведу",
    "я начну анализ",
    "какие данные",
    "ответьте, пожалуйста, какие данные",
    "давайте сначала",
    "давайте начнём",
    "предположим, что",
    "чтобы ответить",
    "чтобы найти",
    "чтобы посчитать",
    "мне необходимо проанализировать",
    "мне нужно проанализировать",
    "для этого нужно",
    "для начала нужно",
)

_TRAILING_FOLLOWUP = re.compile(
    r"\n+(?:---\s*\n+)?(?:"
    r"Хочешь\s+ли|Если\s+(?:вам\s+|тебе\s+)?нужно|Могу\s+(?:также|ещё|ли\s+я)|"
    r"Могу\s+помочь|Могу\s+ли\s+я\s+помочь|Чем\s+могу\s+помочь|"
    r"Как\s+я\s+могу\s+помочь|Если\s+есть\s+конкретн|Если\s+у\s+вас\s+есть\s+вопросы|"
    r"Обращайтесь|Не\s+стесняйтесь|Напишите|Дайте\s+(?:мне\s+)?знать|"
    r"Я\s+(?:здесь,?\s+)?чтобы\s+помочь|Я\s+всегда\s+(?:здесь|готов)"
    r").*$",
    re.I | re.S,
)
_TYPO_LECTURE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"(?:Это,?\s+)?вероятно,?\s+ошибк[аи]\s+в\s+написании|"
    r"похоже,?\s+(?:вы\s+)?имели\s+в\s+виду|"
    r"предполагаю,?\s+что\s+вы\s+хотели\s+сказать|"
    r"скорее\s+всего\s+должно\s+быть\s+написано|"
    r"исправлени[ея]\s+опечатк|"
    r"\(И\s+да,?\s+['«].+?['»]\s+скорее\s+всего"
    r")[^.!?\n]*[.!?…]?\s*",
    re.I | re.M,
)
_APOLOGY_SENTENCE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"Извините[^.!?\n]*[.!?…]|"
    r"Прошу\s+прощения[^.!?\n]*[.!?…]|"
    r"К\s+сожалению[^,.\n]*[,.]?[^.!?\n]*[.!?…]|"
    r"Сожалею[^.!?\n]*[.!?…]|"
    r"Приношу\s+извинения[^.!?\n]*[.!?…]|"
    r"Мне\s+очень\s+жаль[^.!?\n]*[.!?…]"
    r")\s*",
    re.I | re.M,
)
_AI_DISCLAIMER_SENTENCE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"Я\s+(?:всего\s+лишь\s+)?(?:искусственный\s+интеллект|языковая\s+модель|"
    r"ИИ[-\s]?модель|большая\s+языковая\s+модель|нейросеть)[^.!?\n]*[.!?…]|"
    r"Как\s+(?:языковая\s+модель|ИИ|искусственный\s+интеллект)[^.!?\n]*[.!?…]|"
    r"У\s+меня\s+нет\s+(?:тела|сознания|эмоций|личности)[^.!?\n]*[.!?…]|"
    r"I\s+am\s+an?\s+(?:AI|language)\s+model[^.!?\n]*[.!?…]"
    r")\s*",
    re.I | re.M,
)
_SENTENCE_END = re.compile(r"[.!?…][\s\)»\"']*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
# Аббревиатуры, чтобы «т.е.» не считалось двумя предложениями
_ABBR_DOT = re.compile(
    r"\b(?:т\.?\s*е\.?|т\.?\s*п\.?|д\.?\s*р\.?|г\.?\s*р\.?|"
    r"пр\.?|ул\.?|стр\.?|рис\.?|см\.?|напр\.?)\s*",
    re.I,
)


def count_user_sentences(user_text: str) -> int:
    """Сколько законченных предложений в вопросе Шефа."""
    t = (user_text or "").strip()
    if not t:
        return 0
    t = _ABBR_DOT.sub(lambda m: m.group(0).replace(".", "·"), t)
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(t) if p.strip()]
    return max(1, len(parts))


def user_question_is_short(user_text: str) -> bool:
    """Одно предложение — ожидаем короткий ответ."""
    if user_wants_expanded(user_text):
        return False
    return count_user_sentences(user_text) <= 1


def user_wants_expanded(user_text: str) -> bool:
    return bool(_EXPAND_REQUEST.search(user_text or ""))


def user_wants_brief(user_text: str) -> bool:
    return bool(_BRIEF_REQUEST.search(user_text or ""))


def wants_sandbox_write(user_text: str) -> bool:
    low = (user_text or "").lower()
    if any(
        w in low
        for w in (
            "песочниц",
            "jarvis_skills",
            "customskills",
            "save_jarvis",
            "навык",
            "самомодиф",
            "в файл jarvis",
        )
    ):
        return True
    if "функц" in low or "класс" in low:
        if any(w in low for w in ("сохран", "напиш", "добав", "создай", "песочниц")):
            return True
    if "api" in low and any(w in low for w in ("чат", "соискател", "авито")):
        if any(w in low for w in ("напиш", "сохран", "создай", "код", "функц")):
            return True
    return False


def skips_post_brevity(user_text: str) -> bool:
    """Фактические ответы про Jarvis, API, Авито, медиа — не сжимать постобработкой."""
    try:
        from modules import local_qwen as lq

        if lq.is_creative_story_request(user_text):
            return True
        if lq.is_greeting_like(user_text):
            return True
        if lq.is_neural_stack_question(user_text):
            return True
        if lq.is_jarvis_capability_question(user_text):
            return True
        if lq.is_api_or_app_meta_question(user_text):
            return True
        if lq.wants_media_generation(user_text):
            return True
        from modules.listing_generation import wants_listing_generation

        if wants_listing_generation(user_text):
            return True
        from modules.jarvis_capabilities import is_general_capabilities_question

        if is_general_capabilities_question(user_text):
            return True
    except Exception:
        pass
    low = (user_text or "").lower()
    if any(w in low for w in ("авито", "avito", "ideogram", "nano banana", "видео", "картин")):
        return True
    return False


def needs_long_reply(user_text: str, assistant_text: str = "") -> bool:
    """
    Развёрнутый ответ: явная просьба, 2+ предложения в вопросе, код/песочница.
    Одно предложение с «api»/«авито» — НЕ длинный режим.
    """
    if skips_post_brevity(user_text):
        return True
    if user_wants_expanded(user_text):
        return True
    if user_wants_brief(user_text):
        return False
    if wants_sandbox_write(user_text):
        return True
    if count_user_sentences(user_text) >= 2:
        return True
    if "```" in (assistant_text or ""):
        return True
    return False


def reply_max_tokens(user_text: str, *, cloud: bool = False) -> int:
    """Лимит генерации без урезания «мощности» на сложных задачах."""
    if skips_post_brevity(user_text):
        return 2048 if cloud else 2400
    if user_wants_brief(user_text) or user_question_is_short(user_text):
        return 512 if cloud else 400
    if needs_long_reply(user_text):
        return 2048 if cloud else 2400
    return 1024 if cloud else 800


def followup_brevity_hint(user_text: str) -> str:
    """Доп. инструкция после результата инструмента."""
    if user_question_is_short(user_text):
        return (
            "\n\n[Формат ответа] Вопрос короткий — ответь за 2–4 предложения "
            "или список до 6 пунктов. Без повторов, без «---», не дублируй абзацы."
        )
    if count_user_sentences(user_text) >= 2:
        return (
            "\n\n[Формат ответа] Вопрос из нескольких предложений — можно развёрнуто."
        )
    return "\n\n[Формат ответа] Кратко по сути, без повторов."


def _sentence_is_reasoning(sentence: str) -> bool:
    pl = (sentence or "").strip().lower()
    if not pl or len(pl) < 12:
        return False
    if _PROCESS_PLACEHOLDER.search(pl):
        return True
    if any(pl.startswith(start) for start in _REASONING_SENTENCE_STARTS):
        return True
    if re.search(r"продолжай анализ|процесс анализа", pl, re.I):
        return True
    if re.match(r"^(?:да|нет),?\s+продолж", pl, re.I):
        return True
    return False


_SIMULATED_DIALOGUE_EN = re.compile(
    r"(?:would you like|if so, which|shall i tell|let me tell you a)",
    re.I,
)
_SIMULATED_SHEF_LINE = re.compile(
    r"^(?:давай|расскажи|скажи|tell me|let'?s)\s+.{3,90}$",
    re.I | re.M,
)


def strip_simulated_dialogue(text: str) -> str:
    """Убрать имитацию реплик Шефа и англ. «вопросы к пользователю» из ответа."""
    s = (text or "").strip()
    if not s:
        return s
    m_cut = _FAKE_SELF_INTERVIEW.search(s)
    if m_cut:
        s = s[: m_cut.start()].strip()
    blocks = re.split(r"\n\s*\n", s)
    kept: list[str] = []
    for block in blocks:
        b = block.strip()
        if not b:
            continue
        if _FAKE_SELF_INTERVIEW.search(b):
            continue
        if _SIMULATED_DIALOGUE_EN.search(b):
            continue
        if _FAKE_USER_TURN.search(b):
            continue
        if _CONSUMER_IOT.search(b) and len(b) > 80:
            continue
        lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
        if lines and all(_SIMULATED_SHEF_LINE.match(ln) for ln in lines):
            continue
        if _SIMULATED_SHEF_LINE.match(b) and "?" not in b:
            continue
        kept.append(b)
    if kept:
        return "\n\n".join(kept)
    return s


def strip_consumer_assistant_bleed(text: str, user_text: str = "") -> str:
    """Убрать «ChatGPT про умный дом» и фальшивую самопрезентацию ИИ."""
    s = (text or "").strip()
    if not s:
        return s
    try:
        from modules.dialog_handlers import wants_smart_home_advice

        user_asks_iot = wants_smart_home_advice(user_text)
    except Exception:
        user_asks_iot = False

    if _CONSUMER_IOT.search(s) and not user_asks_iot:
        parts = re.split(r"\n\s*\n", s)
        parts = [p for p in parts if not _CONSUMER_IOT.search(p)]
        s = "\n\n".join(parts).strip()

    s = _WRONG_IDENTITY_BLEED.sub("", s)
    s = re.sub(
        r"чем\s+могу\s+вам\s+помочь[^.!?\n]*[.!?]?",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(
        r"приятно\s+познакомиться,?\s+[а-яёa-z]+\.\s*я\s*[-—]?\s*jarvis[^.!?\n]*[.!?]?",
        "",
        s,
        flags=re.I,
    )
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def strip_reasoning_chatter(text: str) -> str:
    """Убрать предложения-рассуждения, оставить итог ответа (абзацы сохраняются)."""
    s = (text or "").strip()
    if not s:
        return s
    s = _PROCESS_PLACEHOLDER.sub("", s).strip()
    blocks = re.split(r"\n\s*\n", s)
    out_blocks: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        parts = [p.strip() for p in _SENTENCE_SPLIT.split(block) if p.strip()]
        if not parts:
            continue
        kept = [p for p in parts if not _sentence_is_reasoning(p)]
        if kept:
            out_blocks.append(" ".join(kept))
    if out_blocks:
        return "\n\n".join(out_blocks)
    return s


def dry_style_instruction() -> str:
    return (
        "[Сухой стиль Jarvis] Без извинений («извините», «к сожалению»). "
        "Не объясняй, что ты ИИ/языковая модель — ты Jarvis. "
        "Без хвостов «могу помочь?», «если есть вопросы». "
        "Опечатка 2–3 букв в приветствии — **не исправляй**; ответь по смыслу. "
        "Не понял — один короткий уточняющий вопрос. "
        "Нет данных → «Данных нет»; неясная задача → «Задача неясна».\n"
    )


def no_reasoning_instruction() -> str:
    return (
        dry_style_instruction()
        + "[Формат] Только готовый ответ Шефу. Запрещены рассуждения вслух, "
        "внутренний монолог, вопросы к себе, «Продолжим?», «сначала мне нужно», "
        "симуляция диалога и «(Процесс…)». Рассуждения — только если Шеф явно просит "
        "«объясни ход мыслей» / «подробно как ты думал».\n"
    )


def strip_apology_and_filler(text: str) -> str:
    """Убрать извинения, дисклеймеры ИИ и вежливые хвосты из ответа модели."""
    s = (text or "").strip()
    if not s or "<!-- jarvis-health-report -->" in s:
        return s
    prev = None
    while prev != s:
        prev = s
        s = _APOLOGY_SENTENCE.sub("\n", s)
        s = _AI_DISCLAIMER_SENTENCE.sub("\n", s)
        s = _TYPO_LECTURE.sub("\n", s)
        s = _TRAILING_FOLLOWUP.sub("", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def paragraph_format_instruction() -> str:
    return (
        "[Вёрстка] **Обязательно** делай ответ абзацами: между блоками — пустая строка "
        "(два Enter, в markdown это разные <p>). Никогда не пиши 5+ предложений подряд "
        "без пустой строки. Списки — с новой строки (•). "
        "Не повторяй одну мысль разными словами. "
        "Не начинай с одинокого «—». Ты Jarvis (Qwen + API), не «просто ИИ».\n"
    )


def dedupe_similar_sentences(sentences: list[str]) -> list[str]:
    """Убрать подряд идущие почти одинаковые предложения (зацикливание модели)."""
    out: list[str] = []
    norms: list[str] = []
    for sent in sentences:
        s = (sent or "").strip()
        if not s:
            continue
        n = _norm_chunk(s)
        if any(_chunks_similar(n, prev) for prev in norms[-3:]):
            continue
        norms.append(n)
        out.append(s)
    return out


def normalize_markdown_layout(text: str) -> str:
    """Списки и заголовки: пустые строки для корректного GFM в react-markdown."""
    s = (text or "").strip()
    if not s or "<!-- jarvis-health-report -->" in s:
        return s

    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"(?<!\n)(\#{2,3}\s)", r"\n\n\1", s)
    s = re.sub(r"(?<!\n)(\*\*[^*]+\*\*\s*\n)", r"\n\n\1", s)

    def _break_numbered(m: re.Match[str]) -> str:
        return "\n\n" + m.group(1)

    s = re.sub(r"(?<!\n)(\d{1,2}\.\s+(?:\*\*)?)", _break_numbered, s)
    s = re.sub(r"(?<=[.!?])\s+(?=-\s)", "\n\n", s)
    s = re.sub(r"(?<=[.!?])\s+(?=•\s)", "\n\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def format_reply_paragraphs(text: str, user_text: str = "") -> str:
    """Разбить сплошной текст на абзацы (markdown: пустая строка между блоками)."""
    s = (text or "").strip()
    if not s or "<!-- jarvis-health-report -->" in s or "<!-- jarvis-page-content -->" in s:
        return s
    if s.startswith("```") or s.count("```") >= 2:
        return re.sub(r"\n{3,}", "\n\n", s).strip()

    s = re.sub(r"^[—–\-]\s+", "", s).strip()
    s = re.sub(r"\n{3,}", "\n\n", s)

    blocks = [b.strip() for b in re.split(r"\n\s*\n", s) if b.strip()]
    if len(blocks) > 1:
        return "\n\n".join(blocks)

    parts = dedupe_similar_sentences(
        [p.strip() for p in _SENTENCE_SPLIT.split(s) if p.strip()]
    )
    if len(parts) <= 1:
        return s

    try:
        from modules import local_qwen as lq

        want = lq.requested_paragraph_count(user_text) if user_text else None
        if want and len(parts) >= want:
            per = max(1, (len(parts) + want - 1) // want)
            merged: list[str] = []
            for i in range(0, len(parts), per):
                chunk = parts[i : i + per]
                if chunk:
                    merged.append(" ".join(chunk))
            if len(merged) >= 1:
                return "\n\n".join(merged[:want])
    except Exception:
        pass

    paragraphs: list[str] = []
    buf: list[str] = []
    char_budget = 0
    max_per_para = 2 if len(parts) > 4 else 1
    for sent in parts:
        buf.append(sent)
        char_budget += len(sent)
        if len(buf) >= max_per_para or char_budget >= 140:
            paragraphs.append(" ".join(buf))
            buf = []
            char_budget = 0
    if buf:
        paragraphs.append(" ".join(buf))

    if len(paragraphs) <= 1 and len(parts) >= 2:
        return "\n\n".join(parts)
    return "\n\n".join(paragraphs)


def length_instruction_for_prompt(user_text: str) -> str:
    """Строка в системный промпт Qwen."""
    base = no_reasoning_instruction() + paragraph_format_instruction()
    try:
        from modules import local_qwen as lq

        if lq.is_creative_story_request(user_text):
            n = lq.requested_paragraph_count(user_text) or 3
            return (
                base
                + f"[Сказка] Ровно **{n} абзаца**, сказка целиком с концом. "
                "Без вопросов Шефу и без его реплик в тексте.\n"
            )
    except Exception:
        pass
    try:
        from modules import local_qwen as lq

        if lq.is_greeting_like(user_text):
            return (
                base
                + "[Привет] 1–2 коротких абзаца. Не исправляй опечатки и не переспрашивай "
                "«вы имели в виду…». Ответь по смыслу (привет / нормально). "
                "Без повторов «чем помочь» и без вежливой воды.\n"
            )
    except Exception:
        pass
    try:
        from modules.listing_generation import wants_listing_generation

        if wants_listing_generation(user_text):
            return (
                base
                + "[Объявление Авито] Строго по плейбуку: заголовки, текст 800–1200 символов, "
                "FAQ, CTA «Напишите в чат Авито», SEO-блок. При нехватке данных — "
                "3–5 вопросов, без готового объявления.\n"
            )
    except Exception:
        pass
    if user_wants_brief(user_text):
        return base + "[Длина] Шеф просит кратко: 2–3 предложения в 1–2 абзацах.\n"
    if user_question_is_short(user_text):
        return (
            base
            + "[Длина] Вопрос в одно предложение — ответ строго короткий: "
            "2–4 предложения в **отдельных абзацах** ИЛИ список до 6 пунктов. "
            "Запрещено повторять одну мысль и писать «---».\n"
        )
    if needs_long_reply(user_text):
        return (
            base
            + "[Длина] Вопрос развёрнутый — можно подробно: несколько абзацев, списки и шаги; "
            "без рассуждений вслух.\n"
        )
    return base + "[Длина] Умеренно: 3–6 предложений в 2–3 абзацах, без воды.\n"


def _ends_complete(s: str) -> bool:
    s = (s or "").rstrip()
    if not s:
        return True
    return s[-1] in ".!?…)]»\""


def _norm_chunk(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())[:400]


def _chunks_similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) > 50 and (a in b or b in a):
        return True
    aw = set(a.split())
    bw = set(b.split())
    if len(aw) < 8 or len(bw) < 8:
        return a == b
    overlap = len(aw & bw) / max(len(aw), len(bw))
    return overlap >= 0.72


def _dedupe_repeated_sections(text: str) -> str:
    """Убрать копии абзацев и блоков между --- (зацикливание модели)."""
    raw = (text or "").strip()
    if not raw:
        return raw

    parts = re.split(r"\n\s*---\s*\n", raw)
    if len(parts) <= 1:
        parts = re.split(r"\n\s*\n", raw)

    unique: list[str] = []
    norms: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        n = _norm_chunk(p)
        if any(_chunks_similar(n, prev) for prev in norms):
            continue
        norms.append(n)
        unique.append(p)

    if len(unique) == 1 and len(parts) > 1:
        return unique[0]
    if not unique:
        return raw
    return "\n\n".join(unique)


def repair_truncated_markdown(text: str) -> str:
    """Убрать незакрытые ** / * в конце текста."""
    s = (text or "").rstrip()
    if not s:
        return s

    pairs = s.count("**")
    if pairs % 2 == 1:
        if s.endswith("**"):
            s = s[:-2].rstrip()
        else:
            m = _TRAILING_PARTIAL_BOLD.search(s)
            if m:
                s = s[: m.start()].rstrip()
            else:
                last = s.rfind("**")
                if last >= 0:
                    tail = s[last + 2 :]
                    if not tail or (len(tail) < 8 and " " not in tail):
                        s = s[:last].rstrip()

    if s.count("*") % 2 == 1 and s.endswith("*") and not s.endswith("**"):
        s = s[:-1].rstrip()

    return s


def _trim_unclosed_code_fence(s: str) -> str:
    if s.count("```") % 2 == 0:
        return s
    last = s.rfind("```")
    if last <= 0:
        return s
    before = s[:last].rstrip()
    if len(before) < 60:
        return s
    return (
        before
        + "\n\n_(фрагмент кода обрезан — полный код сохраняйте через "
        "инструмент save_jarvis_skill_code)_"
    )


def trim_incomplete_reply(text: str) -> str:
    """Убрать обрыв на полуслове и хвост после «---»."""
    s = (text or "").strip()
    if not s:
        return s

    s = _TRAILING_FOLLOWUP.sub("", s).strip()

    hr = list(re.finditer(r"\n---\s*\n", s))
    if hr:
        last_hr = hr[-1]
        after = s[last_hr.end() :].strip()
        if after and not _ends_complete(after):
            s = s[: last_hr.start()].rstrip()

    if _ends_complete(s):
        return repair_truncated_markdown(_trim_unclosed_code_fence(s))

    last_end = 0
    for m in _SENTENCE_END.finditer(s):
        last_end = m.end()

    if last_end >= 40:
        tail = s[last_end:].strip()
        words = tail.split()
        if not tail or len(words) <= 4 or (words and len(words[-1]) <= 3):
            s = s[:last_end].rstrip()
    elif len(s.split()) > 8:
        words = s.split()
        if words and len(words[-1]) <= 3 and not words[-1].endswith((".", "!", "?")):
            s = " ".join(words[:-1]).rstrip()
            if s and not _ends_complete(s):
                s += "…"

    s = repair_truncated_markdown(_trim_unclosed_code_fence(s))
    return s


def _compress_at_sentence_boundary(
    s: str,
    *,
    max_sentences: int,
    max_chars: int,
) -> str:
    parts = re.split(r"(?<=[.!?…])\s+", s)
    if len(parts) > max_sentences:
        s = " ".join(parts[:max_sentences]).strip()
        if s and not _ends_complete(s):
            s += "…"

    if len(s) > max_chars:
        chunk = s[:max_chars]
        cut = chunk.rsplit(" ", 1)[0].rstrip() if " " in chunk else chunk.rstrip()
        if len(cut) < 40:
            cut = chunk.rstrip()
        s = cut + ("…" if cut and not _ends_complete(cut) else "")

    return s.strip()


def apply_default_brevity(
    text: str,
    user_text: str = "",
    *,
    max_sentences: int = 6,
    max_chars: int = 1400,
) -> str:
    """Сжать ответ только когда Шеф явно просит кратко — длину выбирает модель."""
    s = _dedupe_repeated_sections(text)
    s = trim_incomplete_reply(s)

    if "<!-- jarvis-health-report -->" in s:
        return s

    if skips_post_brevity(user_text):
        return s

    try:
        from modules.dialog_handlers import is_casual_smalltalk

        if is_casual_smalltalk(user_text):
            return _compress_at_sentence_boundary(s, max_sentences=3, max_chars=320)
    except Exception:
        pass

    if user_wants_expanded(user_text) or needs_long_reply(user_text, text):
        return s

    if user_wants_brief(user_text):
        return _compress_at_sentence_boundary(
            s, max_sentences=4, max_chars=520
        )

    return s


def _strip_leaked_prompt_instructions(text: str) -> str:
    s = text or ""
    for pat in _LEAKED_PROMPT_LINES:
        s = pat.sub("", s)
    s = _FAKE_BASH_AVITO.sub("", s)
    s = _FAKE_BASH_LINE.sub("", s)
    s = re.sub(
        r"Для этого используйте команду\s*`?sync_avito_chats`?\.?",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(
        r"Выполните в терминале:.*$",
        "",
        s,
        flags=re.I | re.M,
    )
    return s.strip()


def polish_assistant_reply(
    text: str,
    user_text: str = "",
    *,
    skip_brevity: bool = False,
) -> str:
    """Финальная очистка ответа перед показом в чате."""
    if "<!-- jarvis-health-report -->" in (text or ""):
        return text
    if "<!-- jarvis-avito-report -->" in (text or ""):
        return text

    s = _dedupe_repeated_sections(text or "")
    s = strip_simulated_dialogue(s)
    s = strip_consumer_assistant_bleed(s, user_text)
    s = strip_reasoning_chatter(s)
    s = strip_apology_and_filler(s)
    s = _strip_leaked_prompt_instructions(s)
    try:
        from modules.dialog_handlers import (
            casual_smalltalk_reply,
            identity_reply,
            is_casual_smalltalk,
            is_pure_identity_question,
            is_wellbeing_smalltalk,
            wellbeing_reply,
        )

        if is_casual_smalltalk(user_text) and (
            len(s) > 90
            or _TYPO_LECTURE.search(s or "")
            or _FAKE_SELF_INTERVIEW.search(s or "")
            or len(re.findall(r"могу\s+помочь", s or "", re.I)) >= 2
        ):
            return casual_smalltalk_reply(user_text)
        if is_wellbeing_smalltalk(user_text) and (
            len(s) > 100 or _FAKE_SELF_INTERVIEW.search(s or "")
        ):
            return wellbeing_reply()
        if is_pure_identity_question(user_text) and (
            len(s) > 200 or _WRONG_IDENTITY_BLEED.search(s or "")
        ):
            return identity_reply()
    except Exception:
        pass
    try:
        from modules.avito_overview_handler import (
            build_avito_overview_reply,
            is_public_avito_catalog_request,
            looks_like_hallucinated_avito_catalog,
        )

        if is_public_avito_catalog_request(user_text) and (
            len(s) > 80 or looks_like_hallucinated_avito_catalog(s)
        ):
            return build_avito_overview_reply(user_text)
        if re.search(r"авито|avito", user_text or "", re.I) and looks_like_hallucinated_avito_catalog(
            s
        ):
            return build_avito_overview_reply(user_text)
    except Exception:
        pass
    s = repair_truncated_markdown(s)
    s = _LEAKED_TRANSLATE.sub("", s)
    s = _LEAKED_TRANSLATE_PLAIN.sub(" ", s)
    s = _TRANSLATION_HEADER.sub("\n", s)
    s = _GLUED_SENTENCES.sub(r"\1. \2", s)
    s = _GLUED_PUNCT.sub(r"\1 \2", s)
    s = _LEAKED_MODE_LINE.sub("", s)
    if _WRONG_IDENTITY_BLEED.search(s):
        s = _WRONG_IDENTITY_BLEED.sub("", s)
        s = re.sub(r"\n{2,}", "\n\n", s).strip()
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"\n\s*---\s*\n+", "\n\n", s)
    s = s.strip()
    if not (skip_brevity or skips_post_brevity(user_text)):
        s = apply_default_brevity(s, user_text)
    s = normalize_markdown_layout(trim_incomplete_reply(s))
    s = format_reply_paragraphs(s, user_text)
    s = normalize_markdown_layout(s)
    try:
        from modules.icq_smileys import polish_reply_smileys

        s = polish_reply_smileys(s, user_text)
    except Exception:
        pass
    return s


_PAGE_REFUSAL_BLEED = re.compile(
    r"impossible as an ai|without using external tools|"
    r"не могу просматривать веб-страниц",
    re.I,
)


def polish_page_content_reply(text: str, user_text: str = "") -> str:
    """Ответ по странице: не сжимать и не вырезать блоки с текстом сайта."""
    if "<!-- jarvis-health-report -->" in (text or ""):
        return text
    s = _dedupe_repeated_sections(text or "")
    s = strip_reasoning_chatter(s)
    s = _strip_leaked_prompt_instructions(s)
    s = _PAGE_REFUSAL_BLEED.sub("", s)
    s = repair_truncated_markdown(s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return format_reply_paragraphs(trim_incomplete_reply(s.strip()), user_text)

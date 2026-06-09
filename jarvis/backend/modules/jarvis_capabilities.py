"""
Фактический перечень возможностей Jarvis для ответов Шефу («что ты умеешь»).
Динамически учитывает установленные ключи и статус компонентов.
"""

from __future__ import annotations


def is_answer_length_meta_question(text: str) -> bool:
    """«Насколько длинные ответы», лимиты текста — не отправлять в DeepSeek."""
    low = (text or "").lower().strip()
    if len(low) > 180:
        return False
    length_signals = (
        "длинн",
        "коротк",
        "сколько символ",
        "сколько слов",
        "лимит",
        "максимум",
        "объём",
        "объем",
        "размер",
        "насколько",
        "простын",
        "много текста",
        "мало текста",
    )
    topic_signals = (
        "ответ",
        "сообщен",
        "текст",
        "выдава",
        "выдавать",
        "писать",
        "писаешь",
        "можешь",
        "умеешь",
    )
    return any(a in low for a in length_signals) and any(b in low for b in topic_signals)


def answer_length_reply_for_user() -> str:
    return (
        "**Длина ответов Jarvis**\n\n"
        "• Обычный чат — **умеренно**: 3–6 предложений в 2–3 абзацах, без воды.\n"
        "• Короткий вопрос — **2–4 предложения** или список до 6 пунктов.\n"
        "• По просьбе «**подробнее**» / «развёрнуто» — длиннее (отчёты, код, Авито).\n"
        "• **Голосовой режим** — короткая речь (до ~1400 символов), без markdown.\n"
        "• Технический потолок генерации — около **2000 токенов** на один ответ.\n\n"
        "Нужен развёрнутый ответ — напишите «подробнее» или уточните тему."
    )


def is_jarvis_meta_question(text: str) -> bool:
    """Мета-вопросы про Jarvis — только локальный фактический ответ."""
    if is_general_capabilities_question(text) or is_answer_length_meta_question(text):
        return True
    try:
        from modules.local_qwen import is_api_or_app_meta_question, is_jarvis_capability_question

        return is_api_or_app_meta_question(text) or is_jarvis_capability_question(text)
    except Exception:
        return False


def try_handle_jarvis_meta_question(text: str) -> tuple[bool, str]:
    """Короткие ответы без облака и без «лекций» модели."""
    if is_general_capabilities_question(text):
        return True, jarvis_capabilities_summary_for_user()
    if is_answer_length_meta_question(text):
        return True, answer_length_reply_for_user()
    try:
        from modules.local_qwen import jarvis_capability_reply

        cap = jarvis_capability_reply(text)
        if cap:
            return True, cap
    except Exception:
        pass
    return False, ""


def is_general_capabilities_question(text: str) -> bool:
    """Общий вопрос про возможности — не узкий подтема (только браузер и т.п.)."""
    from modules.local_qwen import user_requests_live_web_action

    if user_requests_live_web_action(text):
        return False
    low = (text or "").lower().strip()
    if len(low) > 160:
        return False
    general = (
        "что ты умеешь",
        "что умеешь",
        "чем можешь помочь",
        "чем ты можешь",
        "что ты можешь",
        "твои возможност",
        "список возможност",
        "какие функции",
        "какие навыки",
        "что умеет jarvis",
        "возможности jarvis",
        "расскажи про возможност",
    )
    if not any(g in low for g in general):
        return False
    narrow_only = (
        low in ("браузер", "память", "модель", "ollama")
        or (low.count(" ") <= 2 and any(w in low for w in ("браузер", "память", "модел")))
    )
    return not narrow_only


def jarvis_capabilities_summary_for_user() -> str:
    """Структурированный markdown: абзацы и списки для чата."""
    from modules import local_qwen as lq
    from modules.chromium_browser import chromium_browser_status
    from modules.neural_keys import format_availability_for_router, get_neural_availability
    from modules.media_generation import format_media_for_router

    a = get_neural_availability()
    ch = chromium_browser_status()
    qwen_ok = lq.qwen_available()

    lines: list[str] = [
        "**Я — Jarvis**, локальный агент на вашем ПК (не ChatGPT и не «умный календарь»).",
        "",
        "Ответы собирает **роутер**: локальная **Qwen 2.5 14B** + инструменты + при необходимости облако.",
        "",
        "## Нейросети сейчас",
        "",
        format_availability_for_router(),
        "",
        format_media_for_router(),
        "",
        "## Чат и память",
        "",
        "• Один диалог в приложении; история в `chats.json` до выключения сервера или **RESTART**.",
        "• **Долговременная память:** `jarvis.db`, ячейки (`memory_save_cell`), фраза «запомни: …».",
        "• **Сознательное / бессознательное** — файлы в панели разработчика и «Закреп · Сознательное».",
        "• **Техдокументация.txt** — в бессознательном; подмешивается в промпт и перечитывается каждые 10 мин.",
        "• **Автовыбор профиля** (бухгалтер, маркетолог, разработчик) — без переключателя в UI.",
        "",
        "## Интернет и страницы",
        "",
        "• **web_search** — поиск DuckDuckGo.",
        "• **web_research** — **Стереотипы.txt** → Google → выжимка (ссылки внизу).",
    ]
    if ch.get("ready"):
        lines.append(
            "• **fetch_url** — встроенный **Chromium** (headless), страницы с JavaScript."
        )
    else:
        lines.append(
            "• **fetch_url** — нужен **install-chromium.bat** (Chromium ещё не установлен)."
        )
    lines += [
        "• Ссылка `https://` в сообщении — открою и отвечу по содержимому.",
        "• **analyze_page_seo** — разбор сайта простым языком (SEO, смысл, дизайн).",
        "",
        "## Авито",
        "",
        "• Коннектор в сайдбаре: OAuth, метрики в SQLite, синхронизация чатов.",
        "• Инструменты: `get_stored_metrics`, `sync_avito_chats`, `analyze_avito_chats`, архив переписок.",
        "• **Тексты объявлений** (заголовки, SEO, FAQ) — профиль маркетолога, плейбук в `modes/marketer/`.",
        "• Это **не** замена личного кабинета Авито — публикация объявлений вручную.",
        "",
        "## Telegram и UI",
        "",
        "• Панель «Материнское ядро telegram»: токен, polling, `bot_logic.json`, отправка сообщений.",
        "• **ui_***-инструменты — поля и кнопки коннекторов из чата (JSON, не «я уже нажал»).",
        "",
        "## Картинки и видео",
        "",
    ]
    if a.get("media_image") or a.get("media_video"):
        lines.append(
            "• Запросы «нарисуй», «сгенерируй картинку/видео» — облачные провайдеры "
            "(Ideogram, Nano Banana, OpenAI, xAI — что включено в Настройках)."
        )
        lines.append("• Результат показывается **в чате** (изображение или ссылка на видео).")
    else:
        lines.append(
            "• Генерация медиа — после ключей в ⚙️ Настройках (Ideogram / Nano Banana / OpenAI / xAI)."
        )

    lines += [
        "",
        "## Бухгалтерия и документы",
        "",
        "• Выписки `.xlsx`, 1С `.txt` → SQLite; счета, договоры (профиль бухгалтер + DeepSeek при ключе).",
        "",
        "## Код и навыки",
        "",
        "• Профиль **разработчик** — Perplexity или DeepSeek для сложного кода.",
        "• Песочница **modules/jarvis_skills.py** — `save_jarvis_skill_code`, `run_jarvis_skill`.",
        "",
        "## Голос и прочее",
        "",
        "• Микрофон «Джарвис» — голосовой ввод и озвучка ответа (edge-tts / XTTS).",
        "• **Проверка систем** — отчёт со статусами компонентов.",
        "• Таблицы, **mermaid**-диаграммы, графики ```chart в чате.",
        "• Игра `/game` — тамагочи Jarvis с тем же чатом.",
        "",
        "## Чего у меня нет",
        "",
        "• Нет доступа к календарю Windows, умному дому и погоде «из коробки» — только через интернет/инструменты.",
        "• Не выдумываю bash-команды — действия через JSON-инструменты из промпта.",
        "",
        "_Подробности — **Техдокументация.txt** в бессознательном (`data/memory/unconscious/`); перечитываю каждые 10 минут._",
    ]

    if not qwen_ok:
        lines.insert(
            4,
            "⚠ **Qwen пока не загружена** — установите модель: **install-qwen.bat** или **start.bat**.",
        )

    return "\n".join(lines)

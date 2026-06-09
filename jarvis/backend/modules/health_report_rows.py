"""
Строки отчёта «Проверка систем» — те же блоки, что меню Настроек и панель индикаторов.
"""

from __future__ import annotations

from modules.agent import MODE_LABELS, AgentMode, get_mode, get_runtime

Row = tuple[str, str, str]  # level, name, detail


def _level_ok() -> str:
    return "ok"


def _level_warn() -> str:
    return "warn"


def _level_err() -> str:
    return "err"


def _level_off() -> str:
    return "off"


def _qwen_row(qwen: dict) -> Row:
    name = "Qwen 2.5 14B"
    if qwen.get("ready"):
        detail = qwen.get("message") or qwen.get("value") or qwen.get("status_label") or "готов"
        if len(str(detail)) > 100:
            detail = f"{qwen.get('status_label', 'OK')}: {qwen.get('value') or 'готов'}"
        return (_level_ok(), name, str(detail))
    st = qwen.get("status") or ""
    if st in ("downloading", "loading_ram", "pending_ram"):
        return (
            _level_warn(),
            name,
            qwen.get("message") or qwen.get("status_label") or "Загрузка…",
        )
    if qwen.get("files_present"):
        return (
            _level_err(),
            name,
            qwen.get("message") or "Модель на диске, но не в памяти — Настройки → Ядро",
        )
    return (
        _level_off(),
        name,
        qwen.get("message") or "Файл GGUF не найден — «Скачать модель» в Настройках → Ядро",
    )


def _deepseek_core_row(flags: dict) -> Row:
    configured = flags.get("deepseek_configured")
    active = flags.get("deepseek_active", True)
    usable = flags.get("deepseek_usable")
    if not configured:
        return (_level_warn(), "DeepSeek", "Нужен ключ sk-… — Настройки → Ядро Jarvis")
    if not active:
        return (_level_off(), "DeepSeek", "Ключ есть, сервис выключен тумблером в Настройках")
    if usable:
        return (_level_ok(), "DeepSeek", "Облако готово — диалог и бухгалтерский режим")
    return (_level_warn(), "DeepSeek", "Ключ сохранён, но сервис неактивен")


def _api_key_row(
    label: str,
    configured: bool,
    active: bool,
    usable: bool,
    purpose: str,
) -> Row:
    if not configured:
        return (_level_off(), label, f"Не задан — {purpose}")
    if not active:
        return (_level_off(), label, f"Ключ есть, выключен — Настройки → API для режимов")
    if usable:
        return (_level_ok(), label, purpose)
    return (_level_warn(), label, f"Ключ есть — включите тумблер в Настройках")


def _telegram_rows(tg: dict) -> list[Row]:
    rows: list[Row] = []
    if tg.get("bot_token_configured"):
        rows.append((_level_ok(), "Токен", "BotFather сохранён — Коннектор Телеграм"))
    else:
        rows.append(
            (
                _level_warn(),
                "Токен",
                "Требуется — Настройки → Коннектор Телеграм → «Сохранить токен»",
            )
        )

    st = tg.get("status") or "off"
    if st == "error":
        det = tg.get("error") or tg.get("last_event") or "Ошибка Telegram API"
        rows.append((_level_err(), "Сервер бота", det))
    elif st == "active" and tg.get("polling_active"):
        user = f"@{tg['bot_username']}" if tg.get("bot_username") else "активен"
        rows.append((_level_ok(), "Сервер бота", f"Опрос Telegram · {user}"))
    elif st == "waiting" or (tg.get("enabled") and not tg.get("polling_active")):
        rows.append(
            (
                _level_warn(),
                "Сервер бота",
                tg.get("last_event") or "Запуск опроса Telegram…",
            )
        )
    elif tg.get("bot_token_configured") and not tg.get("enabled"):
        rows.append(
            (
                _level_off(),
                "Сервер бота",
                "Токен OK — включите «Сервер бота» в Коннектор Телеграм",
            )
        )
    else:
        rows.append((_level_off(), "Сервер бота", tg.get("status_label") or "Выключен"))

    logic_name = tg.get("bot_logic_name") or "bot_logic.json"
    if not tg.get("bot_logic_configured"):
        rows.append((_level_off(), "bot_logic (JSON)", "Файл не найден — Коннектор Телеграм"))
    elif tg.get("bot_logic_valid"):
        rows.append((_level_ok(), "bot_logic (JSON)", f"Схема OK · «{logic_name}»"))
    else:
        err = (tg.get("bot_logic_error") or "").strip()
        rows.append(
            (
                _level_warn(),
                "bot_logic (JSON)",
                err or "JSON не проходит проверку схемы",
            )
        )
    return rows


def _avito_rows(av: dict) -> list[Row]:
    keys = av.get("client_id_configured") and av.get("client_secret_configured")
    if keys:
        rows = [(_level_ok(), "Ключи API", "Client ID и Secret сохранены")]
    elif av.get("client_id_configured") or av.get("client_secret_configured"):
        rows = [(_level_warn(), "Ключи API", "Укажите оба ключа — Коннектор Авито")]
    else:
        rows = [(_level_off(), "Ключи API", "Не заданы — Настройки → Коннектор Авито")]

    if not keys:
        rows.append((_level_off(), "Синхронизация", "После сохранения ключей API"))
    elif av.get("status") == "error":
        rows.append(
            (
                _level_err(),
                "Синхронизация",
                av.get("error") or av.get("last_event") or "Ошибка API Авито",
            )
        )
    elif av.get("enabled") and av.get("ready"):
        det = av.get("status_label") or "Активна"
        if av.get("last_sync_date"):
            det += f" · {av['last_sync_date']}"
        rows.append((_level_ok(), "Синхронизация", det))
    elif av.get("enabled"):
        rows.append((_level_warn(), "Синхронизация", av.get("last_event") or "Запуск…"))
    else:
        rows.append((_level_off(), "Синхронизация", "Включите в Коннектор Авито"))
    return rows


def _mail_rows(mail: dict) -> list[Row]:
    rows: list[Row] = []
    for slot in mail.get("slots") or []:
        n = slot.get("slot") or "?"
        label = slot.get("label") or f"Ящик {n}"
        email = (slot.get("email") or "").strip()
        title = f"{label}" + (f" ({email})" if email else "")

        if not slot.get("enabled"):
            rows.append((_level_off(), title, slot.get("status_label") or "Выключен"))
            continue
        st = slot.get("status") or "off"
        if st == "ok":
            rows.append((_level_ok(), title, slot.get("last_event") or "Подключено"))
        elif st == "need_creds":
            rows.append((_level_warn(), title, "Нужен email и пароль приложения"))
        elif st == "error":
            rows.append(
                (
                    _level_warn(),
                    title,
                    slot.get("error") or slot.get("last_event") or "Ошибка IMAP",
                )
            )
        else:
            rows.append((_level_off(), title, slot.get("status_label") or "Не настроен"))
    if not rows:
        rows.append((_level_off(), "Почтовые ящики", "Нет слотов — Настройки → Почтовый клиент"))
    return rows


def _readiness_rows(
    qwen: dict,
    flags: dict,
    mode: AgentMode,
    rt,
    xtts: dict,
    voice_base: dict,
    ram: dict,
) -> list[Row]:
    qwen_ready = bool(qwen.get("ready") or qwen.get("ollama_model_loaded"))
    ram_on = bool(qwen.get("ram_enabled"))
    ds_usable = bool(flags.get("deepseek_usable"))
    core_ready = qwen_ready or ds_usable

    if not core_ready:
        combat = (
            _level_warn(),
            "Боеготовность",
            "Ядро не готово — Qwen в ОЗУ или DeepSeek в Настройках → Ядро",
        )
    elif rt.status and rt.status != "IDLE":
        combat = (_level_ok(), "Боеготовность", f"Jarvis занят: {rt.status}")
    else:
        conn = []
        if ram_on and qwen_ready:
            conn.append("Qwen в ОЗУ")
        if ds_usable:
            conn.append("DeepSeek")
        combat = (
            _level_ok(),
            "Боеготовность",
            "Можно писать в чат · " + (" · ".join(conn) if conn else "ядро готово"),
        )

    mode_label = MODE_LABELS.get(mode, mode.value)
    if mode == AgentMode.DEVELOPER:
        if qwen_ready:
            code = (_level_ok(), "Код", "Локальная Qwen — режим разработчика")
        elif ds_usable:
            code = (_level_ok(), "Код", "DeepSeek + облако")
        elif flags.get("perplexity_usable"):
            code = (_level_warn(), "Код", "Только Perplexity — добавьте DeepSeek или Qwen")
        else:
            code = (_level_warn(), "Код", "Нужен Perplexity / DeepSeek / Qwen")
    elif mode == AgentMode.MARKETER:
        code = (
            (_level_ok() if core_ready else _level_warn()),
            "Режим",
            f"«{mode_label}» · ядро {'готово' if core_ready else 'не готово'}",
        )
    else:
        code = (
            (_level_ok() if core_ready else _level_warn()),
            "Чат" if mode == AgentMode.STANDARD else "Режим",
            f"«{mode_label}» · ядро {'готово' if core_ready else 'не готово'}",
        )

    nb = flags.get("nanobanana_usable") or flags.get("nanobanana_configured")
    if mode == AgentMode.MARKETER and flags.get("nanobanana_usable"):
        images = (_level_ok(), "Изображения", "Nano Banana — режим маркетолога")
    elif flags.get("nanobanana_configured"):
        images = (_level_warn(), "Изображения", "Ключ есть — режим «Маркетолог+Дизайнер»")
    else:
        images = (_level_off(), "Изображения", "Ключ Google AI — API для режимов")

    x_st = xtts.get("status") or ""
    model = xtts.get("model") or "v5_ru"
    if xtts.get("error") or "ошибк" in str(xtts.get("message") or "").lower():
        voice = (_level_err(), "Доступность голоса", xtts.get("message") or "Ошибка Silero")
    elif x_st in ("installing_deps", "downloading_model", "downloading"):
        voice = (_level_warn(), "Доступность голоса", xtts.get("message") or "Установка Silero…")
    elif xtts.get("status") == "ready" or xtts.get("importable"):
        parts = [f"Silero {model}"]
        if rt.chat_speech_enabled:
            parts.append("озвучка ответов")
        if rt.voice_enabled:
            parts.append("микрофон")
        voice = (_level_ok(), "Доступность голоса", " · ".join(parts))
    else:
        voice = (_level_warn(), "Доступность голоса", "Настройки → Голос → Установить Silero")

    if ram.get("qwen_ram_loading") or ram.get("launching"):
        ram_label = "Загрузка в ОЗУ"
        pct = ram.get("load_progress_percent") or ram.get("jarvis_percent_of_total") or 0
        ram_row = (
            _level_warn(),
            ram_label,
            f"{pct}% · Jarvis {ram.get('jarvis_rss_mb', 0)} МБ",
        )
    else:
        pct = ram.get("jarvis_percent_of_total") or 0
        ram_row = (
            _level_ok() if pct < 75 else _level_warn(),
            "Загруженность ОЗУ",
            f"Jarvis {ram.get('jarvis_rss_mb', 0)} МБ · {pct}% от RAM ПК · "
            f"система {ram.get('system_used_percent', 0)}%",
        )

    return [combat, code, images, voice, ram_row]


def collect_health_report_sections() -> dict[str, list[Row]]:
    from modules import avito as avito_module
    from modules import local_qwen as lq
    from modules import mail_client
    from modules import telephony as telephony_module
    from modules import tg_twin
    from modules import voice as voice_module
    from modules.jarvis_memory import get_ram_snapshot
    from modules.memory_store import get_stores_summary
    from modules.service_flags import service_flags_payload

    qwen = lq.get_qwen_status()
    flags = service_flags_payload()
    tg = tg_twin.to_dict()
    av = avito_module.to_dict()
    tel = telephony_module.to_dict()
    mail = mail_client.to_dict()
    xtts = voice_module.get_xtts_status()
    voice_base = voice_module.get_base_voice_info()
    mode = get_mode()
    rt = get_runtime()
    mem = get_stores_summary()
    ram = get_ram_snapshot()

    from modules.chromium_browser import chromium_browser_status

    ch = chromium_browser_status()
    if ch.get("ready"):
        ch_lv = _level_ok()
    elif ch.get("install_in_progress"):
        ch_lv = _level_warn()
    elif ch.get("playwright_installed"):
        ch_lv = _level_warn()
    else:
        ch_lv = _level_off()
    ch_val = ch.get("status_label") or "—"
    ch_det = ch.get("detail") or ch.get("install_message") or "автоустановка при интернете"

    from modules.system_google_chrome import google_chrome_status

    gc = google_chrome_status()
    if gc.get("ready"):
        gc_lv = _level_ok()
    elif gc.get("install_in_progress"):
        gc_lv = _level_warn()
    elif gc.get("required_on_windows"):
        gc_lv = _level_warn()
    else:
        gc_lv = _level_off()
    gc_det = gc.get("detail") or "оконный режим (2ГИС)"

    core: list[Row] = [
        (_level_ok(), "Сервер", "Локальный Jarvis отвечает (start.bat / restart.bat)"),
        _qwen_row(qwen),
        _deepseek_core_row(flags),
        (ch_lv, "Chromium (headless, Jarvis)", f"{ch_val} · {ch_det}"),
    ]
    if gc.get("required_on_windows"):
        core.append(
            (
                gc_lv,
                "Google Chrome (Jarvis, окно)",
                f"{gc.get('status_label') or '—'} · {gc_det}",
            )
        )

    readiness = _readiness_rows(qwen, flags, mode, rt, xtts, voice_base, ram)

    api_keys: list[Row] = [
        _api_key_row(
            "DeepSeek",
            flags.get("deepseek_configured"),
            flags.get("deepseek_active", True),
            flags.get("deepseek_usable"),
            "Диалог, бухгалтер — дублирует ядро при включённом тумблере",
        ),
        _api_key_row(
            "Grok (xAI)",
            flags.get("xai_configured"),
            flags.get("xai_active"),
            flags.get("xai_usable"),
            "Опциональный облачный диалог",
        ),
        _api_key_row(
            "ChatGPT (OpenAI)",
            flags.get("openai_configured"),
            flags.get("openai_active"),
            flags.get("openai_usable"),
            "Опциональный облачный диалог",
        ),
        _api_key_row(
            "Perplexity",
            flags.get("perplexity_configured"),
            flags.get("perplexity_active"),
            flags.get("perplexity_usable"),
            "Режим «Разработчик» — код и поиск",
        ),
        _api_key_row(
            "Ideogram",
            flags.get("ideogram_configured"),
            flags.get("ideogram_active"),
            flags.get("ideogram_usable"),
            "Генерация изображений (ideogram.ai)",
        ),
        _api_key_row(
            "Nano Banana",
            flags.get("nanobanana_configured"),
            flags.get("nanobanana_active"),
            flags.get("nanobanana_usable"),
            "Режим «Маркетолог+Дизайнер» — картинки",
        ),
    ]

    voice_block: list[Row] = []
    try:
        from modules.voice_stt import get_stt_status

        stt = get_stt_status()
        stt_msg = stt.get("message") or stt.get("model") or "—"
        if stt.get("error"):
            voice_block.append((_level_err(), "GigaAM-v3 (STT)", str(stt["error"])[:120]))
        elif stt.get("loading"):
            voice_block.append((_level_warn(), "GigaAM-v3 (STT)", "Загрузка модели…"))
        elif stt.get("ready") and stt.get("engine") == "gigaam":
            voice_block.append((_level_ok(), "GigaAM-v3 (STT)", stt_msg))
        elif stt.get("gigaam_installed") and stt.get("ffmpeg"):
            voice_block.append(
                (_level_warn(), "GigaAM-v3 (STT)", stt_msg or "Модель загрузится при первом запросе")
            )
        else:
            voice_block.append(
                (_level_off(), "GigaAM-v3 (STT)", "install-chat-voice.bat (GigaAM + ffmpeg)")
            )
    except Exception:
        voice_block.append((_level_off(), "GigaAM-v3 (STT)", "Модуль STT недоступен"))
    x_msg = xtts.get("message") or ""
    if xtts.get("error") or "ошибк" in x_msg.lower():
        voice_block.append((_level_err(), "Silero TTS", x_msg or "Ошибка движка"))
    elif xtts.get("status") in ("installing_deps", "downloading_model", "downloading"):
        voice_block.append((_level_warn(), "Silero TTS", x_msg or "Загрузка…"))
    elif xtts.get("status") == "ready" or xtts.get("importable"):
        spk = xtts.get("selected_speaker") or "aidar"
        voice_block.append(
            (_level_ok(), "Silero TTS", x_msg or f"{xtts.get('model') or 'v5_ru'}, голос {spk}")
        )
    else:
        voice_block.append((_level_off(), "Silero TTS", "Установить в Настройках → Голос и озвучка"))
    mic = "вкл" if rt.voice_enabled else "выкл"
    sp = "вкл" if rt.chat_speech_enabled else "выкл"
    voice_block.append(
        (
            _level_ok() if rt.voice_enabled or rt.chat_speech_enabled else _level_off(),
            "Голос в чате",
            f"Микрофон {mic} · озвучка ответов {sp}",
        )
    )

    session: list[Row] = []
    mode_label = MODE_LABELS.get(mode, mode.value)
    mode_ok = True
    mode_detail = mode_label
    if mode == AgentMode.MARKETER and not flags.get("media_image_ready"):
        mode_ok = False
        mode_detail = f"{mode_label} — нужен медиа-провайдер (Ideogram / Nano Banana / OpenAI / xAI)"
    elif mode == AgentMode.ACCOUNTANT and not flags.get("deepseek_usable"):
        mode_ok = False
        mode_detail = f"{mode_label} — нужен DeepSeek"
    elif mode == AgentMode.DEVELOPER and not (
        flags.get("perplexity_usable")
        or flags.get("deepseek_usable")
        or qwen.get("ready")
    ):
        mode_ok = False
        mode_detail = f"{mode_label} — Perplexity / DeepSeek / Qwen"
    session.append(
        ("ok" if mode_ok else "warn", "Режим чата (верхняя панель)", mode_detail)
    )

    unc = len(mem.get("unconscious") or [])
    con = len(mem.get("conscious") or [])
    session.append(
        (_level_ok(), "Память (файлы)", f"Сознательное: {con} · Бессознательное: {unc}")
    )

    from modules.jarvis_docs import probe_tech_doc_part, probe_web_stack_parts

    for web_lv, web_name, web_det in probe_web_stack_parts():
        session.append((web_lv, web_name, web_det))

    session.append(probe_tech_doc_part())

    telephony: list[Row] = []
    if tel.get("enabled"):
        telephony.append(
            (
                _level_ok() if tel.get("status") == "active" else _level_warn(),
                "Звонки",
                tel.get("status_label") or "Jarvis-ATS",
            )
        )
    else:
        telephony.append((_level_off(), "Звонки", tel.get("status_label") or "Выключено"))

    return {
        "core": core,
        "readiness": readiness,
        "api_keys": api_keys,
        "telegram": _telegram_rows(tg),
        "avito": _avito_rows(av),
        "telephony": telephony,
        "mail": _mail_rows(mail),
        "voice": voice_block,
        "session": session,
    }

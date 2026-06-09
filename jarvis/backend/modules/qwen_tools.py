"""
Инструменты («руки») локальной Qwen 2.5 14B: веб-поиск, SQLite / Авито.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

MAX_TOOL_ROUNDS = 5

# JSON: {"tool": "web_search", "arguments": {"query": "..."}}
_JSON_TOOL_RE = re.compile(
    r'\{\s*"tool"\s*:\s*"([a-z_]+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})\s*\}',
    re.I | re.S,
)
# Запасной формат: <tool>имя|аргументы>
_TAG_TOOL_RE = re.compile(r"<tool>([a-z_]+)\|([^<]+)</tool>", re.I)

QWEN_TOOLS_SYSTEM = """
---
[Инструменты Jarvis — ПРИОРИТЕТ UI и панелей сайдбара]

Формат вызова (одна строка, без markdown и текста вокруг):
{"tool": "ИМЯ", "arguments": { ... }}

**Сначала UI / Telegram / Авито (панели слева в приложении):**

1) **ui_get_app_state** — поля «Материнское ядро telegram» и «Коннектор Авито», индикаторы.
   arguments: {}

2) **ui_set_telegram_field** — токен, прокси или bot_logic.json.
   arguments: {"field": "bot_token"|"telegram_proxy"|"bot_logic", "value": "…", "persist": true}

3) **ui_set_avito_field** — Client ID, Secret, User ID.
   arguments: {"field": "client_id"|"client_secret"|"user_id", "value": "…", "persist": true}

4) **ui_apply_text_to_connectors** — ключи из текста Шефа в поля.
   arguments: {"text": "…", "persist": true}

5) **ui_click** — arguments: {"action": "expand_telegram"|"expand_avito"|"telegram_server_on"|"telegram_server_off"|"avito_sync_on"|"avito_sync_off"}

6) **telegram_mother_core_status** — статус бота (polling, bot_logic).
   arguments: {}

7) **telegram_send_message** — сообщение от бота.
   arguments: {"chat_id": "123456789", "text": "…"}

**Почта (4 провайдера + legacy IMAP в настройках):**

8) **mail_list_accounts** — какие ящики настроены (slot, id, email).
   arguments: {}

9) **mail_list_messages** — список писем (тема, от кого, uid).
   arguments: {"account_id": "…", "slot": 1, "provider": "gmail"|"yandex"|"icloud"|"mailru"|"legacy", "folder": "INBOX", "limit": 20, "unread_only": false}

10) **mail_get_message** — полный текст письма по uid из mail_list_messages.
   arguments: {"uid": "123", "account_id": "…", "slot": 1, "provider": "gmail", "folder": "INBOX"}

11) **mail_mark_read** — пометить прочитанным (read=true) или непрочитанным (read=false).
   arguments: {"uid": "123", "read": true, "account_id": "…", "slot": 1, "provider": "gmail", "folder": "INBOX"}

**Данные и интернет:**

8) **get_stored_metrics** — метрики Авито из SQLite.
   arguments: {"period": "week"}

9) **fetch_and_save_avito_metrics** — скачать свежую аналитику с API Авито.
   arguments: {"days": 3}

10) **sync_avito_chats** — скачать чаты и сообщения Авито в локальный архив (accountant.db).
   arguments: {"max_chats": 500, "messages_per_chat": 100}

11) **get_avito_chats** — список чатов из локального архива (после sync_avito_chats).
   arguments: {"limit": 30, "search": ""}

12) **get_avito_chat_messages** — сообщения чата из архива.
   arguments: {"chat_id": "…", "limit": 50}

13) **probe_avito_api** — диагностика прав API (профиль, messenger, stats).

14) **sync_avito_chats_period** — чаты и сообщения за N дней в архив.
   arguments: {"days": 30, "max_chats": 500}

15) **analyze_avito_chats** — анализ переписок (собеседование, адрес, телефон).
   arguments: {"days": 30}

16) **run_avito_chat_pipeline** — синхронизация + анализ за месяц.
   arguments: {"days": 30}

17) **purge_avito_chat** — удалить переписку чата из архива после выгрузки.
   arguments: {"chat_id": "…"}

**Авито-агент (SQLite + действия в кабинете):**

20) **sync_all_avito_data** — полная синхронизация API → SQLite (профиль, объявления, статистика, чаты).
   arguments: {"force": false, "stats_days": 14, "max_chats": 500}

21) **execute_local_sql_query** — только SELECT к таблицам avito_* / extracted_interviews.
   arguments: {"query": "SELECT …", "max_rows": 100}

22) **avito_press_button** — действие в кабинете: update_price | toggle_status | apply_boost.
   **Нельзя** писать в чаты Авито (только чтение архива).
   arguments: {"action_type": "update_price", "params": {"item_id": "…", "new_price": 1000}}

23) **avito_report_stats** — отчёт CTR из SQLite (без выдуманных цифр).
   arguments: {"days": 14}

24) **avito_mine_hr** — HR-майнер: обещания визита → extracted_interviews.
   arguments: {"hours": 48}

25) **avito_audit_listings** — аудит слабых объявлений по конверсии.
   arguments: {"days": 14}

26) **avito_list_interviews** — кто обещал прийти (из extracted_interviews).

18) **web_search** — быстрый поиск (сниппеты DuckDuckGo).
   arguments: {"query": "текст запроса"}

18b) **exchange_rate** — курс ЦБ РФ (мгновенно, без браузера).
   arguments: {"query": "курс доллара сегодня"}

19) **web_research** — уточнить запрос → **Стереотипы.txt** (приоритет) → Google → до 10 стр. → выжимка; ссылки внизу.
   arguments: {"query": "текст запроса", "max_pages": 10}

20) **fetch_url** — открыть страницу во **встроенном Chromium** Jarvis (headless Playwright).
   arguments: {"url": "https://…"}

15) **memory_save_cell** — долговременная память в jarvis.db (видна во всех чатах режима).
   arguments: {"cell_key": "краткое_имя", "content": "текст факта", "mode_code": null|"accountant"|"marketer"|"developer"}

**Изображения в текстовом чате (MS Paint, без Photoshop):**

27) **image_crop** — обрезка изображения.
   arguments: {"image_id": "…", "left": 0, "top": 0, "right": 100, "bottom": 100}

28) **image_convert** — jpg / png / webp.
   arguments: {"image_id": "…", "format": "png"|"jpg"|"webp"}

29) **image_transparency** — убрать или добавить прозрачный фон.
   arguments: {"image_id": "…", "mode": "remove"|"add"}

После обработки **обязательно** покажи результат: markdown ![](url) из ответа инструмента.

**Песочница навыков (только modules/jarvis_skills.py):**

16) **save_jarvis_skill_code** — перезаписать файл песочницы (полный Python-текст с class CustomSkills).
   arguments: {"code": "# полный файл\\nclass CustomSkills: ..."}

17) **jarvis_skills_ping** — проверить, что песочница загружена.
   arguments: {}

18) **list_jarvis_skills** — список методов CustomSkills.
   arguments: {}

19) **run_jarvis_skill** — вызвать метод CustomSkills.
   Для словаря оскорблений: add_insult_lexicon (аргумент — слово/фраза), insult_lexicon_stats.
   arguments: {"method": "ping_skills"}

Примеры (копируй формат):
{"tool": "ui_get_app_state", "arguments": {}}
{"tool": "ui_click", "arguments": {"action": "telegram_server_on"}}
{"tool": "get_stored_metrics", "arguments": {"period": "week"}}
{"tool": "memory_save_cell", "arguments": {"cell_key": "шеф_предпочтения", "content": "…"}}

Правила:
• Шеф просит изменить поле / включить сервер / метрики Авито → **сначала JSON-инструмент**, не «я уже сделал».
• Не выдумывай цифры Авито и переписки — **sync_all_avito_data** / get_stored_metrics / execute_local_sql_query.
• Шеф про чаты/соискателей/переписку Авито → **sync_all_avito_data** или sync_avito_chats, затем get_avito_chats.
• Изменить цену/статус объявления → **avito_press_button** (не «я уже сделал» без JSON).
• **Не** отправлять сообщения в чаты Авито — в Jarvis это отключено; только sync/анализ чатов.
• Шеф просит «запомни» факт → **memory_save_cell**, не отвечай «не могу между чатами».
• Не отрицай интернет и jarvis.db — у Jarvis они есть.
• **Песочница:** Шеф просит код/функцию/навык → **save_jarvis_skill_code** (полный файл), НЕ длинный Python в чате.
  В чате — только итог: что сохранено и `run_jarvis_skill("метод")`.
• После блока [Результат инструмента ...] — ответ Шефу по-русски, без JSON.
• Не повторяй один и тот же абзац дважды подряд.
• Ответ Шефу — **абзацами** (пустая строка между блоками), списки с новой строки; не сплошная «простыня».
• **Никогда** не пиши `bash`, `login_avito_oauth`, `sync_avito_chats` как shell-команды — только JSON {"tool":"sync_avito_chats_period",...}.
""".strip()


def _iter_json_objects(raw: str) -> list[str]:
    """Все сбалансированные {...} в тексте, содержащие ключ tool или action."""
    out: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] != "{":
            i += 1
            continue
        depth = 0
        start = i
        for j in range(i, n):
            ch = raw[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = raw[start : j + 1]
                    if '"tool"' in chunk or '"action"' in chunk:
                        out.append(chunk)
                    i = j + 1
                    break
        else:
            break
    return out


def _normalize_tool_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    """Поддержка {"tool":...} и усечённого {"action":"ui_click",...}."""
    if not isinstance(data, dict):
        return None
    tool = (data.get("tool") or "").strip().lower()
    if tool:
        if tool not in VALID_TOOLS:
            return None
        args = data.get("arguments")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return None
        return {"tool": tool, "arguments": args}

    action = (data.get("action") or "").strip().lower()
    if not action:
        return None
    # ui_click: {"action": "telegram_server_on"}
    if action in (
        "open_settings",
        "expand_telegram",
        "expand_avito",
        "telegram_server_on",
        "telegram_server_off",
        "avito_sync_on",
        "avito_sync_off",
        "collapse_indicators",
    ):
        return {"tool": "ui_click", "arguments": {"action": action}}
    if action.startswith("ui_") and action in VALID_TOOLS:
        args = {k: v for k, v in data.items() if k != "action"}
        return {"tool": action, "arguments": args}
    return None


def _parse_json_tool(s: str) -> dict[str, Any] | None:
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return None
    return _normalize_tool_payload(data)


def parse_tool_call(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None

    for block in re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S | re.I):
        call = _parse_json_tool(block)
        if call:
            return call

    for chunk in _iter_json_objects(raw):
        call = _parse_json_tool(chunk)
        if call:
            return call

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{") and ('"tool"' in line or '"action"' in line):
            call = _parse_json_tool(line)
            if call:
                return call

    m = _JSON_TOOL_RE.search(raw)
    if m:
        call = _parse_json_tool(m.group(0))
        if call:
            return call

    m = _TAG_TOOL_RE.search(raw)
    if m:
        name = m.group(1).strip().lower()
        arg_raw = m.group(2).strip()
        if name == "web_search":
            return {"tool": name, "arguments": {"query": arg_raw}}
        if name == "web_research":
            return {"tool": name, "arguments": {"query": arg_raw, "max_pages": 10}}
        if name == "get_stored_metrics":
            return {"tool": name, "arguments": {"period": arg_raw}}
        if name == "fetch_and_save_avito_metrics":
            return {"tool": name, "arguments": {}}
        if name == "ui_click":
            return {"tool": name, "arguments": {"action": arg_raw}}
        if name.startswith("ui_") and name in VALID_TOOLS:
            return {"tool": name, "arguments": {}}
    return None


VALID_TOOLS = frozenset(
    {
        "web_search",
        "web_research",
        "exchange_rate",
        "fetch_url",
        "fetch_and_save_avito_metrics",
        "get_stored_metrics",
        "sync_avito_chats",
        "get_avito_chats",
        "get_avito_chat_messages",
        "probe_avito_api",
        "sync_avito_chats_period",
        "analyze_avito_chats",
        "run_avito_chat_pipeline",
        "purge_avito_chat",
        "ui_get_app_state",
        "ui_set_telegram_field",
        "ui_set_avito_field",
        "ui_apply_text_to_connectors",
        "ui_click",
        "ui_mode_developer",
        "ui_mode_standard",
        "ui_mode_accountant",
        "ui_mode_marketer",
        "telegram_mother_core_status",
        "telegram_send_message",
        "memory_save_cell",
        "save_jarvis_skill_code",
        "jarvis_skills_ping",
        "list_jarvis_skills",
        "run_jarvis_skill",
        "hf_search",
        "hf_download_skill",
        "hf_list_skills",
        "hf_enable_skill",
        "sync_all_avito_data",
        "execute_local_sql_query",
        "avito_press_button",
        "avito_report_stats",
        "avito_mine_hr",
        "avito_audit_listings",
        "avito_list_interviews",
        "image_crop",
        "image_convert",
        "image_transparency",
        "mail_list_accounts",
        "mail_list_messages",
        "mail_get_message",
        "mail_mark_read",
    }
)


def _mail_target_args(args: dict[str, Any]) -> dict[str, Any]:
    account_id = str(args.get("account_id") or "").strip() or None
    slot_raw = args.get("slot")
    slot = int(slot_raw) if slot_raw not in (None, "", "null") else None
    provider = str(args.get("provider") or "").strip() or None
    folder = str(args.get("folder") or "INBOX").strip() or "INBOX"
    return {
        "account_id": account_id,
        "slot": slot,
        "provider": provider,
        "folder": folder,
    }


def _parse_period(period: str) -> tuple[str, str]:
    p = (period or "week").strip().lower()
    today = date.today()
    if p in ("week", "неделя", "неделю", "7", "7d", "за неделю"):
        return (today - timedelta(days=7)).isoformat(), today.isoformat()
    if p in ("month", "месяц", "30", "30d", "за месяц"):
        return (today - timedelta(days=30)).isoformat(), today.isoformat()
    if ".." in p:
        a, _, b = p.partition("..")
        return a.strip()[:10], b.strip()[:10]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", p):
        return p, p
    return (today - timedelta(days=7)).isoformat(), today.isoformat()


def _format_avito_metrics(data: dict) -> str:
    totals = data.get("totals") or {}
    series = data.get("series") or []
    lines = [
        f"Период: {data.get('date_from')} — {data.get('date_to')}",
        f"Объявлений в выборке: {data.get('items_count', 0)}",
        f"Итого просмотры: {totals.get('views', 0)}, избранное: {totals.get('favorites', 0)}, "
        f"контакты: {totals.get('contacts', 0)}, расход: {totals.get('spend', 0)} ₽",
    ]
    if series:
        lines.append("По дням:")
        for row in series:
            lines.append(
                f"  {row.get('date')}: просмотры {row.get('views', 0)}, "
                f"контакты {row.get('contacts', 0)}, избранное {row.get('favorites', 0)}"
            )
    rows = data.get("rows") or []
    if rows:
        lines.append("Топ объявлений (по просмотрам за период):")
        by_item: dict[str, dict] = {}
        for r in rows:
            iid = str(r.get("item_id"))
            if iid not in by_item:
                by_item[iid] = {
                    "title": r.get("title") or iid,
                    "views": 0,
                    "contacts": 0,
                }
            by_item[iid]["views"] += int(r.get("views") or 0)
            by_item[iid]["contacts"] += int(r.get("contacts") or 0)
        top = sorted(by_item.values(), key=lambda x: x["views"], reverse=True)[:8]
        for t in top:
            lines.append(
                f"  — {t['title'][:80]}: просмотры {t['views']}, контакты {t['contacts']}"
            )
    if not rows and not series:
        lines.append(
            "В SQLite пока нет строк. Вызовите fetch_and_save_avito_metrics (нужны ключи Авито в настройках)."
        )
    return "\n".join(lines)


def execute_tool(call: dict[str, Any]) -> str:
    from modules.agent import get_runtime

    name = call["tool"]
    args = call.get("arguments") or {}
    rt = get_runtime()

    if name == "memory_save_cell":
        cell_key = str(args.get("cell_key") or "").strip()
        content = str(args.get("content") or "").strip()
        if not cell_key or not content:
            return "Ошибка: укажите cell_key и content для memory_save_cell."
        from modules import jarvis_db
        from modules.agent import AgentMode, get_mode

        jarvis_db.init_db()
        raw_mode = args.get("mode_code")
        mode_code: str | None
        if raw_mode is None or str(raw_mode).strip() in ("", "null", "standard"):
            m = get_mode()
            mode_code = None if m == AgentMode.STANDARD else m.value
        else:
            mode_code = str(raw_mode).strip()
        jarvis_db.set_cell(
            mode_code=mode_code,
            namespace=str(args.get("namespace") or "default").strip() or "default",
            cell_key=cell_key,
            content=content,
            source="agent",
        )
        rt.log("memory", f"Ячейка «{cell_key}» сохранена")
        scope = "все чаты (стандарт)" if mode_code is None else f"все чаты режима «{mode_code}»"
        return (
            f"Сохранено в jarvis.db → ячейка «{cell_key}» ({scope}). "
            "Факт будет подмешиваться в следующих ответах."
        )

    if name == "exchange_rate":
        query = str(args.get("query") or "").strip()
        from modules.exchange_rates import format_exchange_rate_reply

        rt.status = "IDLE"
        rt.log("exchange", f"Курс ЦБ: «{query[:60]}»")
        return format_exchange_rate_reply(query or "курс доллара")

    if name == "web_search":
        query = str(args.get("query") or "").strip()
        if not query:
            return "Ошибка: укажите arguments.query для web_search."
        rt.status = "Searching Web..."
        rt.log("web.search", f"DuckDuckGo: «{query[:60]}»…")
        from modules.web_search import search_web_text

        text = search_web_text(query, max_results=5)
        rt.log("web.search", "Поиск завершён")
        rt.status = "IDLE"
        return text

    if name == "web_research":
        query = str(args.get("query") or "").strip()
        if not query:
            return "Ошибка: укажите arguments.query для web_research."
        max_pages = int(args.get("max_pages") or 10)
        rt.status = "Searching Web..."
        rt.log("web.research", f"Стереотипы + Google, до {max_pages} стр.: «{query[:60]}»…")
        from modules.web_research import research_web_query

        try:
            from store import load_settings

            settings = load_settings()
            ds_key = (settings.get("deepseek_key") or "").strip()
            model = (settings.get("default_model") or "deepseek-chat").strip()
        except Exception:
            ds_key, model = "", "deepseek-chat"
        text = research_web_query(
            query,
            max_pages=max_pages,
            deepseek_key=ds_key,
            model=model,
        )
        rt.log("web.research", "Выжимка готова")
        rt.status = "IDLE"
        return text

    if name == "fetch_url":
        url = str(args.get("url") or "").strip()
        if not url:
            return "Ошибка: укажите arguments.url для fetch_url."
        rt.status = "Searching Web..."
        rt.log("web.fetch", f"Chromium {url[:80]}…")
        from modules.web_search import fetch_url_text

        text = fetch_url_text(url)
        rt.log("web.fetch", "Загрузка завершена")
        rt.status = "IDLE"
        return text

    if name == "fetch_and_save_avito_metrics":
        days = int(args.get("days") or 3)
        days = max(1, min(days, 14))
        rt.log("avito", f"Синхронизация метрик за {days} дн.…")
        from modules import avito as avito_module

        results: list[dict] = []
        for offset in range(1, days + 1):
            target = date.today() - timedelta(days=offset)
            results.append(avito_module.sync_day(target))
        ok = sum(1 for r in results if r.get("ok"))
        lines = [f"Синхронизировано дней: {ok}/{days}"]
        for r in results:
            if r.get("ok"):
                lines.append(f"  ✓ {r.get('date')}: {r.get('items', 0)} объявлений")
            else:
                lines.append(f"  ✗ {r.get('date', '?')}: {r.get('error', 'ошибка')}")
        return "\n".join(lines)

    if name == "get_stored_metrics":
        period = str(args.get("period") or "week")
        date_from, date_to = _parse_period(period)
        rt.log("avito", f"Чтение SQLite avito_stats {date_from}…{date_to}")
        from modules import avito as avito_module

        data = avito_module.get_metrics(date_from, date_to)
        return _format_avito_metrics(data)

    if name == "sync_avito_chats":
        from modules.avito_chat_analytics import sync_chats_for_period

        days = int(args.get("days") or 30)
        max_chats = int(args.get("max_chats") or 500)
        mpc = int(args.get("messages_per_chat") or 500)
        rt.log("avito", f"Синхронизация чатов за {days} дн.")
        result = sync_chats_for_period(
            days=days, max_chats=max_chats, messages_per_chat=mpc
        )
        hint = result.get("hint") or ""
        return (
            f"Чаты синхронизированы: {result.get('chats_saved', 0)} чатов, "
            f"{result.get('messages_saved', 0)} сообщений. "
            f"Аккаунт: {result.get('account_name', '')} ({result.get('user_id', '')}). "
            f"{hint}"
        ).strip()

    if name == "get_avito_chats":
        from modules.avito_messenger import format_chats_summary, get_chats_from_db

        limit = int(args.get("limit") or 30)
        search = str(args.get("search") or "").strip() or None
        data = get_chats_from_db(limit=limit, search=search)
        if not data.get("chats"):
            return format_chats_summary(limit=5)
        lines = [format_chats_summary(limit=3), "", f"Найдено чатов: {data.get('total', 0)}"]
        for c in data["chats"]:
            lines.append(
                f"• id={c.get('chat_id')} | {c.get('counterpart_name')} | "
                f"{(c.get('item_title') or '')[:50]} | {(c.get('last_message_text') or '')[:60]}"
            )
        return "\n".join(lines)

    if name == "get_avito_chat_messages":
        from modules.avito_messenger import get_messages_from_db

        chat_id = str(args.get("chat_id") or args.get("id") or "").strip()
        if not chat_id:
            return "Ошибка: укажите chat_id для get_avito_chat_messages."
        limit = int(args.get("limit") or 50)
        data = get_messages_from_db(chat_id, limit=limit)
        msgs = data.get("messages") or []
        if not msgs:
            return f"В архиве нет сообщений для чата {chat_id}. Сначала sync_avito_chats."
        lines = [f"Чат {chat_id}: {data.get('total', 0)} сообщений в архиве", ""]
        for m in msgs[-limit:]:
            who = "→" if m.get("direction") == "out" else "←"
            lines.append(
                f"{who} [{m.get('created_at', '')[:19]}] {(m.get('text') or '')[:200]}"
            )
        return "\n".join(lines)

    if name == "probe_avito_api":
        from modules.avito_messenger import probe_api

        rt.log("avito", "Диагностика API")
        p = probe_api()
        lines = ["=== Диагностика API Авито ==="]
        lines.append(f"Ключи: {'OK' if p.get('credentials') else 'нет'}")
        prof = p.get("profile") or {}
        lines.append(
            f"Профиль: {'OK' if prof.get('ok') else 'нет'} {prof.get('error', '')}"
        )
        msg = p.get("messenger_chats") or {}
        lines.append(
            f"Messenger (чаты): {'OK' if msg.get('ok') else 'нет'} {msg.get('error', '')}"
        )
        if msg.get("api_path"):
            lines.append(f"  endpoint: {msg['api_path']}")
        st = p.get("stats") or {}
        lines.append(f"Статистика: {'OK' if st.get('ok') else 'нет'} {st.get('error', '')}")
        arch = p.get("archive") or {}
        lines.append(
            f"Локальный архив: {arch.get('chats_in_db', 0)} чатов, "
            f"{arch.get('messages_in_db', 0)} сообщений"
        )
        return "\n".join(lines)

    if name == "sync_avito_chats_period":
        from modules.avito_chat_analytics import sync_chats_for_period

        days = int(args.get("days") or 30)
        max_chats = int(args.get("max_chats") or 500)
        mpc = int(args.get("messages_per_chat") or 500)
        rt.log("avito", f"Синхронизация чатов за {days} дн.")
        r = sync_chats_for_period(days=days, max_chats=max_chats, messages_per_chat=mpc)
        return (
            f"За {days} дн.: {r.get('chats_saved', 0)} чатов, "
            f"{r.get('messages_saved', 0)} сообщений в accountant.db."
        )

    if name == "analyze_avito_chats":
        from modules.avito_chat_analytics import analyze_chats, format_analysis_report

        days = int(args.get("days") or 30)
        chat_id = str(args.get("chat_id") or "").strip() or None
        rt.log("avito", f"Анализ чатов за {days} дн.")
        data = analyze_chats(days=days, chat_id=chat_id)
        return format_analysis_report(data)

    if name == "run_avito_chat_pipeline":
        from modules.avito_chat_analytics import run_full_pipeline

        days = int(args.get("days") or 30)
        rt.log("avito", f"Пайплайн чатов за {days} дн.")
        r = run_full_pipeline(days=days)
        return r.get("report", "Готово.")

    if name == "purge_avito_chat":
        from modules.avito_chat_analytics import purge_chat_archive

        chat_id = str(args.get("chat_id") or args.get("id") or "").strip()
        if not chat_id:
            return "Ошибка: укажите chat_id для purge_avito_chat."
        rt.log("avito", f"Очистка архива чата {chat_id}")
        r = purge_chat_archive(chat_id)
        return (
            f"Удалено: {r.get('messages_deleted', 0)} сообщений, "
            f"карточка чата: {'да' if r.get('chat_deleted') else 'нет'}."
        )

    if name == "sync_all_avito_data":
        from modules.avito_api import sync_all_avito_data

        force = bool(args.get("force"))
        stats_days = int(args.get("stats_days") or 14)
        max_chats = int(args.get("max_chats") or 500)
        rt.log("avito", "Полная синхронизация API → SQLite")
        r = sync_all_avito_data(
            stats_days=max(1, min(stats_days, 30)),
            max_chats=max(10, min(max_chats, 800)),
            force=force,
        )
        return json.dumps(r, ensure_ascii=False, indent=2)[:8000]

    if name == "execute_local_sql_query":
        from modules.avito_storage import execute_local_sql_query

        query = str(args.get("query") or "")
        max_rows = int(args.get("max_rows") or 100)
        rt.log("avito", "SQL SELECT к локальной БД")
        r = execute_local_sql_query(query, max_rows=max_rows)
        if not r.get("ok"):
            return f"SQL ошибка: {r.get('error')}"
        rows = r.get("rows") or []
        if not rows:
            return "Запрос выполнен: 0 строк."
        return json.dumps(rows, ensure_ascii=False, indent=2)[:8000]

    if name == "avito_press_button":
        from modules.avito_api import avito_press_button

        action_type = str(args.get("action_type") or "").strip().lower().replace("-", "_")
        if action_type in ("send_message", "message", "reply", "write", "send"):
            return (
                "Отправка в чаты Авито отключена. Jarvis только читает и анализирует переписки "
                "(sync_avito_chats, get_avito_chats, avito_mine_hr)."
            )
        action_type = str(args.get("action_type") or "").strip()
        params = dict(args.get("params") or {}) if isinstance(args.get("params"), dict) else {}
        for k in ("chat_id", "text", "item_id", "new_price", "action", "service_type", "service"):
            if k in args and args[k] is not None:
                params[k] = args[k]
        if not action_type and params.get("action"):
            action_type = str(params.pop("action", ""))
        rt.log("avito", f"Действие в кабинете: {action_type}")
        r = avito_press_button(action_type, params)
        rt.last_router_engine = "avito_action"
        rt.last_router_intent = "LOCAL_HELP"
        return json.dumps(r, ensure_ascii=False, indent=2)[:4000]

    if name == "avito_report_stats":
        from modules.avito_skills import report_statistics_markdown

        days = int(args.get("days") or 14)
        rt.log("avito", f"Отчёт статистики за {days} дн.")
        rt.last_router_engine = "avito_stats"
        rt.last_router_intent = "LOCAL_HELP"
        return report_statistics_markdown(days=max(1, min(days, 90)))

    if name == "avito_mine_hr":
        from modules.avito_skills import mine_hr_interviews

        hours = int(args.get("hours") or 48)
        rt.log("avito", f"HR-майнер за {hours} ч")
        r = mine_hr_interviews(hours=max(12, min(hours, 168)))
        rt.last_router_engine = "avito_hr"
        rt.last_router_intent = "LOCAL_HELP"
        return json.dumps(r, ensure_ascii=False, indent=2)

    if name == "avito_audit_listings":
        from modules.avito_skills import audit_listings_markdown

        days = int(args.get("days") or 14)
        rt.log("avito", "Аудит объявлений")
        rt.last_router_engine = "avito_audit"
        rt.last_router_intent = "LOCAL_HELP"
        return audit_listings_markdown(days=max(1, min(days, 90)))

    if name == "avito_list_interviews":
        from modules.avito_skills import list_promised_interviews_markdown

        rt.log("avito", "Список обещаний визита")
        rt.last_router_engine = "avito_hr"
        rt.last_router_intent = "LOCAL_HELP"
        return list_promised_interviews_markdown()

    if name == "ui_get_app_state":
        from modules.ui_control import get_ui_snapshot

        rt.log("ui", "Снимок полей и индикаторов")
        return get_ui_snapshot()

    if name == "ui_set_telegram_field":
        from modules.ui_control import set_telegram_field

        field = str(args.get("field") or "")
        value = str(args.get("value") or "")
        persist = bool(args.get("persist", True))
        return set_telegram_field(field, value, persist=persist)

    if name == "ui_set_avito_field":
        from modules.ui_control import set_avito_field

        field = str(args.get("field") or "")
        value = str(args.get("value") or "")
        persist = bool(args.get("persist", True))
        return set_avito_field(field, value, persist=persist)

    if name == "ui_apply_text_to_connectors":
        from modules.ui_control import parse_and_apply_credentials

        text = str(args.get("text") or "")
        persist = bool(args.get("persist", True))
        return parse_and_apply_credentials(text, persist=persist)

    if name == "ui_click":
        from modules.ui_control import execute_ui_click

        action = str(args.get("action") or "")
        return execute_ui_click(action)

    if name.startswith("ui_mode_"):
        from modules.ui_control import execute_ui_click

        return execute_ui_click(name.replace("ui_", "", 1))

    if name == "telegram_mother_core_status":
        from modules import tg_twin
        from modules.ui_control import get_avito_connector_status_text

        rt.log("telegram", "Статус материнского ядра")
        return (
            "=== Материнское ядро Telegram ===\n"
            + tg_twin.get_mother_core_status_text()
            + "\n\n=== Коннектор Авито (кратко) ===\n"
            + get_avito_connector_status_text()
        )

    if name == "telegram_send_message":
        from modules import tg_twin

        chat_id = args.get("chat_id") or args.get("chat") or ""
        text = str(args.get("text") or args.get("message") or "")
        rt.log("telegram", f"Исходящее → {chat_id}")
        res = tg_twin.send_message_outbound(chat_id, text)
        if res.get("ok"):
            return res.get("message", "Отправлено")
        return f"Ошибка: {res.get('error', 'не удалось отправить')}"

    if name == "save_jarvis_skill_code":
        from modules.chat_assistant import save_jarvis_skill_code as _save

        code = str(args.get("code") or args.get("python_code") or args.get("content") or "")
        rt.log("skills", "Запись jarvis_skills.py")
        result = _save(code)
        status = result.get("status", "error")
        msg = result.get("message", "")
        if status == "success":
            from modules.skills_runtime import reload_jarvis_skills_module

            reload_jarvis_skills_module()
            return f"✅ {msg} Модуль перезагружен — можно вызывать run_jarvis_skill."
        return f"❌ {msg}"

    if name == "jarvis_skills_ping":
        from modules.skills_runtime import reload_jarvis_skills_module

        mod = reload_jarvis_skills_module()
        rt.log("skills", "ping песочницы")
        return mod.CustomSkills.ping_skills()

    if name == "list_jarvis_skills":
        from modules.skills_runtime import list_custom_skill_methods

        rt.log("skills", "список методов")
        methods = list_custom_skill_methods()
        if not methods:
            return "Методов CustomSkills пока нет (кроме служебных)."
        return "Методы CustomSkills:\n" + "\n".join(f"• {m}" for m in methods)

    if name == "run_jarvis_skill":
        from modules.skills_runtime import run_custom_skill

        method = str(args.get("method") or args.get("name") or "").strip()
        if not method:
            return "Ошибка: укажите arguments.method для run_jarvis_skill."
        rt.log("skills", f"вызов CustomSkills.{method}")
        try:
            extra = args.get("chat_id") or args.get("arg") or args.get("value")
            if extra is not None and str(extra).strip():
                return run_custom_skill(method, str(extra).strip())
            return run_custom_skill(method)
        except Exception as e:
            return f"Ошибка вызова {method}: {e}"

    if name == "hf_search":
        from modules.hf_hub_client import search_hub, token_configured

        if not token_configured():
            return "Нет токена HF — положите huggingface.key в backend/config/"
        q = str(args.get("query") or args.get("q") or "")
        repo_type = str(args.get("repo_type") or args.get("type") or "model")
        items = search_hub(q, repo_type=repo_type, limit=int(args.get("limit") or 8))
        if not items:
            return f"По запросу «{q}» на Hugging Face ничего не найдено."
        lines = [f"HF {repo_type} — «{q}»:"]
        for it in items:
            lines.append(
                f"• {it['repo_id']} (↓{it.get('downloads') or '?'}, likes={it.get('likes') or '?'})"
            )
        return "\n".join(lines)

    if name == "hf_download_skill":
        from modules.hf_hub_client import token_configured
        from modules.hf_skills_store import install_skill

        if not token_configured():
            return "Нет токена HF — положите huggingface.key в backend/config/"
        repo_id = str(args.get("repo_id") or args.get("repo") or "")
        rt.log("hf", f"скачивание {repo_id}")
        try:
            manifest = install_skill(
                repo_id,
                repo_type=str(args.get("repo_type") or "model"),
                revision=str(args.get("revision") or "main"),
                filenames=list(args.get("filenames") or []) or None,
                allow_patterns=list(args.get("allow_patterns") or []) or None,
                label=str(args.get("label") or ""),
            )
        except Exception as e:
            return f"Ошибка скачивания HF: {e}"
        return (
            f"✅ Навык установлен: {manifest.get('label')} (id={manifest.get('id')}, "
            f"{manifest.get('integration')}, {manifest.get('size_bytes', 0) // (1024 * 1024)} МБ)"
        )

    if name == "hf_list_skills":
        from modules.hf_skills_store import list_installed

        rt.log("hf", "список навыков")
        items = list_installed()
        if not items:
            return "Установленных навыков HF пока нет. hf_search → hf_download_skill."
        lines = ["Навыки Hugging Face:"]
        for s in items:
            flag = "ВКЛ" if s.get("enabled") else "выкл"
            lines.append(
                f"• [{flag}] {s.get('label') or s.get('repo_id')} — id={s.get('id')}, "
                f"{s.get('integration')}"
            )
        return "\n".join(lines)

    if name == "hf_enable_skill":
        from modules.hf_skills_store import set_enabled

        sid = str(args.get("skill_id") or args.get("id") or "")
        enabled = args.get("enabled")
        if enabled is None:
            enabled = True
        try:
            s = set_enabled(sid, bool(enabled))
        except ValueError as e:
            return str(e)
        return f"Навык {s.get('repo_id')} — {'включён' if s.get('enabled') else 'выключен'}."

    if name in ("image_crop", "image_convert", "image_transparency"):
        from modules import image_tools
        from modules.agent import get_runtime

        rt = get_runtime()
        iid = str(args.get("image_id") or rt.last_chat_image_id or "").strip()
        if not iid:
            return "Нет image_id — сначала прикрепите картинку в чат."
        try:
            if name == "image_crop":
                res = image_tools.crop_image(
                    iid,
                    left=int(args.get("left") or 0),
                    top=int(args.get("top") or 0),
                    right=int(args.get("right") or 0),
                    bottom=int(args.get("bottom") or 0),
                )
            elif name == "image_convert":
                res = image_tools.convert_format(iid, target=str(args.get("format") or "png"))
            else:
                res = image_tools.set_transparency(iid, mode=str(args.get("mode") or "remove"))
            rt.last_chat_image_id = res["id"]
            return (
                f"Готово ({res.get('note')}). Размер {res.get('width')}×{res.get('height')}. "
                f"Покажи в чате:\n{res.get('markdown')}"
            )
        except Exception as e:
            return f"Ошибка обработки изображения: {e}"

    if name == "mail_list_accounts":
        from modules import mail_client

        rt.log("mail", "список ящиков")
        return mail_client.format_accounts_for_agent()

    if name == "mail_list_messages":
        from modules import mail_client

        target = _mail_target_args(args)
        limit = int(args.get("limit") or 20)
        unread_only = bool(args.get("unread_only"))
        if not target["account_id"] and target["slot"] is None and not target["provider"]:
            return "Ошибка: укажите account_id, slot (1–5) или provider (gmail/yandex/icloud/mailru/legacy)."
        rt.log("mail", f"письма {target.get('provider') or target.get('account_id') or target.get('slot')}")
        try:
            data = mail_client.list_messages(
                target["account_id"],
                slot=target["slot"],
                provider=target["provider"],
                folder=target["folder"],
                limit=limit,
                unread_only=unread_only,
            )
        except ValueError as e:
            return str(e)
        return mail_client.format_messages_for_agent(data)

    if name == "mail_get_message":
        from modules import mail_client

        uid = str(args.get("uid") or "").strip()
        if not uid:
            return "Ошибка: укажите uid из mail_list_messages."
        target = _mail_target_args(args)
        if not target["account_id"] and target["slot"] is None and not target["provider"]:
            return "Ошибка: укажите account_id, slot или provider."
        rt.log("mail", f"письмо uid={uid}")
        try:
            data = mail_client.get_message(
                uid,
                target["account_id"],
                slot=target["slot"],
                provider=target["provider"],
                folder=target["folder"],
            )
        except ValueError as e:
            return str(e)
        body = str(data.get("body") or "").strip()
        return (
            f"uid={data.get('uid')} | {data.get('subject')}\n"
            f"От: {data.get('from')}\n"
            f"Дата: {data.get('date')}\n"
            f"Прочитано: {'да' if data.get('seen') else 'нет'}\n\n"
            f"{body or '(пустое тело)'}"
        )

    if name == "mail_mark_read":
        from modules import mail_client

        uid = str(args.get("uid") or "").strip()
        if not uid:
            return "Ошибка: укажите uid."
        target = _mail_target_args(args)
        read = bool(args.get("read", True))
        if not target["account_id"] and target["slot"] is None and not target["provider"]:
            return "Ошибка: укажите account_id, slot или provider."
        rt.log("mail", f"{'read' if read else 'unread'} uid={uid}")
        try:
            res = mail_client.set_read_flag(
                uid,
                read=read,
                account_id=target["account_id"],
                slot=target["slot"],
                provider=target["provider"],
                folder=target["folder"],
            )
        except ValueError as e:
            return str(e)
        return str(res.get("message") or "Готово")

    return f"Неизвестный инструмент: {name}"


_CHAT_ID_RE = re.compile(r"(?:chat[_\s-]?id|чат[_\s-]?id|id чата)\s*[:=]?\s*(-?\d{5,15})", re.I)
_BARE_CHAT_ID_RE = re.compile(r"\b(-?\d{8,15})\b")


def _extract_chat_id(text: str) -> str:
    m = _CHAT_ID_RE.search(text or "")
    if m:
        return m.group(1)
    m = _BARE_CHAT_ID_RE.search(text or "")
    return m.group(1) if m else ""


def _extract_message_text(text: str) -> str:
    t = (text or "").strip()
    for sep in ("—", ":", "»", "->"):
        if sep in t:
            parts = t.split(sep, 1)
            if len(parts) > 1 and len(parts[1].strip()) > 3:
                return parts[1].strip()
    return t


def maybe_auto_tools(
    user_text: str, history: list[dict] | None = None
) -> list[dict[str, Any]]:
    """Подсказки бэкенда: если запрос явно про Авито/поиск — выполнить инструмент до ответа Qwen."""
    low = (user_text or "").lower()
    calls: list[dict[str, Any]] = []
    fetch_url_call: dict[str, Any] | None = None
    from modules.url_page_handler import (
        extract_first_url,
        extract_url_from_context,
        user_wants_page_lookup,
    )

    page_url = extract_first_url(user_text or "")
    if not page_url and user_wants_page_lookup(user_text or "", history):
        from modules.url_page_handler import extract_url_from_context

        page_url = extract_url_from_context(user_text or "", history)
    if page_url:
        fetch_url_call = {
            "tool": "fetch_url",
            "arguments": {"url": page_url},
        }
    if any(
        w in low
        for w in (
            "авито",
            "avito",
            "автоириент",
            "авто ориент",
            "объявлен",
            "просмотр",
            "контакт",
            "отработал",
            "метрик",
            "статистик",
        )
    ):
        from modules.avito_overview_handler import wants_avito_overview

        if wants_avito_overview(user_text, history):
            calls.append({"tool": "probe_avito_api", "arguments": {}})
            if not any(
                w in low for w in ("синхрон", "скачай", "загруз", "выгруз")
            ):
                calls.append({"tool": "get_stored_metrics", "arguments": {"period": "week"}})
        capability_q = any(
            w in low
            for w in (
                "что доступн",
                "что тебе",
                "что теперь",
                "что умеешь",
                "что можешь",
                "какие инструмент",
                "какие возможност",
                "список функ",
                "по api",
                "по апи",
            )
        )
        if capability_q:
            calls.append({"tool": "probe_avito_api", "arguments": {}})
        elif any(w in low for w in ("метрик", "статистик", "просмотр", "контакт", "отработал", "отчёт", "отчет", "ctr")):
            calls.append({"tool": "sync_all_avito_data", "arguments": {"force": False, "stats_days": 14}})
            if any(w in low for w in ("отчёт", "отчет", "ctr", "конверс")):
                calls.append({"tool": "avito_report_stats", "arguments": {"days": 14}})
            elif any(w in low for w in ("недел", "week", "7 дн", "за 7")):
                calls.append({"tool": "get_stored_metrics", "arguments": {"period": "week"}})
            elif any(w in low for w in ("месяц", "month", "30 дн")):
                calls.append({"tool": "get_stored_metrics", "arguments": {"period": "month"}})
            else:
                calls.append({"tool": "get_stored_metrics", "arguments": {"period": "week"}})
        if any(
            w in low
            for w in (
                "обещал прийти",
                "собеседован",
                "кто придёт",
                "кто придет",
                "hr",
                "кандидат",
            )
        ):
            calls.append({"tool": "sync_all_avito_data", "arguments": {}})
            calls.append({"tool": "avito_mine_hr", "arguments": {"hours": 48}})
            calls.append({"tool": "avito_list_interviews", "arguments": {}})
        if any(w in low for w in ("аудит объяв", "слабые объяв", "улучши объяв")):
            calls.append({"tool": "avito_audit_listings", "arguments": {"days": 14}})
        if any(
            w in low
            for w in (
                "обнов",
                "свеж",
                "скачай",
                "синхрон",
                "загруз",
                "выгруз",
                "архив",
                "авториз",
                "сохрани",
            )
        ):
            if any(
                w in low
                for w in ("чат", "переписк", "сообщен", "архив", "мессендж", "соискател")
            ):
                calls.append(
                    {
                        "tool": "sync_avito_chats_period",
                        "arguments": {"days": 30, "max_chats": 500},
                    }
                )
            else:
                calls.append({"tool": "fetch_and_save_avito_metrics", "arguments": {"days": 3}})

    if fetch_url_call:
        q_rest = re.sub(r"https?://\S+", "", user_text).strip()
        if len(q_rest) > 12:
            calls.append({"tool": "web_search", "arguments": {"query": q_rest[:200]}})

    try:
        from modules.exchange_rates import user_wants_exchange_rate

        if user_wants_exchange_rate(user_text):
            calls.append({"tool": "exchange_rate", "arguments": {"query": user_text.strip()[:200]}})
    except Exception:
        pass

    try:
        from modules.web_research import is_web_search_meta_question

        if is_web_search_meta_question(user_text):
            return calls
    except Exception:
        pass

    if any(
        w in low
        for w in (
            "интернет",
            "найди в сети",
            "поиск в сети",
            "duckduckgo",
            "новост",
            "сегодня в интернете",
            "найди ",
            "загугли",
        )
    ) and "авито" not in low:
        if not any(
            w in low
            for w in (
                "можешь ли",
                "умеешь ли",
                "есть ли",
                "есть у тебя",
                "встроенн браузер",
                "просматривать страниц",
            )
        ):
            q = user_text.strip()[:200]
            calls.append({"tool": "web_research", "arguments": {"query": q, "max_pages": 10}})

    remember_m = re.search(
        r"(?:запомни|сохрани в память|запиши в память)\s*[:—\-]\s*(.+)",
        user_text,
        re.I | re.S,
    )
    if remember_m:
        fact = remember_m.group(1).strip()[:4000]
        if len(fact) > 2:
            try:
                from modules.user_preferences import parse_remember_preference, save_preference

                pref = parse_remember_preference(user_text)
                if pref:
                    save_preference(pref)
                    calls.append(
                        {
                            "tool": "memory_save_cell",
                            "arguments": {
                                "cell_key": f"pref_{pref.category}_{pref.slug()}",
                                "content": f"{pref.canonical} ({pref.category})",
                                "namespace": "user_prefs",
                            },
                        }
                    )
                else:
                    key = "шеф_" + re.sub(
                        r"[^a-z0-9а-яё]+", "_", fact[:40].lower()
                    ).strip("_")[:32]
                    key = key or "fact"
                    calls.append(
                        {
                            "tool": "memory_save_cell",
                            "arguments": {"cell_key": key, "content": fact},
                        }
                    )
            except Exception:
                key = "шеф_" + re.sub(r"[^a-z0-9а-яё]+", "_", fact[:40].lower()).strip("_")[
                    :32
                ]
                key = key or "fact"
                calls.append(
                    {
                        "tool": "memory_save_cell",
                        "arguments": {"cell_key": key, "content": fact},
                    }
                )

    from modules.ui_control import _BOT_TOKEN_RE

    if any(
        w in low
        for w in (
            "client id",
            "client_id",
            "client secret",
            "botfather",
            "bot_token",
            "токен бота",
            "developers.avito",
            "подключи авито",
            "ключи авито",
            "credentials",
        )
    ) or _BOT_TOKEN_RE.search(user_text):
        calls.append(
            {
                "tool": "ui_apply_text_to_connectors",
                "arguments": {"text": user_text, "persist": True},
            }
        )

    if any(
        w in low
        for w in (
            "вставь токен",
            "сохрани токен",
            "включи сервер",
            "выключи сервер",
            "включи синхрон",
            "сохрани ключи",
            "заполни поле",
            "измени поле",
            "что в поле",
            "что написано в",
            "какие ключи",
            "покажи поля",
            "состояние полей",
            "что в токене",
            "что в прокси",
            "материнск",
            "mother core",
            "telegram",
            "телеграм",
            "тг бот",
            "botfather",
            "сервер бота",
            "коннектор авито",
            "материнское ядро",
        )
    ):
        calls.append({"tool": "ui_get_app_state", "arguments": {}})

    if any(
        w in low
        for w in (
            "материнск",
            "mother core",
            "telegram",
            "телеграм",
            "тг-бот",
            "тг бот",
            "botfather",
            "сервер бота",
            "polling",
            "bot_logic",
        )
    ) and "отправ" not in low and "напиши" not in low:
        calls.append({"tool": "telegram_mother_core_status", "arguments": {}})

    if any(w in low for w in ("напиши в телеграм", "отправь в телеграм", "send to telegram", "telegram_send")):
        calls.append(
            {
                "tool": "telegram_send_message",
                "arguments": {
                    "chat_id": _extract_chat_id(user_text),
                    "text": _extract_message_text(user_text),
                },
            }
        )

    from modules.text_sanitize import wants_sandbox_write

    if wants_sandbox_write(user_text):
        calls.append({"tool": "jarvis_skills_ping", "arguments": {}})
        calls.append({"tool": "list_jarvis_skills", "arguments": {}})

    if any(
        w in low
        for w in (
            "чат",
            "чаты",
            "переписк",
            "сообщен",
            "соискател",
            "кандидат",
            "отклик",
            "messenger",
            "собеседован",
        )
    ) and any(w in low for w in ("авито", "avito")):
        analyze_q = any(
            w in low
            for w in (
                "анализ",
                "разбор",
                "ключев",
                "фраз",
                "собеседован",
                "адрес",
                "месяц",
                "за 30",
                "выгруз",
                "найди",
                "посчитай",
                "сколько",
                "уточнял",
                "случа",
                "успешн",
            )
        )
        sync_q = any(
            w in low for w in ("синхрон", "скачай", "загруз", "обнов", "получ", "архив", "парс")
        )
        purge_q = any(w in low for w in ("очист", "удал", "закрыл", "закрыт", "после выгруз"))

        if analyze_q and sync_q:
            calls.append({"tool": "run_avito_chat_pipeline", "arguments": {"days": 30}})
        elif analyze_q:
            calls.append({"tool": "sync_avito_chats_period", "arguments": {"days": 30}})
            calls.append({"tool": "analyze_avito_chats", "arguments": {"days": 30}})
        elif sync_q:
            calls.append({"tool": "sync_avito_chats_period", "arguments": {"days": 30}})
        elif purge_q:
            cid = _extract_chat_id(user_text) or ""
            if cid:
                calls.append({"tool": "purge_avito_chat", "arguments": {"chat_id": cid}})
        else:
            calls.append({"tool": "probe_avito_api", "arguments": {}})
            calls.append({"tool": "get_avito_chats", "arguments": {"limit": 30}})

    # Скачать чаты без слова «авито», если в том же диалоге уже обсуждали API Авито
    from modules.avito_sync_handler import wants_avito_chat_sync

    if wants_avito_chat_sync(user_text, history) and not any(
        c.get("tool", "").startswith("sync_avito") for c in calls
    ):
        calls.insert(
            0,
            {"tool": "sync_avito_chats_period", "arguments": {"days": 30, "max_chats": 500}},
        )

    if fetch_url_call:
        calls = [c for c in calls if c.get("tool") != "fetch_url"]
        calls.insert(0, fetch_url_call)
    return calls[:8]


def run_qwen_tool_loop(
    messages: list[dict[str, str]],
    *,
    chat_fn,
    user_text: str = "",
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> tuple[str, int, str]:
    """Цикл tool-calling для Qwen. chat_fn(messages) -> (text, tokens)."""
    total_tokens = 0
    used_tools = False

    for _ in range(max_rounds):
        text, tokens = chat_fn(messages)
        total_tokens += tokens
        call = parse_tool_call(text)
        if not call:
            label = "qwen+tools" if used_tools else "qwen"
            return text, total_tokens, label

        used_tools = True
        from modules.agent import get_runtime

        get_runtime().log("qwen.tool", f"Вызов `{call['tool']}`")
        result = execute_tool(call)
        messages.append({"role": "assistant", "content": text})
        from modules.text_sanitize import followup_brevity_hint

        follow = (
            f"[Результат инструмента {call['tool']}]\n{result}\n\n"
            "Сформируй ответ пользователю на русском. Используй только эти данные, "
            "не выдумывай цифры."
            + followup_brevity_hint(user_text)
        )
        if call["tool"] == "save_jarvis_skill_code":
            follow += (
                "\n\nКод уже записан в jarvis_skills.py. "
                "Ответь Шефу в 1–3 предложениях: что добавлено и имя метода для "
                "run_jarvis_skill. Не дублируй исходный код в чате."
            )
        messages.append({"role": "user", "content": follow})

    text, tokens = chat_fn(messages)
    total_tokens += tokens
    return text, total_tokens, "qwen+tools"

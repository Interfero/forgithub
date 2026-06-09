"""
Запросы «проанализируй авито» — только факты API + SQLite, без выдуманных объявлений с сайта.
"""

from __future__ import annotations

import re
from typing import Any

# Публичный парсинг каталога Avito.ru — не наш сценарий
_PUBLIC_CATALOG = re.compile(
    r"найди\s+на\s+авито|поиск\s+на\s+авито|"
    r"топ[-\s]?\d+|ключев(?:ое|ого)\s+слов|"
    r"сам(?:ые|ых|ая|ое)\s+(?:низк|дешёв)|"
    r"по\s+запросу\s+[«\"]",
    re.I,
)

_OVERVIEW = re.compile(
    r"(?:"
    r"проанализ|анализ|разбер|разбор|сводк|отчёт|отчет|"
    r"провер(?:ь|ить)|статус|статистик|метрик|"
    r"что\s+(?:у|на)\s+(?:меня\s+)?(?:на\s+)?авито|"
    r"как\s+(?:дела|обстоят\s+дела)\s+(?:на\s+)?авито|"
    r"analyze\s+avito"
    r")",
    re.I,
)

_LISTING_SUCCESS = re.compile(
    r"(?:"
    r"(?:насколько|как)\s+(?:успеш|эффектив)|"
    r"успеш(?:ны|ность|н).*(?:объявлен|листинг)|"
    r"(?:объявлен|листинг).*(?:успеш|эффектив|конверс|метрик|статистик|ctr|просмотр|контакт)|"
    r"текущ(?:ий|ем|его|ая)\s+профил.*(?:объявлен|авито|avito)|"
    r"(?:отчёт|отчет|статистик).*(?:объявлен|листинг)"
    r")",
    re.I,
)


def wants_avito_overview(user_text: str, history: list[dict] | None = None) -> bool:
    low = (user_text or "").lower().strip()
    if not low or ("авито" not in low and "avito" not in low):
        return False

    from modules.avito_analyze_handler import wants_avito_chat_analyze
    from modules.avito_sync_handler import wants_avito_chat_sync

    if wants_avito_chat_sync(user_text, history):
        return False
    if wants_avito_chat_analyze(user_text, history):
        return False

    if _OVERVIEW.search(low):
        return True

    # Короткое «авито» / «про авито» без задачи — тоже обзор, не галлюцинации
    if len(low) < 48 and re.match(
        r"^(?:про\s+)?(?:авито|avito)\s*[.!?]?\s*$", low, re.I
    ):
        return True

    return False


def is_public_avito_catalog_request(user_text: str) -> bool:
    low = (user_text or "").lower()
    if "авито" not in low and "avito" not in low:
        return False
    if any(w in low for w in ("мой кабинет", "мои объяв", "мой аккаунт", "по api", "коннектор")):
        return False
    return bool(_PUBLIC_CATALOG.search(low))


def build_avito_overview_reply(user_text: str) -> str:
    """Ответ по probe API + локальной БД; конкретные следующие шаги."""
    if is_public_avito_catalog_request(user_text):
        return _public_catalog_redirect()

    from modules.avito import _creds_ok, _load_config, get_config, get_metrics
    from modules.avito_messenger import archive_stats, probe_api
    from modules.avito_storage import init_avito_storage, storage_summary

    init_avito_storage()

    if not _creds_ok(_load_config()):
        return _no_credentials_reply()

    cfg = get_config()
    probe = probe_api()
    storage = storage_summary()
    arch = archive_stats()

    prof_ok = bool((probe.get("profile") or {}).get("ok"))
    msg_ok = bool((probe.get("messenger_chats") or {}).get("ok"))
    stats_ok = bool((probe.get("stats") or {}).get("ok"))

    stats_rows = int(storage.get("stats_rows") or 0)
    items_count = int(storage.get("items") or 0)
    chats_n = int(arch.get("chats_in_db") or 0)
    msgs_n = int(arch.get("messages_in_db") or 0)
    inbound_n = int(storage.get("inbound_leads") or 0)

    sync_note = ""
    if stats_ok and stats_rows == 0:
        sync_note = (
            "В SQLite пока нет метрик. Для загрузки с API напишите "
            "«**синхронизируй авито**» — в чате будет прогресс, без обрыва связи."
        )
    elif stats_ok and items_count == 0 and stats_rows > 0:
        sync_note = (
            "Метрики в базе есть, каталог объявлений пуст — выполните «**синхронизируй авито**»."
        )

    from modules.avito_report_html import build_avito_overview_html

    return build_avito_overview_html(
        cfg=cfg,
        probe=probe,
        storage=storage,
        arch=arch,
        sync_note=sync_note,
        metrics_days=7,
    )


def _metrics_preview_block(*, days: int = 7) -> str:
    from datetime import date, timedelta

    from modules.avito_storage import stats_aggregate

    date_to = date.today().isoformat()
    date_from = (date.today() - timedelta(days=days)).isoformat()
    agg = stats_aggregate(date_from, date_to)
    t = agg.get("totals") or {}
    lines = [
        f"### Метрики за {days} дней (из `avito_stats`)",
        "",
        f"- **Просмотры:** {t.get('views', 0)}",
        f"- **Контакты (API):** {t.get('contacts', 0)}",
        f"- **В избранное:** {t.get('favorites', 0)}",
        f"- **Отклики (соискатель написал первым):** {t.get('inbound_leads', 0)}",
        f"- **Средний CTR:** {t.get('avg_ctr_pct', 0)}%",
        "",
        "| День | Просмотры | Контакты | Избранное | Отклики |",
        "|------|-----------|----------|-----------|---------|",
    ]
    for d in agg.get("daily") or []:
        lines.append(
            f"| {d.get('date')} | {d.get('views', 0)} | {d.get('contacts', 0)} | "
            f"{d.get('favorites', 0)} | {d.get('inbound_leads', 0)} |"
        )
    top = (agg.get("items") or [])[:5]
    if top:
        lines.extend(["", "**Топ объявлений по просмотрам:**"])
        for it in top:
            lines.append(
                f"- {it.get('title') or it.get('item_id')} — просмотры **{it.get('views', 0)}**, "
                f"контакты **{it.get('contacts', 0)}**, избранное **{it.get('favorites', 0)}**, "
                f"отклики **{it.get('inbound_leads', 0)}**"
            )
    return "\n".join(lines)


def _avito_data_catalog_block(*, stats_ok: bool, chats_n: int) -> str:
    """Какие данные Jarvis умеет хранить и как их включить."""
    lines = [
        "### Какие данные Jarvis ведёт по Авито",
        "",
        "| Данные | Таблица SQLite | Источник API | Как обновить |",
        "|--------|----------------|--------------|--------------|",
        "| Просмотры / контакты / избранное по дням и объявлениям | `avito_stats` | POST `/stats/v1/.../items` | «синхронизируй метрики авито» |",
        "| Каталог объявлений (id, url, статус) | `avito_items` | GET `/core/v1/.../items/{id}/` | вместе с синхронизацией |",
        "| Чаты и сообщения | `avito_chats`, `avito_messages` | Messenger API | «скачай чаты авито» |",
        "| Отклик = соискатель написал первым | `avito_inbound_leads` | анализ архива чатов | после загрузки чатов |",
        "| HR: обещали прийти | `extracted_interviews` | LLM по чатам | «кто обещал прийти» |",
        "",
        "**Права в [developers.avito.ru](https://developers.avito.ru):**",
        "- `stats:read` — статистика (обязательно для просмотров);",
        "- `items:info` — карточки объявлений;",
        "- `messenger:read` — только **чтение** чатов (отправка в Jarvis отключена);",
        "- для цены/статуса — отдельные scope на изменение объявлений.",
    ]
    if not stats_ok:
        lines.append("")
        lines.append("⚠️ Сейчас **stats:read** не подтверждён — включите в приложении и пересохраните ключи.")
    if chats_n == 0:
        lines.append("")
        lines.append("💬 Чатов в базе нет — отклики «написал первым» появятся после «**скачай чаты авито**».")
    return "\n".join(lines)


def _sync_stats_and_items_worker() -> list[str]:
    from modules.avito_api import fetch_and_sync_items, fetch_and_sync_stats
    from modules.avito_storage import sync_inbound_leads_from_messages

    parts: list[str] = []
    sr = fetch_and_sync_stats(period_days=14)
    parts.append(f"строк статистики: **{sr.get('rows_upserted', 0)}**")
    ir = fetch_and_sync_items()
    parts.append(f"каталог объявлений: **{ir.get('items_saved', 0)}** шт.")
    inbound = sync_inbound_leads_from_messages()
    parts.append(f"откликов «соискатель написал первым»: **{inbound.get('count', 0)}**")
    return parts


def _try_pull_stats_and_items(*, timeout_sec: float = 28.0) -> str:
    """При обзоре: если API stats OK, а SQLite пуст — короткая синхронизация (с таймаутом)."""
    import concurrent.futures

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_sync_stats_and_items_worker)
            parts = fut.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError:
        return (
            "**Синхронизация:** не уложилась в лимит времени — напишите "
            "«**синхронизируй авито**» (полная загрузка с прогрессом в чате)."
        )
    except Exception as e:
        return f"**Синхронизация:** ошибка ({str(e)[:120]})."
    if not parts:
        return ""
    return "**Подтянул с API сейчас:** " + ", ".join(parts) + "."


def _no_credentials_reply() -> str:
    return (
        "## Авито: API не подключён\n\n"
        "**Данных нет.** В коннекторе Авито (сайдбар слева) не указаны **Client ID** и **Client Secret** "
        "с [developers.avito.ru](https://developers.avito.ru).\n\n"
        "### Что Jarvis реально умеет (после ключей)\n"
        "- Синхронизировать **ваши** объявления, статистику и чаты в SQLite\n"
        "- Отчёт CTR и аудит слабых объявлений по **вашим** цифрам\n"
        "- HR: кто обещал прийти (из **ваших** переписок)\n"
        "- Сменить цену/статус объявления (если права API; **без** отправки сообщений в чаты)\n\n"
        "**Сделайте:** откройте коннектор Авито → вставьте ключи → «**синхронизируй авито**»."
    )


def _public_catalog_redirect() -> str:
    return (
        "## Публичный поиск Avito — не поддерживается\n\n"
        "Jarvis **не сканирует** публичный каталог avito.ru и не выдаёт выдуманные «топ-N объявлений». "
        "Это была бы галлюцинация или несанкционированный парсинг.\n\n"
        "Работаем только с **вашим кабинетом** через официальный API.\n\n"
        "Напишите: **«проанализируй авито»** или **«синхронизируй авито»** — покажу статус API и ваши данные из SQLite."
    )


def _concrete_actions(*, has_chats: bool) -> list[str]:
    actions = [
        "",
        "### Что можно сделать дальше (скажите в чате)",
        "- «**Синхронизируй авито**» — полное обновление API → SQLite",
        "- «**Отчёт по статистике авито за 2 недели**» — CTR из базы",
        "- «**Аудит объявлений авито**» — слабые по конверсии",
    ]
    if has_chats:
        actions.extend(
            [
                "- «**Кто обещал прийти на собеседование**» — HR из чатов",
                "- «**Покажи чаты авито**» — список из архива",
            ]
        )
    else:
        actions.append("- «**Скачай чаты авито**» — архив Messenger")
    return actions


def wants_avito_listing_success(
    user_text: str, history: list[dict] | None = None
) -> bool:
    """«Насколько успешны объявления» — локальные метрики, не DeepSeek."""
    low = (user_text or "").lower().strip()
    if not low:
        return False

    from modules.avito_sync_handler import _history_mentions_avito

    if "авито" in low or "avito" in low:
        if any(
            w in low
            for w in (
                "успеш",
                "метрик",
                "статистик",
                "конверс",
                "ctr",
                "просмотр",
                "эффектив",
                "отчёт",
                "отчет",
                "объявлен",
            )
        ):
            return True

    if not _LISTING_SUCCESS.search(low):
        return False

    if any(w in low for w in ("авито", "avito", "профил", "кабинет", "мои объяв")):
        return True
    if history and _history_mentions_avito(history):
        return True

    try:
        from modules.agent import AgentMode, get_mode

        if get_mode() == AgentMode.MARKETER:
            return True
    except Exception:
        pass

    return False


def build_avito_listing_success_reply(user_text: str) -> str:
    """Отчёт по успешности объявлений из SQLite + API."""
    from modules.avito import _creds_ok, _load_config
    from modules.avito_skills import report_statistics_markdown
    from modules.avito_storage import init_avito_storage, storage_summary

    init_avito_storage()
    if not _creds_ok(_load_config()):
        return _no_credentials_reply()

    storage = storage_summary()
    stats_rows = int(storage.get("stats_rows") or 0)
    if stats_rows == 0:
        sync_hint = _try_pull_stats_and_items(timeout_sec=20.0)
        if sync_hint and "Подтянул" in sync_hint:
            storage = storage_summary()

    parts = [
        "## Успешность объявлений в вашем профиле",
        "",
        "Только **ваш кабинет** Avito (API + SQLite), без выдуманных объявлений с сайта.",
        "",
        report_statistics_markdown(days=14),
        "",
        _listing_success_verdict(days=14),
    ]
    parts.extend(
        _concrete_actions(has_chats=int(storage.get("chats") or 0) > 0)
    )
    parts.extend(
        [
            "",
            "> Цифры из вашей базы. Для обновления: «**синхронизируй авито**».",
        ]
    )
    return "\n".join(parts)


def _listing_success_verdict(*, days: int = 14) -> str:
    from datetime import date, timedelta

    from modules.avito_storage import stats_aggregate

    date_to = date.today().isoformat()
    date_from = (date.today() - timedelta(days=days)).isoformat()
    agg = stats_aggregate(date_from, date_to)
    t = agg.get("totals") or {}
    views = int(t.get("views") or 0)
    contacts = int(t.get("contacts") or 0)
    ctr = float(t.get("avg_ctr_pct") or 0)

    if views == 0:
        return (
            "### Итог\n\n"
            "За период **нет просмотров** в базе. Напишите «**синхронизируй метрики авито**» "
            "или проверьте, что объявления активны в кабинете."
        )

    lines = ["### Итог", ""]
    if ctr >= 5:
        lines.append(
            f"Средний CTR **{ctr}%** — **хороший** показатель (типично для Avito 2–5%)."
        )
    elif ctr >= 2:
        lines.append(
            f"Средний CTR **{ctr}%** — **средний** уровень; есть потенциал для роста."
        )
    else:
        lines.append(
            f"Средний CTR **{ctr}%** — **ниже среднего**; стоит доработать заголовки, фото и цены."
        )
    lines.append(
        f"За **{days}** дней: **{views}** просмотров → **{contacts}** контактов."
    )
    return "\n".join(lines)


def try_handle_avito_listing_success(
    user_text: str,
    history: list[dict] | None = None,
) -> tuple[bool, str]:
    if not wants_avito_listing_success(user_text, history):
        return False, ""
    return True, build_avito_listing_success_reply(user_text)


def try_handle_avito_overview(
    user_text: str,
    history: list[dict] | None = None,
) -> tuple[bool, str]:
    if not wants_avito_overview(user_text, history):
        return False, ""
    return True, build_avito_overview_reply(user_text)


# --- Санитайзер: выдуманные объявления ---

_FAKE_LISTING_BLOCK = re.compile(
    r"(?:"
    r"марка\s+и\s+модель\s*:|"
    r"топ[-\s]?\d+\s+объявлен|"
    r"ключев(?:ому|ое)\s+слов(?:у|о)\s+[«\"]|"
    r"вот\s+результаты\s+для\s+ключев"
    r")",
    re.I,
)


def looks_like_hallucinated_avito_catalog(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    if _FAKE_LISTING_BLOCK.search(s):
        return True
    if s.lower().count("цена:") >= 2 and re.search(r"руб\.?", s, re.I):
        return True
    return False

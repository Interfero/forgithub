"""
HTML-отчёт «проанализируй авито» — структурированные блоки с рамками для чата.
"""

from __future__ import annotations

import html
from datetime import date, datetime, timedelta, timezone
from typing import Any

_AVITO_REPORT_MARKER = "<!-- jarvis-avito-report -->"


def is_avito_report_message(content: str) -> bool:
    return _AVITO_REPORT_MARKER in (content or "")


def _esc(text: str, limit: int = 500) -> str:
    s = html.escape((text or "—").replace("\n", " ").strip())
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


def _icon(ok: bool | None) -> str:
    if ok is True:
        return "🟢"
    if ok is False:
        return "🔴"
    return "🟡"


def _box(title: str, body_html: str, *, variant: str = "") -> str:
    cls = f"ja-box {variant}".strip()
    return (
        f'<section class="ja-section">'
        f'<div class="{cls}">'
        f'<h3 class="ja-section-title">{html.escape(title)}</h3>'
        f"{body_html}"
        "</div></section>"
    )


def _kv_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><td class=\"ja-k\">{_esc(k, 80)}</td><td class=\"ja-v\">{v}</td></tr>"
        for k, v in rows
    )
    return (
        '<table class="ja-table ja-kv"><tbody>'
        f"{body}</tbody></table>"
    )


def _metrics_table(daily: list[dict[str, Any]]) -> str:
    if not daily:
        return "<p class=\"ja-muted\">Нет строк за период — нужна синхронизация метрик.</p>"
    head = (
        "<thead><tr>"
        "<th>День</th><th>Просмотры</th><th>Контакты</th>"
        "<th>Избранное</th><th>Отклики¹</th>"
        "</tr></thead>"
    )
    rows = []
    for d in daily:
        rows.append(
            "<tr>"
            f"<td>{_esc(str(d.get('date') or ''), 12)}</td>"
            f"<td>{int(d.get('views') or 0)}</td>"
            f"<td>{int(d.get('contacts') or 0)}</td>"
            f"<td>{int(d.get('favorites') or 0)}</td>"
            f"<td>{int(d.get('inbound_leads') or 0)}</td>"
            "</tr>"
        )
    foot = (
        '<p class="ja-footnote">¹ Отклик — соискатель написал первым (из архива чатов Messenger).</p>'
    )
    return (
        f'<table class="ja-table">{head}<tbody>{"".join(rows)}</tbody></table>{foot}'
    )


def _top_items_table(items: list[dict[str, Any]], *, limit: int = 8) -> str:
    if not items:
        return "<p class=\"ja-muted\">Нет агрегированных данных по объявлениям.</p>"
    head = (
        "<thead><tr><th>Объявление</th><th>Просмотры</th>"
        "<th>Контакты</th><th>CTR</th></tr></thead>"
    )
    rows = []
    for it in items[:limit]:
        title = _esc(str(it.get("title") or it.get("item_id") or "—"), 56)
        rows.append(
            "<tr>"
            f"<td>{title}</td>"
            f"<td>{int(it.get('views') or 0)}</td>"
            f"<td>{int(it.get('contacts') or 0)}</td>"
            f"<td>{float(it.get('ctr_pct') or 0)}%</td>"
            "</tr>"
        )
    return f'<table class="ja-table">{head}<tbody>{"".join(rows)}</tbody></table>'


def build_profile_recommendations(ctx: dict[str, Any]) -> list[tuple[str, str]]:
    """Рекомендации по улучшению профиля (только факты из API + SQLite)."""
    recs: list[tuple[str, str]] = []

    if not ctx.get("stats_ok"):
        recs.append(
            (
                "Права API",
                "На developers.avito.ru включите право stats:read и пересохраните ключи в коннекторе Авито.",
            )
        )
    if not ctx.get("msg_ok"):
        recs.append(
            (
                "Messenger",
                "Подключите messenger:read — без него не будет архива чатов и откликов «написал первым».",
            )
        )

    stats_rows = int(ctx.get("stats_rows") or 0)
    items_count = int(ctx.get("items_count") or 0)
    if stats_rows == 0:
        recs.append(
            (
                "Синхронизация",
                "Напишите в чате «синхронизируй авито» — подтяну просмотры, контакты и избранное по дням в SQLite.",
            )
        )
    elif items_count == 0:
        recs.append(
            (
                "Каталог",
                "Метрики есть, каталог объявлений пуст — повторите синхронизацию для привязки id к заголовкам.",
            )
        )

    views = int(ctx.get("views_7d") or 0)
    contacts = int(ctx.get("contacts_7d") or 0)
    favorites = int(ctx.get("favorites_7d") or 0)
    ctr = float(ctx.get("ctr_7d") or 0)
    inbound = int(ctx.get("inbound_n") or 0)
    chats_n = int(ctx.get("chats_n") or 0)

    if views > 30 and ctr < 2.0:
        recs.append(
            (
                "Конверсия",
                f"CTR {ctr}% при {views} просмотрах за 7 дней — ниже типичного (2–5%). "
                "Усильте первое фото, заголовок с выгодой и цену в начале описания.",
            )
        )
    elif views > 20 and ctr >= 5.0:
        recs.append(
            (
                "Конверсия",
                f"CTR {ctr}% — сильный показатель. Масштабируйте: продвижение x2/x5 на объявления с лучшим CTR.",
            )
        )

    if views > 50 and favorites < max(3, views // 40):
        recs.append(
            (
                "Избранное",
                "Мало добавлений в избранное при заметных просмотрах — добавьте 6–10 фото, "
                "короткое видео или блок «почему выгодно» в начале описания.",
            )
        )

    if contacts > 5 and inbound == 0 and chats_n > 0:
        recs.append(
            (
                "Отклики",
                "Контакты по API есть, но в чатах нет диалогов «соискатель написал первым». "
                "Проверьте, отвечаете ли вы быстрее автоприглашением — это снижает инициативные сообщения.",
            )
        )
    elif chats_n == 0 and contacts > 0:
        recs.append(
            (
                "Чаты",
                "Скачайте чаты авито в чате — для HR-анализа и подсчёта откликов по переписке.",
            )
        )

    weak = ctx.get("weak_items") or []
    for it in weak[:3]:
        title = str(it.get("title") or it.get("item_id") or "объявление")[:80]
        ctr_i = float(it.get("ctr_pct") or 0)
        recs.append(
            (
                f"Слабое объявление",
                f"{title} — CTR {ctr_i}%. "
                "Перепишите заголовок, обновите фото, уточните условия и призыв к действию.",
            )
        )

    if not recs:
        recs.append(
            (
                "Стабильно",
                "Критичных проблем по данным API не видно. "
                "Для динамики — «отчёт по статистике авито за 2 недели» или «аудит объявлений».",
            )
        )

    return recs[:8]


def _recommendations_html(recs: list[tuple[str, str]]) -> str:
    items = []
    for title, body in recs:
        items.append(
            f'<li class="ja-rec-item">'
            f'<strong class="ja-rec-title">{_esc(title, 64)}</strong>'
            f'<span class="ja-rec-body">{_esc(body, 400)}</span>'
            f"</li>"
        )
    return f'<ol class="ja-rec-list">{"".join(items)}</ol>'


def build_avito_overview_html(
    *,
    cfg: dict[str, Any],
    probe: dict[str, Any],
    storage: dict[str, Any],
    arch: dict[str, Any],
    sync_note: str = "",
    metrics_days: int = 7,
) -> str:
    from modules.avito_storage import stats_aggregate, items_with_stats

    prof_ok = bool((probe.get("profile") or {}).get("ok"))
    msg_ok = bool((probe.get("messenger_chats") or {}).get("ok"))
    stats_ok = bool((probe.get("stats") or {}).get("ok"))

    stats_rows = int(storage.get("stats_rows") or 0)
    items_count = int(storage.get("items") or 0)
    chats_n = int(arch.get("chats_in_db") or 0)
    msgs_n = int(arch.get("messages_in_db") or 0)
    inbound_n = int(storage.get("inbound_leads") or 0)

    date_to = date.today().isoformat()
    date_from = (date.today() - timedelta(days=metrics_days)).isoformat()
    agg = stats_aggregate(date_from, date_to) if stats_rows > 0 else {"totals": {}, "daily": [], "items": []}
    t = agg.get("totals") or {}

    weak_items: list[dict[str, Any]] = []
    if stats_rows > 0:
        all_items = items_with_stats(date_from, date_to)
        ctrs = [float(x.get("ctr_pct") or 0) for x in all_items if int(x.get("views") or 0) > 15]
        avg_ctr = sum(ctrs) / len(ctrs) if ctrs else 0.0
        weak_items = [
            x
            for x in all_items
            if int(x.get("views") or 0) > 20
            and float(x.get("ctr_pct") or 0) < avg_ctr * 0.65
        ]
        weak_items.sort(key=lambda x: float(x.get("ctr_pct") or 0))

    rec_ctx = {
        "stats_ok": stats_ok,
        "msg_ok": msg_ok,
        "stats_rows": stats_rows,
        "items_count": items_count,
        "views_7d": int(t.get("views") or 0),
        "contacts_7d": int(t.get("contacts") or 0),
        "favorites_7d": int(t.get("favorites") or 0),
        "ctr_7d": float(t.get("avg_ctr_pct") or 0),
        "inbound_n": inbound_n,
        "chats_n": chats_n,
        "weak_items": weak_items,
    }
    recommendations = build_profile_recommendations(rec_ctx)

    ts = datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M")
    user_id = _esc(str(cfg.get("user_id") or "—"), 24)

    api_rows = [
        ("Профиль API", f"{_icon(prof_ok)} {'OK' if prof_ok else _esc((probe.get('profile') or {}).get('error', 'нет'), 100)}"),
        ("Messenger (чаты)", f"{_icon(msg_ok)} {'OK' if msg_ok else _esc((probe.get('messenger_chats') or {}).get('error', 'нет'), 100)}"),
        ("Статистика объявлений", f"{_icon(stats_ok)} {'OK — stats:read' if stats_ok else 'нет прав stats:read'}"),
        ("Client ID / Secret", "🟢 заданы"),
        ("User ID", f"<code>{user_id}</code>"),
    ]

    db_rows = [
        ("Объявлений в каталоге", f"<strong>{items_count}</strong>"),
        ("Строк статистики (по дням)", f"<strong>{stats_rows}</strong>"),
        ("Чатов в архиве", f"<strong>{chats_n}</strong>"),
        ("Сообщений", f"<strong>{msgs_n}</strong>"),
        ("Откликов «написал первым»", f"<strong>{inbound_n}</strong>"),
        ("HR-интервью (извлечено)", f"<strong>{int(storage.get('interviews') or 0)}</strong>"),
    ]
    if storage.get("last_full_sync_date"):
        db_rows.append(("Полная синхронизация", _esc(str(storage["last_full_sync_date"]), 20)))

    summary_html = ""
    if stats_rows > 0 and int(t.get("views") or 0) > 0:
        summary_html = (
            '<p class="ja-summary">'
            f"За <strong>{metrics_days} дн.</strong>: просмотры <strong>{int(t.get('views') or 0)}</strong>, "
            f"контакты <strong>{int(t.get('contacts') or 0)}</strong>, "
            f"избранное <strong>{int(t.get('favorites') or 0)}</strong>, "
            f"средний CTR <strong>{float(t.get('avg_ctr_pct') or 0)}%</strong>."
            "</p>"
        )
    elif stats_rows == 0 and chats_n > 0:
        summary_html = (
            '<p class="ja-warn">Чаты в базе есть, метрик пока нет — '
            "выполните «<strong>синхронизируй авито</strong>».</p>"
        )

    sync_block = ""
    if sync_note:
        sync_block = f'<p class="ja-sync">{_esc(sync_note, 300)}</p>'

    sections = [
        _box("1. Подключение API", _kv_table(api_rows)),
        _box("2. Локальная база (SQLite)", _kv_table(db_rows) + sync_block),
    ]
    if summary_html:
        sections.append(
            _box(f"3. Сводка за {metrics_days} дней", summary_html, variant="ja-box-accent")
        )
    if stats_rows > 0:
        sections.append(
            _box(
                f"4. Динамика по дням",
                _metrics_table(agg.get("daily") or []),
            )
        )
        sections.append(
            _box(
                "5. Топ объявлений по просмотрам",
                _top_items_table(agg.get("items") or []),
            )
        )
    sections.append(
        _box(
            "6. Рекомендации по профилю",
            _recommendations_html(recommendations),
            variant="ja-box-rec",
        )
    )
    sections.append(
        _box(
            "7. Что сказать Jarvis дальше",
            "<ul class=\"ja-actions\">"
            "<li>«<strong>Синхронизируй авито</strong>» — обновить API → SQLite</li>"
            "<li>«<strong>Отчёт по статистике авито за 2 недели</strong>»</li>"
            "<li>«<strong>Аудит объявлений авито</strong>» — слабые по CTR</li>"
            + (
                "<li>«<strong>Кто обещал прийти</strong>» — HR из чатов</li>"
                if chats_n > 0
                else "<li>«<strong>Скачай чаты авито</strong>»</li>"
            )
            + "</ul>"
            '<p class="ja-footnote">Только ваш кабинет через API; публичный каталог avito.ru не парсится.</p>',
        )
    )

    provenance = (
        '<footer class="ja-provenance">'
        "<p><strong>Источник данных:</strong> только Avito API (проверка прав) и таблицы SQLite "
        "(<code>avito_stats</code>, <code>avito_items</code>, архив чатов). "
        "Jarvis <strong>не придумывает</strong> просмотры, контакты и объявления. "
        "Рекомендации в блоке 6 — выводы по вашим цифрам, не факты с сайта.</p>"
        "</footer>"
    )

    return (
        f"{_AVITO_REPORT_MARKER}"
        '<div class="jarvis-avito-report">'
        '<header class="ja-header">'
        "<h2>📊 Отчёт по Авито (ваш кабинет)</h2>"
        f'<p class="ja-meta">Снимок: <strong>{html.escape(ts)}</strong> · только API + SQLite</p>'
        "</header>"
        + "".join(sections)
        + provenance
        + "</div>"
    )

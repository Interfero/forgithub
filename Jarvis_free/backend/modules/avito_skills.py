"""
Бизнес-навыки Авито-агента: HR-майнер, статистика, аудит объявлений.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from modules.avito_storage import (
    execute_local_sql_query,
    init_avito_storage,
    items_with_stats,
    messages_for_hr_mining,
    stats_aggregate,
    upsert_interview,
)

_HR_PROMPT = """Проанализируй фрагмент переписки Авито (сообщения кандидата/покупателя).
Найди **явное** согласие или обещание прийти на собеседование/встречу.
Извлеки JSON (только JSON, без markdown):
{"found": true|false, "candidate_name": "", "phone": "", "visit_at": "дата и время текстом", "confidence": 0.0-1.0}
Если нет явного обещания — {"found": false}.
"""

_EMPTY_CLICHES_RE = re.compile(
    r"\b(уютн|шикарн|прекрасн|уникальн|лучш|идеальн)\w*\b",
    re.I,
)


def _llm_extract_hr(text: str) -> dict[str, Any]:
    from modules.local_qwen import qwen_available, qwen_chat

    if not qwen_available():
        return {"found": False}
    msgs = [
        {"role": "system", "content": _HR_PROMPT},
        {"role": "user", "content": text[:6000]},
    ]
    try:
        raw, _ = qwen_chat(msgs, temperature=0.1, max_tokens=400, timeout_sec=60.0)
    except Exception:
        return {"found": False}
    raw = (raw or "").strip()
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"found": False}
    try:
        data = json.loads(m.group(0))
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"found": False}


def mine_hr_interviews(*, hours: int = 48) -> dict[str, Any]:
    """HR-майнер: обещания визита → extracted_interviews."""
    init_avito_storage()
    rows = messages_for_hr_mining(hours=hours)
    if not rows:
        return {"ok": True, "extracted": 0, "message": "Нет сообщений собеседника за период"}

    by_chat: dict[str, list[dict]] = {}
    for r in rows:
        by_chat.setdefault(r["chat_id"], []).append(r)

    extracted = 0
    for chat_id, msgs in by_chat.items():
        msgs.sort(key=lambda x: x.get("created_at") or "")
        blob = "\n".join(
            f"{m.get('counterpart_name', '')}: {m.get('text', '')[:500]}" for m in msgs[-20:]
        )
        data = _llm_extract_hr(blob)
        if not data.get("found"):
            continue
        last_mid = msgs[-1].get("message_id", "")
        upsert_interview(
            {
                "candidate_name": str(data.get("candidate_name") or msgs[-1].get("counterpart_name") or "")[:200],
                "phone": str(data.get("phone") or "")[:64],
                "visit_at": str(data.get("visit_at") or "")[:200],
                "chat_id": chat_id,
                "item_id": str(msgs[-1].get("item_id") or ""),
                "source_message_id": str(last_mid),
                "confidence": float(data.get("confidence") or 0.7),
                "raw_json": json.dumps(data, ensure_ascii=False),
                "extracted_at": date.today().isoformat(),
            }
        )
        extracted += 1

    return {"ok": True, "extracted": extracted, "chats_scanned": len(by_chat)}


def report_statistics_markdown(
    *,
    days: int = 14,
) -> str:
    """Отчёт только из SQLite — без выдуманных цифр."""
    date_to = date.today().isoformat()
    date_from = (date.today() - timedelta(days=days)).isoformat()
    agg = stats_aggregate(date_from, date_to)
    if not agg["items"] and not agg["daily"]:
        return (
            f"**Статистика Авито ({date_from} — {date_to})**\n\n"
            "В локальной базе нет строк `avito_stats`. "
            "Вызовите `sync_all_avito_data` или дождитесь ночной синхронизации."
        )

    lines = [
        f"## Статистика Авито ({date_from} — {date_to})",
        "",
        f"- **Просмотры:** {agg['totals']['views']}",
        f"- **Контакты (API):** {agg['totals']['contacts']}",
        f"- **В избранное:** {agg['totals'].get('favorites', 0)}",
        f"- **Отклики (соискатель написал первым):** {agg['totals'].get('inbound_leads', 0)}",
        f"- **Средний CTR (контакты/просмотры):** {agg['totals']['avg_ctr_pct']}%",
        "",
        "### По дням",
        "| День | Просмотры | Контакты | Избранное | Отклики |",
        "|------|-----------|----------|-----------|---------|",
    ]
    daily = agg["daily"]
    for i, d in enumerate(daily):
        v = int(d.get("views") or 0)
        c = int(d.get("contacts") or 0)
        fav = int(d.get("favorites") or 0)
        inb = int(d.get("inbound_leads") or 0)
        ctr = round(100.0 * c / v, 2) if v else 0.0
        trend = ""
        if i > 0:
            pv = int(daily[i - 1].get("views") or 0)
            if pv and v > pv * 1.1:
                trend = " 📈"
            elif pv and v < pv * 0.9:
                trend = " 📉"
        lines.append(
            f"| {d['date']} | {v} | {c} | {fav} | {inb} |{trend}"
        )

    lines.extend(["", "### Топ объявлений по просмотрам", ""])
    for it in agg["items"][:15]:
        lines.append(
            f"- **{it.get('title') or it['item_id']}** (id `{it['item_id']}`): "
            f"просмотры {it['views']}, контакты {it['contacts']}, "
            f"избранное {it.get('favorites', 0)}, отклики {it.get('inbound_leads', 0)}, "
            f"CTR **{it['ctr_pct']}%**"
        )
    return "\n".join(lines)


def audit_listings_markdown(*, days: int = 14) -> str:
    """Аудит объявлений: текст + конверсия vs среднее по аккаунту."""
    date_to = date.today().isoformat()
    date_from = (date.today() - timedelta(days=days)).isoformat()
    items = items_with_stats(date_from, date_to)
    if not items:
        return (
            "**Аудит объявлений**\n\n"
            "Нет данных в `avito_items` / `avito_stats`. Сначала `sync_all_avito_data`."
        )

    ctrs = [float(x.get("ctr_pct") or 0) for x in items if int(x.get("views") or 0) > 10]
    avg_ctr = sum(ctrs) / len(ctrs) if ctrs else 0.0

    lines = [
        "## Аудит объявлений Авито",
        "",
        f"Средний CTR по объявлениям с просмотрами (>10): **{round(avg_ctr, 2)}%**",
        "",
    ]
    weak = [x for x in items if int(x.get("views") or 0) > 20 and float(x.get("ctr_pct") or 0) < avg_ctr * 0.6]
    weak.sort(key=lambda x: float(x.get("ctr_pct") or 0))

    for it in weak[:12]:
        desc = (it.get("description") or "")[:800]
        title = it.get("title") or it["item_id"]
        tips: list[str] = []
        if len(desc) < 120:
            tips.append("Расширить описание: факты, условия, призыв к действию (AIDA).")
        if _EMPTY_CLICHES_RE.search(desc) or _EMPTY_CLICHES_RE.search(title):
            tips.append("Убрать пустые клише («уютный», «шикарный») — заменить конкретикой.")
        if not re.search(r"\d", desc):
            tips.append("Добавить цифры: цена, площадь, срок, комплектация.")
        if len(desc) > 3500:
            tips.append("Сократить текст — важное в первых 2–3 абзацах.")
        if not tips:
            tips.append("Проверить главное фото и категорию; сравнить с конкурентами в нише.")
        lines.append(f"### {title} (`{it['item_id']}`)")
        lines.append(f"- CTR **{it['ctr_pct']}%** при {it['views']} просмотрах (ниже среднего)")
        for t in tips:
            lines.append(f"  - {t}")
        lines.append("")

    if not weak:
        lines.append("Слабых объявлений по CTR не найдено — все в пределах нормы.")
    return "\n".join(lines)


def list_promised_interviews_markdown() -> str:
    q = execute_local_sql_query(
        """
        SELECT candidate_name, phone, visit_at, chat_id, item_id, confidence, extracted_at
        FROM extracted_interviews
        ORDER BY extracted_at DESC
        LIMIT 50
        """
    )
    if not q.get("ok"):
        return f"Ошибка SQL: {q.get('error')}"
    rows = q.get("rows") or []
    if not rows:
        return (
            "**Обещания визита**\n\n"
            "Таблица пуста. Запустите навык HR: `mine_hr_interviews` после синхронизации чатов."
        )
    lines = ["## Кто обещал прийти (из локальной БД)", ""]
    for r in rows:
        lines.append(
            f"- **{r.get('candidate_name') or '—'}** · {r.get('phone') or 'тел. нет'} · "
            f"визит: {r.get('visit_at') or '—'} · чат `{r.get('chat_id')}`"
        )
    return "\n".join(lines)

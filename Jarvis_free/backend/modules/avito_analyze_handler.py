"""
Запросы на анализ архива чатов Авито — ответ по данным SQLite, без рассуждений LLM.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from modules.avito_sync_handler import _history_mentions_avito


def _mentions_chat_context(low: str, history: list[dict] | None) -> bool:
    if any(
        w in low
        for w in (
            "авито",
            "avito",
            "соискател",
            "кандидат",
            "отклик",
            "messenger",
            "переписк",
            "архив чат",
        )
    ):
        return True
    if any(w in low for w in ("чат", "чаты", "переписк")) and _history_mentions_avito(history):
        return True
    return _history_mentions_avito(history)


def wants_avito_chat_analyze(user_text: str, history: list[dict] | None = None) -> bool:
    low = (user_text or "").lower().strip()
    if not low:
        return False

    if not _mentions_chat_context(low, history):
        return False

    analyze_markers = (
        "найди",
        "найти",
        "посчитай",
        "подсчит",
        "сколько",
        "анализ",
        "разбор",
        "случа",
        "уточнял",
        "уточня",
        "спрашивал",
        "спрашив",
        "успешн",
        "запис",
        "выгруз",
        "отчёт",
        "отчет",
        "статистик",
        "по фраз",
        "ключев",
    )
    topic_markers = (
        "адрес",
        "офис",
        "телефон",
        "собеседован",
        "соискател",
        "кандидат",
        "чат",
        "чаты",
        "переписк",
        "сообщен",
    )

    has_analyze = any(m in low for m in analyze_markers)
    has_topic = any(m in low for m in topic_markers)

    if has_analyze and has_topic:
        return True
    if "сколько" in low and has_topic:
        return True
    if ("найди" in low or "покажи" in low) and ("адрес" in low or "собеседован" in low):
        return True
    return False


def parse_analyze_focus(user_text: str) -> str:
    """address | phone | interview | all"""
    low = (user_text or "").lower()
    if "адрес" in low or ("офис" in low and "соискател" in low):
        return "address"
    if "телефон" in low or "позвон" in low:
        return "phone"
    if "собеседован" in low or "запис" in low:
        return "interview"
    return "all"


def _extract_days(user_text: str, default: int = 30) -> int:
    import re

    low = (user_text or "").lower()
    m = re.search(r"за\s+(\d+)\s*(?:дн|день|дней)", low)
    if m:
        return max(1, min(365, int(m.group(1))))
    if "месяц" in low or "30 дн" in low:
        return 30
    if "недел" in low:
        return 7
    return default


def format_focus_answer(
    user_text: str,
    data: dict[str, Any],
    *,
    focus: str,
    list_examples: bool,
) -> str:
    from modules.text_sanitize import polish_assistant_reply

    days = int(data.get("days") or 30)
    counts = data.get("counts") or {}
    total = int(counts.get("total") or 0)
    analyzed = int(data.get("analyzed") or 0)

    if focus == "address":
        n = int(counts.get("address") or 0)
        label = "соискатель уточнял адрес офиса"
        success_note = " (успешные записи по вашему критерию)" if "успешн" in user_text.lower() else ""
        head = f"За **{days}** дн.: **{n}** чатов, где {label}{success_note}."
    elif focus == "phone":
        n = int(counts.get("phone") or 0)
        head = f"За **{days}** дн.: **{n}** чатов с упоминанием телефона в переписке."
    elif focus == "interview":
        n = int(counts.get("interview") or 0) + int(counts.get("confirmed") or 0)
        head = f"За **{days}** дн.: **{n}** чатов с признаками собеседования/записи."
    else:
        head = (
            f"За **{days}** дн. просмотрено **{total}** чатов в архиве. "
            f"Адрес: **{counts.get('address', 0)}**, "
            f"телефон: **{counts.get('phone', 0)}**, "
            f"собеседование: **{int(counts.get('interview', 0)) + int(counts.get('confirmed', 0))}**."
        )
        return polish_assistant_reply(head, user_text)

    if analyzed == 0:
        body = (
            f"{head}\n\n"
            "В архиве пока нет чатов за этот период. Скажите «скачай чаты авито» — загружу переписки."
        )
        return polish_assistant_reply(body, user_text)

    lines = [head]
    if list_examples and focus != "all":
        tag = focus
        shown = 0
        for row in data.get("chats") or []:
            tags = row.get("tags") or []
            if tag not in tags:
                continue
            lines.append(f"• {row.get('summary', row.get('chat_id'))}")
            shown += 1
            if shown >= 12:
                rest = n - shown
                if rest > 0:
                    lines.append(f"… и ещё **{rest}**.")
                break
    return polish_assistant_reply("\n".join(lines), user_text)


def run_avito_analyze_for_user(
    user_text: str,
    *,
    days: int | None = None,
    history: list[dict] | None = None,
) -> tuple[str, dict[str, Any]]:
    from modules.avito import _creds_ok, _load_config
    from modules.avito_chat_analytics import analyze_chats
    from modules.avito_messenger import archive_stats
    from modules.text_sanitize import polish_assistant_reply

    days = days if days is not None else _extract_days(user_text)
    focus = parse_analyze_focus(user_text)
    list_examples = any(w in user_text.lower() for w in ("найди", "покажи", "список", "все случа"))

    if not _creds_ok(_load_config()):
        return (
            polish_assistant_reply(
                "Шеф, для анализа нужен архив чатов. Сначала укажите ключи Авито в коннекторе.",
                user_text,
            ),
            {"ok": False},
        )

    cc = archive_stats()
    if int(cc.get("chats_in_db") or cc.get("chats") or 0) == 0:
        return (
            polish_assistant_reply(
                "Архив чатов пуст. Напишите «скачай чаты авито» — затем повторите вопрос.",
                user_text,
            ),
            {"ok": False, "empty_archive": True},
        )

    try:
        data = analyze_chats(days=days)
        reply = format_focus_answer(
            user_text, data, focus=focus, list_examples=list_examples
        )
        return reply, data
    except Exception as e:
        return (
            polish_assistant_reply(f"Ошибка анализа чатов: {e}", user_text),
            {"ok": False, "error": str(e)},
        )


async def stream_avito_analyze_operation(
    chat_id: str,
    user_text: str,
    history: list[dict] | None,
    *,
    stream_reply,
) -> AsyncIterator[str]:
    from modules.agent import get_runtime
    from modules.operation_stream import sse_log, sse_progress

    rt = get_runtime()
    rt.status = "Analyzing Avito..."
    days = _extract_days(user_text)

    yield sse_progress("avito_analyze", "Анализ архива чатов…", current=0, total=100)
    yield sse_log("avito", f"Поиск по перепискам за {days} дн.")

    reply, _meta = run_avito_analyze_for_user(user_text, days=days, history=history)

    yield sse_progress("avito_analyze", "Готово", current=100, total=100)
    rt.status = "IDLE"

    async for chunk in stream_reply(chat_id, reply, user_text=user_text, instant=True):
        yield chunk

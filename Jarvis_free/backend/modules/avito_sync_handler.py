"""
Определение намерения «скачать чаты Авито» и выполнение синхронизации без галлюцинаций LLM.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from collections.abc import AsyncIterator
from typing import Any


def _history_mentions_avito(history: list[dict] | None) -> bool:
    if not history:
        return False
    for m in history[-6:]:
        if m.get("role") not in ("user", "assistant"):
            continue
        low = (m.get("content") or "").lower()
        if any(w in low for w in ("авито", "avito", "api авито", "апи авито", "messenger")):
            return True
    return False


def wants_avito_chat_sync(user_text: str, history: list[dict] | None = None) -> bool:
    low = (user_text or "").lower().strip()
    if not low:
        return False

    verbs = (
        "скачай",
        "скачать",
        "выгруз",
        "загруз",
        "синхрон",
        "сохрани",
        "сохранить",
        "стяг",
        "авториз",
        "получи",
        "подтяни",
        "забери",
        "скопируй",
        "запиши",
        "перенес",
    )
    nouns = (
        "чат",
        "чаты",
        "переписк",
        "сообщен",
        "мессендж",
        "архив",
        "авито",
        "avito",
        "соискател",
        "кандидат",
    )

    has_verb = any(v in low for v in verbs)
    has_noun = any(n in low for n in nouns)

    if has_verb and has_noun:
        return True
    if has_verb and "архив" in low:
        return True
    if has_verb and ("api" in low or "апи" in low) and "чат" in low:
        return True
    if has_verb and _history_mentions_avito(history):
        return True
    if has_verb and "данн" in low and _history_mentions_avito(history):
        return True

    return False


def _format_sync_result(user_text: str, result: dict[str, Any]) -> str:
    from modules.text_sanitize import polish_assistant_reply

    chats = int(result.get("chats_saved") or 0)
    msgs = int(result.get("messages_saved") or 0)
    api_path = result.get("api_path") or "?"
    hint = result.get("hint") or ""
    days = int(result.get("days") or 30)

    if chats == 0:
        body = (
            f"Запрос к API выполнен ({api_path}), но **чатов 0**. "
            f"{hint} "
            "Проверьте **User ID** и право messenger:read."
        )
    else:
        body = (
            f"Готово: в архив Jarvis загружено **{chats}** чатов и **{msgs}** сообщений "
            f"за {days} дн. Можете спросить «покажи чаты» или «анализ за месяц»."
        )
    return polish_assistant_reply(body.strip(), user_text)


def run_avito_sync_for_user(
    user_text: str,
    *,
    days: int = 30,
    history: list[dict] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Синхронный sync (запасной путь без SSE)."""
    from modules.avito import _creds_ok, _load_config
    from modules.text_sanitize import polish_assistant_reply

    if not _creds_ok(_load_config()):
        return (
            polish_assistant_reply(
                "Шеф, укажите **Client ID** и **Client Secret** в коннекторе Авито.",
                user_text,
            ),
            {"ok": False, "error": "need_creds"},
        )

    try:
        from modules.avito_messenger import probe_api

        probe = probe_api()
        msg_api = probe.get("messenger_chats") or {}
        if not msg_api.get("ok"):
            err = msg_api.get("error") or "нет доступа"
            return (
                polish_assistant_reply(f"Messenger API недоступен: {err}", user_text),
                {"ok": False, "probe": probe},
            )

        from modules.avito_chat_analytics import sync_chats_for_period

        result = sync_chats_for_period(days=days, max_chats=500, messages_per_chat=500)
        result["days"] = days
        return _format_sync_result(user_text, result), result
    except Exception as e:
        return (
            polish_assistant_reply(f"Ошибка загрузки чатов Авито: {e}", user_text),
            {"ok": False, "error": str(e)},
        )


async def stream_avito_sync_operation(
    chat_id: str,
    user_text: str,
    history: list[dict] | None,
    *,
    days: int = 30,
    stream_reply,
) -> AsyncIterator[str]:
    """
    SSE: progress/log во время синхронизации, затем финальный ответ в чат.
    stream_reply — async generator main._stream_assistant_reply (передаётся из main.py).
    """
    from modules.agent import get_runtime
    from modules.avito import _creds_ok, _load_config
    from modules.operation_stream import sse_log, sse_progress
    from modules.text_sanitize import polish_assistant_reply

    rt = get_runtime()
    rt.status = "Syncing Avito..."

    if not _creds_ok(_load_config()):
        err = polish_assistant_reply(
            "Шеф, укажите **Client ID** и **Client Secret** в коннекторе Авито.",
            user_text,
        )
        yield sse_progress("avito_sync", "Нужны ключи API в коннекторе Авито", current=0, total=0)
        async for chunk in stream_reply(chat_id, err, user_text=user_text, instant=True):
            yield chunk
        rt.status = "IDLE"
        return

    yield sse_progress("avito_sync", "Старт загрузки чатов Авито…", current=0, total=500)
    yield sse_log("avito", "Подключение к Messenger API")

    q: queue.Queue = queue.Queue()

    def on_progress(msg: str, current: int, total: int) -> None:
        q.put(("progress", msg, current, total))

    def worker() -> None:
        try:
            from modules.avito_messenger import probe_api

            on_progress("Проверка Messenger API…", 0, 500)
            probe = probe_api()
            msg_api = probe.get("messenger_chats") or {}
            if not msg_api.get("ok"):
                q.put(("error", msg_api.get("error") or "нет доступа"))
                return

            from modules.avito_chat_analytics import sync_chats_for_period

            r = sync_chats_for_period(
                days=days,
                max_chats=500,
                messages_per_chat=500,
                on_progress=on_progress,
            )
            r["days"] = days
            q.put(("done", r))
        except Exception as e:
            q.put(("error", str(e)))

    thread = threading.Thread(target=worker, name="avito-sync-stream", daemon=True)
    thread.start()

    result: dict[str, Any] | None = None
    while thread.is_alive() or not q.empty():
        try:
            item = q.get(timeout=0.35)
        except queue.Empty:
            await asyncio.sleep(0.05)
            continue

        kind = item[0]
        if kind == "progress":
            _, msg, cur, tot = item
            yield sse_progress("avito_sync", msg, current=cur, total=tot)
            yield sse_log("avito", msg)
        elif kind == "error":
            err_text = str(item[1])
            yield sse_progress("avito_sync", f"Ошибка: {err_text}", current=0, total=0)
            rt.status = "IDLE"
            reply = polish_assistant_reply(f"Ошибка загрузки чатов: {err_text}", user_text)
            async for chunk in stream_reply(chat_id, reply, user_text=user_text, instant=True):
                yield chunk
            return
        elif kind == "done":
            result = item[1]

    thread.join(timeout=120.0)
    rt.status = "IDLE"

    if result:
        chats = int(result.get("chats_saved") or 0)
        yield sse_progress(
            "avito_sync",
            f"Завершено: {chats} чатов, {result.get('messages_saved', 0)} сообщений",
            current=chats,
            total=max(chats, 500),
        )
        reply = _format_sync_result(user_text, result)
        async for chunk in stream_reply(chat_id, reply, user_text=user_text, instant=True):
            yield chunk

"""
Парсинг, анализ и очистка архива чатов Авито (accountant.db).
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from collections.abc import Callable
from typing import Any

from modules.documents import DB_PATH

ProgressFn = Callable[[str, int, int], None]  # message, current, total

DEFAULT_CRITERIA: dict[str, list[str]] = {
    "interview": [
        "собеседован",
        "запись на",
        "приглашаем на",
        "ждём вас",
        "ждем вас",
        "приходите",
        "встреча",
    ],
    "address": [
        "адрес офис",
        "адрес:",
        "находимся",
        "метро",
        "ул.",
        "улиц",
        "офис",
        "приезжайте",
    ],
    "phone": [
        "телефон",
        "позвон",
        "+7",
        "8-9",
    ],
    "confirmed": [
        "подтвержда",
        "записан",
        "ждём",
        "до встречи",
    ],
}


def _init_analysis_tables() -> None:
    from modules.avito_messenger import init_messenger_tables

    init_messenger_tables()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS avito_chat_analysis (
                user_id TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                analyzed_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                message_count INTEGER NOT NULL DEFAULT 0,
                has_interview INTEGER NOT NULL DEFAULT 0,
                has_address INTEGER NOT NULL DEFAULT 0,
                has_phone INTEGER NOT NULL DEFAULT 0,
                matched_tags TEXT NOT NULL DEFAULT '[]',
                summary TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (user_id, chat_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS avito_analysis_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )


def _load_criteria() -> dict[str, list[str]]:
    _init_analysis_tables()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT value FROM avito_analysis_config WHERE key = 'criteria'"
        ).fetchone()
    if row:
        try:
            data = json.loads(row[0])
            if isinstance(data, dict):
                return {k: list(v) for k, v in data.items() if isinstance(v, list)}
        except json.JSONDecodeError:
            pass
    return dict(DEFAULT_CRITERIA)


def save_criteria(criteria: dict[str, list[str]]) -> None:
    _init_analysis_tables()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO avito_analysis_config (key, value) VALUES ('criteria', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (json.dumps(criteria, ensure_ascii=False),),
        )


def _parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    if s.isdigit() and len(s) >= 10:
        try:
            return datetime.fromtimestamp(int(s[:10]), tz=timezone.utc)
        except (OSError, ValueError):
            return None
    return None


def _uid() -> str:
    from modules.avito_messenger import _user_id

    return _user_id()


def sync_chats_for_period(
    *,
    days: int = 30,
    max_chats: int = 500,
    messages_per_chat: int = 500,
    on_progress: ProgressFn | None = None,
) -> dict:
    """Синхронизировать чаты и сообщения за последние N дней."""

    def prog(msg: str, current: int = 0, total: int = 0) -> None:
        if on_progress:
            on_progress(msg, current, total)

    from modules.avito_messenger import (
        _chat_row,
        _fetch_chats_page,
        _fetch_messages_page,
        _message_row,
        _upsert_chat,
        _upsert_message,
        fetch_account_profile,
    )

    prog("Проверка OAuth и профиля аккаунта…", 0, max_chats)
    uid = _uid()
    profile = fetch_account_profile()
    name = profile.get("name") or uid
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    prog(f"Аккаунт: {name}. Загрузка списка чатов…", 0, max_chats)

    chats_saved = 0
    messages_saved = 0
    offset = 0
    limit = 100
    api_path = ""

    while chats_saved < max_chats:
        prog(f"Запрос страницы чатов (offset {offset})…", chats_saved, max_chats)
        batch, api_path = _fetch_chats_page(uid, limit=limit, offset=offset)
        if not batch:
            prog("Список чатов от API пуст — завершение.", chats_saved, max_chats)
            break
        for raw in batch:
            if not isinstance(raw, dict):
                continue
            row = _chat_row(uid, raw)
            if not row["chat_id"]:
                continue
            _upsert_chat(row)
            chats_saved += 1
            label = (row.get("counterpart_name") or row["chat_id"])[:40]
            prog(
                f"Чат {chats_saved}: {label} — загрузка сообщений…",
                chats_saved,
                max_chats,
            )

            moff = 0
            chat_msgs = 0
            stop_chat = False
            while chat_msgs < messages_per_chat and not stop_chat:
                msgs = _fetch_messages_page(
                    uid, row["chat_id"], limit=50, offset=moff
                )
                if not msgs:
                    break
                for m in msgs:
                    if not isinstance(m, dict):
                        continue
                    mrow = _message_row(uid, row["chat_id"], m)
                    if not mrow:
                        continue
                    dt = _parse_dt(mrow["created_at"])
                    if dt and dt < cutoff:
                        stop_chat = True
                        break
                    _upsert_message(mrow)
                    messages_saved += 1
                    chat_msgs += 1
                    if chat_msgs % 25 == 0:
                        prog(
                            f"Чат {chats_saved}: {chat_msgs} сообщ. (всего {messages_saved})…",
                            chats_saved,
                            max_chats,
                        )
                    if chat_msgs >= messages_per_chat:
                        break
                if len(msgs) < 50:
                    break
                moff += 50

            if chats_saved >= max_chats:
                break
        if len(batch) < limit:
            break
        offset += limit

    prog(
        f"Готово: {chats_saved} чатов, {messages_saved} сообщений.",
        chats_saved,
        max_chats,
    )

    hint = ""
    if chats_saved == 0:
        from modules.avito_messenger import probe_api

        try:
            p = probe_api()
            hint = (p.get("messenger_chats") or {}).get("error") or ""
        except Exception as e:
            hint = str(e)[:200]

    return {
        "ok": True,
        "days": days,
        "chats_saved": chats_saved,
        "messages_saved": messages_saved,
        "api_path": api_path,
        "cutoff": cutoff.isoformat(),
        "hint": hint,
    }


def _match_tags(text: str, criteria: dict[str, list[str]]) -> list[str]:
    low = (text or "").lower()
    tags: list[str] = []
    for tag, phrases in criteria.items():
        if any(p.lower() in low for p in phrases):
            tags.append(tag)
    return tags


def _chat_full_text(uid: str, chat_id: str) -> tuple[str, int]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT text, created_at FROM avito_messages
            WHERE user_id = ? AND chat_id = ?
            ORDER BY created_at ASC
            """,
            (uid, chat_id),
        ).fetchall()
    parts = [r["text"] for r in rows if r["text"]]
    return "\n".join(parts), len(rows)


def analyze_chats(
    *,
    days: int = 30,
    chat_id: str | None = None,
    criteria: dict[str, list[str]] | None = None,
) -> dict:
    """Анализ переписок по критериям (ключевые фразы)."""
    _init_analysis_tables()
    crit = criteria or _load_criteria()
    uid = _uid()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if chat_id:
            chats = conn.execute(
                "SELECT * FROM avito_chats WHERE user_id = ? AND chat_id = ?",
                (uid, chat_id),
            ).fetchall()
        else:
            chats = conn.execute(
                "SELECT * FROM avito_chats WHERE user_id = ? ORDER BY last_message_at DESC",
                (uid,),
            ).fetchall()

    results: list[dict] = []
    summary_counts: dict[str, int] = {k: 0 for k in crit}
    summary_counts["total"] = 0

    for ch in chats:
        cid = ch["chat_id"]
        lm = _parse_dt(ch["last_message_at"] or "")
        if lm and lm < cutoff:
            continue

        body, msg_count = _chat_full_text(uid, cid)
        if msg_count == 0:
            continue

        tags = _match_tags(body, crit)
        has_interview = 1 if "interview" in tags or "confirmed" in tags else 0
        has_address = 1 if "address" in tags else 0
        has_phone = 1 if "phone" in tags else 0

        name = ch["counterpart_name"] or cid
        item = (ch["item_title"] or "")[:60]
        tag_str = ", ".join(tags) if tags else "—"
        one_line = f"{name}" + (f" · {item}" if item else "") + f" — [{tag_str}] ({msg_count} сообщ.)"

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO avito_chat_analysis (
                    user_id, chat_id, analyzed_at, status, message_count,
                    has_interview, has_address, has_phone, matched_tags, summary
                ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, chat_id) DO UPDATE SET
                    analyzed_at=excluded.analyzed_at,
                    status='active',
                    message_count=excluded.message_count,
                    has_interview=excluded.has_interview,
                    has_address=excluded.has_address,
                    has_phone=excluded.has_phone,
                    matched_tags=excluded.matched_tags,
                    summary=excluded.summary
                """,
                (
                    uid,
                    cid,
                    now,
                    msg_count,
                    has_interview,
                    has_address,
                    has_phone,
                    json.dumps(tags, ensure_ascii=False),
                    one_line,
                ),
            )

        results.append(
            {
                "chat_id": cid,
                "counterpart_name": name,
                "item_title": item,
                "message_count": msg_count,
                "tags": tags,
                "has_interview": bool(has_interview),
                "has_address": bool(has_address),
                "summary": one_line,
            }
        )
        summary_counts["total"] += 1
        for t in tags:
            summary_counts[t] = summary_counts.get(t, 0) + 1

    return {
        "ok": True,
        "days": days,
        "analyzed": len(results),
        "counts": summary_counts,
        "chats": results[:100],
    }


def format_analysis_report(data: dict) -> str:
    c = data.get("counts") or {}
    lines = [
        f"Анализ чатов за {data.get('days', 30)} дн.: просмотрено {c.get('total', 0)} чатов.",
        f"Собеседование/запись: {c.get('interview', 0) + c.get('confirmed', 0)}, "
        f"адрес: {c.get('address', 0)}, телефон: {c.get('phone', 0)}.",
    ]
    for row in (data.get("chats") or [])[:20]:
        lines.append(f"• {row.get('summary', row.get('chat_id'))}")
    if data.get("analyzed", 0) > 20:
        lines.append(f"… и ещё {data['analyzed'] - 20} чатов.")
    return "\n".join(lines)


def purge_chat_archive(chat_id: str, *, keep_analysis: bool = True) -> dict:
    """
    Удалить сообщения и карточку чата из локального архива (после выгрузки/закрытия).
    """
    _init_analysis_tables()
    uid = _uid()
    cid = (chat_id or "").strip()
    if not cid:
        raise ValueError("chat_id обязателен")

    with sqlite3.connect(DB_PATH) as conn:
        msg_del = conn.execute(
            "DELETE FROM avito_messages WHERE user_id = ? AND chat_id = ?",
            (uid, cid),
        ).rowcount
        chat_del = conn.execute(
            "DELETE FROM avito_chats WHERE user_id = ? AND chat_id = ?",
            (uid, cid),
        ).rowcount
        if keep_analysis:
            conn.execute(
                """
                UPDATE avito_chat_analysis
                SET status = 'purged', analyzed_at = ?
                WHERE user_id = ? AND chat_id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), uid, cid),
            )
        else:
            conn.execute(
                "DELETE FROM avito_chat_analysis WHERE user_id = ? AND chat_id = ?",
                (uid, cid),
            )

    return {
        "ok": True,
        "chat_id": cid,
        "messages_deleted": msg_del,
        "chat_deleted": chat_del,
    }


def purge_stale_chats(*, days: int = 30, only_without_interview: bool = False) -> dict:
    """Массовая очистка старых или «пустых» чатов из архива."""
    uid = _uid()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    purged = 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT chat_id, last_message_at FROM avito_chats WHERE user_id = ?",
            (uid,),
        ).fetchall()

    for row in rows:
        cid = row["chat_id"]
        if only_without_interview:
            with sqlite3.connect(DB_PATH) as conn:
                a = conn.execute(
                    """
                    SELECT has_interview FROM avito_chat_analysis
                    WHERE user_id = ? AND chat_id = ? AND status = 'active'
                    """,
                    (uid, cid),
                ).fetchone()
            if a and a[0]:
                continue
        lm = _parse_dt(row["last_message_at"] or "")
        if lm and lm < cutoff:
            purge_chat_archive(cid)
            purged += 1

    return {"ok": True, "purged": purged, "days": days}


def run_full_pipeline(*, days: int = 30) -> dict:
    """Синхронизация → анализ → отчёт."""
    sync = sync_chats_for_period(days=days)
    analysis = analyze_chats(days=days)
    return {
        "sync": sync,
        "analysis": analysis,
        "report": format_analysis_report(analysis),
    }

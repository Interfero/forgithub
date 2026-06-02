"""
Локальный индекс сообщений Telegram для поиска (SQLite + FTS5).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.tg_twin import TG_DIR

INBOX_DB = TG_DIR / "inbox.db"


def _connect() -> sqlite3.Connection:
    TG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(INBOX_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                chat_id INTEGER NOT NULL,
                msg_id INTEGER NOT NULL,
                chat_title TEXT,
                chat_username TEXT,
                sender_name TEXT,
                text TEXT NOT NULL DEFAULT '',
                date_iso TEXT,
                outgoing INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, msg_id)
            );
            CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date_iso);

            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                text,
                chat_title,
                sender_name
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _rowid(conn: sqlite3.Connection, chat_id: int, msg_id: int) -> int | None:
    cur = conn.execute(
        "SELECT rowid FROM messages WHERE chat_id=? AND msg_id=?",
        (chat_id, msg_id),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def upsert_message(
    *,
    chat_id: int,
    msg_id: int,
    chat_title: str,
    chat_username: str | None,
    sender_name: str,
    text: str,
    date_iso: str | None,
    outgoing: bool,
) -> None:
    init_db()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO messages (
                chat_id, msg_id, chat_title, chat_username, sender_name,
                text, date_iso, outgoing
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, msg_id) DO UPDATE SET
                chat_title=excluded.chat_title,
                chat_username=excluded.chat_username,
                sender_name=excluded.sender_name,
                text=excluded.text,
                date_iso=excluded.date_iso,
                outgoing=excluded.outgoing
            """,
            (
                chat_id,
                msg_id,
                chat_title,
                chat_username,
                sender_name,
                text or "",
                date_iso,
                1 if outgoing else 0,
            ),
        )
        rid = _rowid(conn, chat_id, msg_id)
        if rid is not None:
            conn.execute("DELETE FROM messages_fts WHERE rowid=?", (rid,))
            conn.execute(
                """
                INSERT INTO messages_fts(rowid, text, chat_title, sender_name)
                VALUES (?, ?, ?, ?)
                """,
                (rid, text or "", chat_title, sender_name),
            )
        conn.commit()
    finally:
        conn.close()


async def index_message_from_event(event, client) -> None:
    msg = event.message
    text = msg.message or ""
    if not text and not msg.media:
        return
    chat = await event.get_chat()
    sender = await event.get_sender()
    title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(event.chat_id)
    username = getattr(chat, "username", None)
    sender_name = (
        getattr(sender, "first_name", None)
        or getattr(sender, "title", None)
        or "?"
    )
    date_iso = msg.date.isoformat() if msg.date else None
    upsert_message(
        chat_id=event.chat_id,
        msg_id=msg.id,
        chat_title=title,
        chat_username=username,
        sender_name=sender_name,
        text=text,
        date_iso=date_iso,
        outgoing=bool(msg.out),
    )


def _dialog_username(entity) -> str | None:
    username = getattr(entity, "username", None)
    return f"@{str(username).lower()}" if username else None


def _is_blocked_dialog(dialog, peer_blocklist: set[int], username_blocklist: set[str]) -> bool:
    if dialog.id in peer_blocklist:
        return True
    uname = _dialog_username(dialog.entity)
    return bool(uname and uname in username_blocklist)


async def sync_all_dialogs(
    client,
    *,
    limit_per_chat: int,
    peer_blocklist: set[int],
    username_blocklist: set[str],
    on_progress=None,
) -> dict:
    init_db()
    total = 0
    chats = 0
    async for dialog in client.iter_dialogs():
        if _is_blocked_dialog(dialog, peer_blocklist, username_blocklist):
            continue
        chats += 1
        title = dialog.title or dialog.name or str(dialog.id)
        username = getattr(dialog.entity, "username", None)
        async for msg in client.iter_messages(dialog.entity, limit=limit_per_chat):
            text = msg.message or ""
            if not text and not msg.media:
                continue
            sender = await msg.get_sender() if msg.sender_id else None
            sender_name = (
                getattr(sender, "first_name", None)
                or getattr(sender, "title", None)
                or "?"
            )
            upsert_message(
                chat_id=dialog.id,
                msg_id=msg.id,
                chat_title=title,
                chat_username=username,
                sender_name=sender_name,
                text=text,
                date_iso=msg.date.isoformat() if msg.date else None,
                outgoing=bool(msg.out),
            )
            total += 1
        if on_progress:
            on_progress(chats, total)
    return {"chats_indexed": chats, "messages_indexed": total}


def _fts_query(q: str) -> str:
    import re

    tokens = re.findall(r"[\w\u0400-\u04FF]+", q, flags=re.UNICODE)
    if not tokens:
        return f'"{q}"'
    return " OR ".join(f'"{t}"*' for t in tokens[:12])


def search(query: str, limit: int = 40) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    init_db()
    conn = _connect()
    try:
        fts_q = _fts_query(q)
        rows = conn.execute(
            """
            SELECT m.chat_id, m.msg_id, m.chat_title, m.chat_username,
                   m.sender_name, m.text, m.date_iso, m.outgoing
            FROM messages_fts fts
            JOIN messages m ON m.rowid = fts.rowid
            WHERE messages_fts MATCH ?
            ORDER BY m.date_iso DESC
            LIMIT ?
            """,
            (fts_q, limit),
        ).fetchall()
        if not rows:
            like = f"%{q}%"
            rows = conn.execute(
                """
                SELECT chat_id, msg_id, chat_title, chat_username,
                       sender_name, text, date_iso, outgoing
                FROM messages
                WHERE text LIKE ? OR chat_title LIKE ? OR sender_name LIKE ?
                ORDER BY date_iso DESC
                LIMIT ?
                """,
                (like, like, like, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def stats() -> dict:
    init_db()
    conn = _connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        chats = conn.execute("SELECT COUNT(DISTINCT chat_id) FROM messages").fetchone()[0]
        last = conn.execute("SELECT MAX(date_iso) FROM messages").fetchone()[0]
        return {
            "messages_total": total,
            "chats_total": chats,
            "last_message_at": last,
        }
    finally:
        conn.close()

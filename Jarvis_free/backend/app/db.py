from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.schemas import AppSettings, ChatOut, MessageOut


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    settings.data_path.mkdir(parents=True, exist_ok=True)
    settings.files_path.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                indexed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )


@contextmanager
def get_conn():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def load_settings() -> AppSettings:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    if not rows:
        return AppSettings()
    data = {r["key"]: json.loads(r["value"]) for r in rows}
    return AppSettings.model_validate(data)


def save_settings(s: AppSettings) -> AppSettings:
    payload = s.model_dump()
    with get_conn() as conn:
        for key, value in payload.items():
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )
    return s


def list_chats() -> list[ChatOut]:
    with get_conn() as conn:
        chats = conn.execute(
            "SELECT id, title, updated_at FROM chats ORDER BY updated_at DESC"
        ).fetchall()
        result: list[ChatOut] = []
        for c in chats:
            msgs = conn.execute(
                "SELECT id, role, content, created_at FROM messages "
                "WHERE chat_id = ? ORDER BY created_at ASC",
                (c["id"],),
            ).fetchall()
            result.append(
                ChatOut(
                    id=c["id"],
                    title=c["title"],
                    updated_at=c["updated_at"],
                    messages=[
                        MessageOut(
                            id=m["id"],
                            role=m["role"],
                            content=m["content"],
                            created_at=m["created_at"],
                        )
                        for m in msgs
                    ],
                )
            )
    return result


def create_chat(title: str = "Новый диалог") -> ChatOut:
    cid = str(uuid.uuid4())
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chats (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (cid, title, now, now),
        )
    return ChatOut(id=cid, title=title, updated_at=now, messages=[])


def update_chat(chat_id: str, title: str) -> ChatOut | None:
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, chat_id),
        )
        if cur.rowcount == 0:
            return None
    chats = [c for c in list_chats() if c.id == chat_id]
    return chats[0] if chats else None


def delete_chat(chat_id: str) -> bool:
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        cur = conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        return cur.rowcount > 0


def add_message(chat_id: str, role: str, content: str) -> MessageOut:
    mid = str(uuid.uuid4())
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, chat_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (mid, chat_id, role, content, now),
        )
        conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))
    return MessageOut(id=mid, role=role, content=content, created_at=now)


def get_chat_messages(chat_id: str, limit: int = 50) -> list[MessageOut]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages "
            "WHERE chat_id = ? ORDER BY created_at ASC",
            (chat_id,),
        ).fetchall()
    msgs = [
        MessageOut(id=r["id"], role=r["role"], content=r["content"], created_at=r["created_at"])
        for r in rows
    ]
    if len(msgs) > limit:
        return msgs[-limit:]
    return msgs


def register_file(name: str, path: Path, size: int) -> str:
    fid = str(uuid.uuid4())
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO files (id, name, path, size, indexed, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (fid, name, str(path), size, now),
        )
    return fid


def mark_file_indexed(file_id: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE files SET indexed = 1 WHERE id = ?", (file_id,))


def list_files() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, size, indexed FROM files ORDER BY created_at DESC"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "size": r["size"],
            "indexed": bool(r["indexed"]),
        }
        for r in rows
    ]

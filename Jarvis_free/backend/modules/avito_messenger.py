"""
Авито Messenger API — список чатов, сообщения, локальный архив в accountant.db.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

import httpx

from modules.documents import DB_PATH
from modules.http_proxy import httpx_client

API_BASE = "https://api.avito.ru"
_HTTP = httpx.Timeout(60.0, connect=20.0)

CHAT_LIST_PATHS = (
    "/messenger/v2/accounts/{uid}/chats",
    "/messenger/v1/accounts/{uid}/chats",
)
MESSAGE_LIST_PATHS = (
    "/messenger/v3/accounts/{uid}/chats/{cid}/messages/",
    "/messenger/v3/accounts/{uid}/chats/{cid}/messages",
    "/messenger/v2/accounts/{uid}/chats/{cid}/messages",
    "/messenger/v1/accounts/{uid}/chats/{cid}/messages",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _headers() -> dict[str, str]:
    from modules.avito import _api_headers

    return _api_headers()


def _cfg() -> dict:
    from modules.avito import _load_config

    return _load_config()


def _user_id() -> str:
    from modules.avito import _creds_ok, _resolve_user_id

    cfg = _cfg()
    if not _creds_ok(cfg):
        raise RuntimeError("Нужны Client ID и Client Secret Авито")
    return _resolve_user_id(cfg)


def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    with httpx_client(timeout=_HTTP, proxy=None) as client:
        return client.request(method, url, headers=_headers(), **kwargs)


def init_messenger_tables() -> None:
    from modules.documents import init_db

    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS avito_account (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                profile_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS avito_chats (
                user_id TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                item_id TEXT NOT NULL DEFAULT '',
                item_title TEXT NOT NULL DEFAULT '',
                context_type TEXT NOT NULL DEFAULT '',
                counterpart_id TEXT NOT NULL DEFAULT '',
                counterpart_name TEXT NOT NULL DEFAULT '',
                last_message_text TEXT NOT NULL DEFAULT '',
                last_message_at TEXT NOT NULL DEFAULT '',
                unread_count INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}',
                synced_at TEXT NOT NULL,
                PRIMARY KEY (user_id, chat_id)
            );

            CREATE TABLE IF NOT EXISTS avito_messages (
                user_id TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                author_id TEXT NOT NULL DEFAULT '',
                direction TEXT NOT NULL DEFAULT '',
                msg_type TEXT NOT NULL DEFAULT 'text',
                text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL DEFAULT '{}',
                synced_at TEXT NOT NULL,
                PRIMARY KEY (user_id, chat_id, message_id)
            );

            CREATE TABLE IF NOT EXISTS avito_sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_avito_chats_updated
                ON avito_chats(last_message_at DESC);
            CREATE INDEX IF NOT EXISTS idx_avito_messages_chat
                ON avito_messages(user_id, chat_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_avito_messages_text
                ON avito_messages(text);
            """
        )


def _meta_get(key: str) -> str:
    init_messenger_tables()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT value FROM avito_sync_meta WHERE key = ?", (key,)
        ).fetchone()
    return row[0] if row else ""


def _meta_set(key: str, value: str) -> None:
    init_messenger_tables()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO avito_sync_meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def _parse_ts(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (OSError, ValueError):
            return str(int(value))
    s = str(value).strip()
    if s.isdigit() and len(s) >= 10:
        try:
            ts = int(s[:10])
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (OSError, ValueError):
            pass
    return s


def _chat_row(uid: str, raw: dict) -> dict:
    chat_id = str(
        raw.get("id")
        or raw.get("chat_id")
        or raw.get("chatId")
        or ""
    ).strip()
    ctx = raw.get("context") or {}
    if isinstance(ctx, dict):
        ctx_type = str(ctx.get("type") or "")
        ctx_val = ctx.get("value") if isinstance(ctx.get("value"), dict) else ctx
    else:
        ctx_type, ctx_val = "", {}
    item_id = ""
    item_title = ""
    if isinstance(ctx_val, dict):
        item_id = str(ctx_val.get("id") or ctx_val.get("item_id") or "")
        item_title = str(ctx_val.get("title") or ctx_val.get("name") or "")[:500]

    users = raw.get("users") or raw.get("participants") or []
    counterpart_id = ""
    counterpart_name = ""
    if isinstance(users, list):
        for u in users:
            if not isinstance(u, dict):
                continue
            uid_u = str(u.get("id") or "")
            if uid_u and uid_u != uid:
                counterpart_id = uid_u
                counterpart_name = str(u.get("name") or u.get("public_name") or "")[:200]
                break
        if not counterpart_name and users:
            u0 = users[0] if isinstance(users[0], dict) else {}
            counterpart_name = str(u0.get("name") or "")[:200]
            counterpart_id = str(u0.get("id") or "")

    last = raw.get("last_message") or raw.get("lastMessage") or {}
    if isinstance(last, dict):
        content = last.get("content")
        content_text = ""
        if isinstance(content, dict):
            content_text = str(content.get("text") or content.get("body") or "")
        elif isinstance(content, str):
            content_text = content
        msg_obj = last.get("message")
        msg_text = ""
        if isinstance(msg_obj, dict):
            msg_text = str(msg_obj.get("text") or "")
        lm_text = str(
            last.get("text") or content_text or msg_text or last.get("body") or ""
        )[:2000]
        lm_at = _parse_ts(
            last.get("created")
            or last.get("created_at")
            or raw.get("updated")
            or raw.get("updated_at")
        )
    else:
        lm_text = ""
        lm_at = _parse_ts(raw.get("updated") or raw.get("updated_at"))

    unread = int(raw.get("unread_count") or raw.get("unreadCount") or 0)

    return {
        "user_id": uid,
        "chat_id": chat_id,
        "item_id": item_id,
        "item_title": item_title,
        "context_type": ctx_type,
        "counterpart_id": counterpart_id,
        "counterpart_name": counterpart_name,
        "last_message_text": lm_text,
        "last_message_at": lm_at,
        "unread_count": unread,
        "raw_json": json.dumps(raw, ensure_ascii=False)[:8000],
        "synced_at": _now_iso(),
    }


def _message_row(uid: str, chat_id: str, raw: dict) -> dict | None:
    mid = str(raw.get("id") or raw.get("message_id") or raw.get("messageId") or "")
    if not mid:
        return None
    content = raw.get("content")
    text = ""
    if isinstance(content, dict):
        text = str(content.get("text") or content.get("body") or "")
    elif isinstance(content, str):
        text = content
    msg_wrap = raw.get("message")
    if not text and isinstance(msg_wrap, dict):
        text = str(msg_wrap.get("text") or "")
    if not text and isinstance(raw.get("message"), str):
        text = str(raw.get("message"))
    if not text:
        text = str(raw.get("text") or raw.get("body") or "")

    author = str(
        raw.get("author_id")
        or raw.get("authorId")
        or raw.get("user_id")
        or raw.get("from_id")
        or ""
    )
    direction = str(raw.get("direction") or "").lower()
    if direction not in ("in", "out"):
        direction = "out" if author and author == uid else "in"
    role = "self" if direction == "out" else "counterpart"

    return {
        "user_id": uid,
        "chat_id": chat_id,
        "message_id": mid,
        "author_id": author,
        "direction": direction,
        "role": role,
        "msg_type": str(raw.get("type") or "text"),
        "text": text[:8000],
        "created_at": _parse_ts(raw.get("created") or raw.get("created_at")),
        "raw_json": json.dumps(raw, ensure_ascii=False)[:8000],
        "synced_at": _now_iso(),
    }


def _upsert_chat(row: dict) -> None:
    init_messenger_tables()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO avito_chats (
                user_id, chat_id, item_id, item_title, context_type,
                counterpart_id, counterpart_name, last_message_text,
                last_message_at, unread_count, raw_json, synced_at
            ) VALUES (
                :user_id, :chat_id, :item_id, :item_title, :context_type,
                :counterpart_id, :counterpart_name, :last_message_text,
                :last_message_at, :unread_count, :raw_json, :synced_at
            )
            ON CONFLICT(user_id, chat_id) DO UPDATE SET
                item_id=excluded.item_id,
                item_title=excluded.item_title,
                context_type=excluded.context_type,
                counterpart_id=excluded.counterpart_id,
                counterpart_name=excluded.counterpart_name,
                last_message_text=excluded.last_message_text,
                last_message_at=excluded.last_message_at,
                unread_count=excluded.unread_count,
                raw_json=excluded.raw_json,
                synced_at=excluded.synced_at
            """,
            row,
        )


def _upsert_message(row: dict) -> None:
    from modules.avito_storage import init_avito_storage

    init_avito_storage()
    if "role" not in row:
        row = {
            **row,
            "role": "self" if row.get("direction") == "out" else "counterpart",
        }
    with sqlite3.connect(DB_PATH) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(avito_messages)").fetchall()}
        if "role" in cols:
            conn.execute(
                """
                INSERT INTO avito_messages (
                    user_id, chat_id, message_id, author_id, direction, role,
                    msg_type, text, created_at, raw_json, synced_at
                ) VALUES (
                    :user_id, :chat_id, :message_id, :author_id, :direction, :role,
                    :msg_type, :text, :created_at, :raw_json, :synced_at
                )
                ON CONFLICT(user_id, chat_id, message_id) DO UPDATE SET
                    author_id=excluded.author_id,
                    direction=excluded.direction,
                    role=excluded.role,
                    msg_type=excluded.msg_type,
                    text=excluded.text,
                    created_at=excluded.created_at,
                    raw_json=excluded.raw_json,
                    synced_at=excluded.synced_at
                """,
                row,
            )
        else:
            conn.execute(
                """
                INSERT INTO avito_messages (
                    user_id, chat_id, message_id, author_id, direction,
                    msg_type, text, created_at, raw_json, synced_at
                ) VALUES (
                    :user_id, :chat_id, :message_id, :author_id, :direction,
                    :msg_type, :text, :created_at, :raw_json, :synced_at
                )
                ON CONFLICT(user_id, chat_id, message_id) DO UPDATE SET
                    author_id=excluded.author_id,
                    direction=excluded.direction,
                    msg_type=excluded.msg_type,
                    text=excluded.text,
                    created_at=excluded.created_at,
                    raw_json=excluded.raw_json,
                    synced_at=excluded.synced_at
                """,
                row,
            )


def _extract_list(body: Any, keys: tuple[str, ...]) -> list:
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        return []
    for k in keys:
        v = body.get(k)
        if isinstance(v, list):
            return v
    nested = body.get("result")
    if isinstance(nested, dict):
        for k in keys:
            v = nested.get(k)
            if isinstance(v, list):
                return v
    if isinstance(nested, list):
        return nested
    return []


def fetch_account_profile() -> dict:
    uid = _user_id()
    r = _request("GET", f"/core/v1/accounts/self")
    if r.status_code == 403:
        raise RuntimeError(
            "Нет доступа к профилю (user:read). Проверьте права приложения на developers.avito.ru"
        )
    r.raise_for_status()
    data = r.json()
    profile = {
        "user_id": uid,
        "name": str(data.get("name") or data.get("profile_name") or ""),
        "email": str(data.get("email") or ""),
        "phone": str(data.get("phone") or data.get("phones", [""])[0] if data.get("phones") else ""),
        "profile_json": json.dumps(data, ensure_ascii=False),
        "updated_at": _now_iso(),
    }
    init_messenger_tables()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO avito_account (user_id, name, email, phone, profile_json, updated_at)
            VALUES (:user_id, :name, :email, :phone, :profile_json, :updated_at)
            ON CONFLICT(user_id) DO UPDATE SET
                name=excluded.name, email=excluded.email, phone=excluded.phone,
                profile_json=excluded.profile_json, updated_at=excluded.updated_at
            """,
            profile,
        )
    return profile


def _fetch_chats_page(uid: str, *, limit: int, offset: int) -> tuple[list[dict], str]:
    last_err = ""
    for tpl in CHAT_LIST_PATHS:
        path = tpl.format(uid=uid)
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        r = _request("GET", path, params=params)
        if r.status_code == 404:
            last_err = f"{path}: HTTP 404"
            continue
        if r.status_code == 403:
            raise RuntimeError(
                "Нет доступа к Messenger API (messenger:read). "
                "В developers.avito.ru включите права «Чтение сообщений» для приложения."
            )
        if r.status_code >= 400:
            last_err = f"{path}: HTTP {r.status_code} {r.text[:200]}"
            continue
        body = r.json()
        chats = _extract_list(body, ("chats", "items", "data", "result"))
        _meta_set("last_chats_api_sample", json.dumps(body, ensure_ascii=False)[:2000])
        return chats, path
    raise RuntimeError(last_err or "Не удалось получить список чатов Авито")


def _fetch_messages_page(uid: str, chat_id: str, *, limit: int, offset: int) -> list[dict]:
    last_err = ""
    for tpl in MESSAGE_LIST_PATHS:
        path = tpl.format(uid=uid, cid=chat_id)
        r = _request("GET", path, params={"limit": limit, "offset": offset})
        if r.status_code in (404, 405):
            last_err = f"{path}: HTTP {r.status_code}"
            continue
        if r.status_code == 403:
            raise RuntimeError("Нет доступа к сообщениям (messenger:read)")
        if r.status_code >= 400:
            last_err = f"{path}: HTTP {r.status_code}"
            continue
        body = r.json()
        msgs = _extract_list(body, ("messages", "result", "items", "data"))
        return msgs
    if last_err:
        return []
    return []


def sync_chats(
    *,
    max_chats: int = 500,
    messages_per_chat: int = 100,
    fetch_messages: bool = True,
) -> dict:
    """Скачать чаты и сообщения в локальную БД."""
    from modules import jarvis_db

    uid = _user_id()
    jarvis_db.init_db()
    profile = fetch_account_profile()

    chats_saved = 0
    messages_saved = 0
    offset = 0
    limit = 100
    api_path = ""

    while chats_saved < max_chats:
        batch, api_path = _fetch_chats_page(uid, limit=limit, offset=offset)
        if not batch:
            break
        for raw in batch:
            if not isinstance(raw, dict):
                continue
            row = _chat_row(uid, raw)
            if not row["chat_id"]:
                continue
            _upsert_chat(row)
            chats_saved += 1
            if fetch_messages:
                moff = 0
                chat_msg_count = 0
                while chat_msg_count < messages_per_chat:
                    msgs = _fetch_messages_page(
                        uid, row["chat_id"], limit=50, offset=moff
                    )
                    if not msgs:
                        break
                    for m in msgs:
                        if not isinstance(m, dict):
                            continue
                        mrow = _message_row(uid, row["chat_id"], m)
                        if mrow:
                            _upsert_message(mrow)
                            messages_saved += 1
                            chat_msg_count += 1
                            if chat_msg_count >= messages_per_chat:
                                break
                    if len(msgs) < 50:
                        break
                    moff += 50
            if chats_saved >= max_chats:
                break
        if len(batch) < limit:
            break
        offset += limit

    now = _now_iso()
    _meta_set("last_chats_sync_at", now)
    _meta_set("chats_api_path", api_path)
    _meta_set("chats_count", str(chats_saved))
    _meta_set("messages_count", str(messages_saved))

    jarvis_db.set_cell(
        mode_code=None,
        namespace="avito",
        cell_key="archive_last_sync",
        content=(
            f"Синхронизация чатов: {now}. Чатов: {chats_saved}, сообщений: {messages_saved}. "
            f"API: {api_path}. БД: accountant.db (avito_chats, avito_messages)."
        ),
        source="system",
    )

    hint = ""
    if chats_saved == 0:
        try:
            probe = probe_api()
            err = (probe.get("messenger_chats") or {}).get("error") or ""
            if err:
                hint = err
        except Exception as e:
            hint = str(e)[:200]

    return {
        "ok": True,
        "user_id": uid,
        "account_name": profile.get("name", ""),
        "chats_saved": chats_saved,
        "messages_saved": messages_saved,
        "api_path": api_path,
        "synced_at": now,
        "hint": hint,
    }


def get_account_from_db() -> dict | None:
    init_messenger_tables()
    uid = (_cfg().get("user_id") or "").strip()
    if not uid:
        return None
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM avito_account WHERE user_id = ?", (uid,)
        ).fetchone()
    return dict(row) if row else None


def get_chats_from_db(
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> dict:
    init_messenger_tables()
    uid = (_cfg().get("user_id") or "").strip() or _user_id()
    q = "SELECT * FROM avito_chats WHERE user_id = ?"
    params: list[Any] = [uid]
    if search and search.strip():
        s = f"%{search.strip()}%"
        q += " AND (counterpart_name LIKE ? OR item_title LIKE ? OR last_message_text LIKE ?)"
        params.extend([s, s, s])
    q += " ORDER BY last_message_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(q, params).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM avito_chats WHERE user_id = ?", (uid,)
        ).fetchone()[0]

    return {
        "user_id": uid,
        "total": total,
        "chats": [dict(r) for r in rows],
        "last_sync_at": _meta_get("last_chats_sync_at"),
    }


def get_messages_from_db(chat_id: str, *, limit: int = 100, offset: int = 0) -> dict:
    init_messenger_tables()
    uid = (_cfg().get("user_id") or "").strip() or _user_id()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM avito_messages
            WHERE user_id = ? AND chat_id = ?
            ORDER BY created_at ASC
            LIMIT ? OFFSET ?
            """,
            (uid, chat_id, limit, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM avito_messages WHERE user_id = ? AND chat_id = ?",
            (uid, chat_id),
        ).fetchone()[0]
    return {"chat_id": chat_id, "total": total, "messages": [dict(r) for r in rows]}


def archive_stats() -> dict:
    init_messenger_tables()
    uid = (_cfg().get("user_id") or "").strip()
    chats = msgs = 0
    if uid:
        with sqlite3.connect(DB_PATH) as conn:
            chats = conn.execute(
                "SELECT COUNT(*) FROM avito_chats WHERE user_id = ?", (uid,)
            ).fetchone()[0]
            msgs = conn.execute(
                "SELECT COUNT(*) FROM avito_messages WHERE user_id = ?", (uid,)
            ).fetchone()[0]
    return {
        "chats_in_db": chats,
        "messages_in_db": msgs,
        "last_chats_sync_at": _meta_get("last_chats_sync_at"),
        "last_api_path": _meta_get("chats_api_path"),
    }


def probe_api() -> dict:
    """Диагностика: какие части API доступны с текущими ключами."""
    from modules.avito import _creds_ok

    out: dict[str, Any] = {
        "credentials": _creds_ok(_cfg()),
        "profile": {"ok": False, "error": ""},
        "messenger_chats": {"ok": False, "error": ""},
        "stats": {"ok": False, "error": ""},
        "archive": archive_stats(),
    }
    if not out["credentials"]:
        out["profile"]["error"] = "Нет Client ID / Secret"
        return out

    try:
        fetch_account_profile()
        out["profile"]["ok"] = True
    except Exception as e:
        out["profile"]["error"] = str(e)[:300]

    try:
        uid = _user_id()
        chats, path = _fetch_chats_page(uid, limit=1, offset=0)
        out["messenger_chats"]["ok"] = True
        out["messenger_chats"]["sample_count"] = len(chats)
        out["messenger_chats"]["api_path"] = path
    except Exception as e:
        out["messenger_chats"]["error"] = str(e)[:300]

    try:
        uid = _user_id()
        from datetime import date, timedelta

        day = (date.today() - timedelta(days=1)).isoformat()
        r = _request(
            "POST",
            f"/stats/v1/accounts/{uid}/items",
            json={
                "itemIds": [],
                "dateFrom": day,
                "dateTo": day,
                "periodGrouping": "day",
                "fields": ["uniqViews"],
            },
        )
        out["stats"]["ok"] = r.status_code not in (403, 404)
        out["stats"]["http"] = r.status_code
        if r.status_code in (403, 404):
            out["stats"]["error"] = (
                "Нет stats:read — статистика объявлений недоступна с этими правами"
            )
    except Exception as e:
        out["stats"]["error"] = str(e)[:300]

    return out


def capabilities_summary_text() -> str:
    """Краткий фактический ответ «что доступно по API Авито» — без инструкций для новичков."""
    from modules.avito import _creds_ok

    arch = archive_stats()
    creds = _creds_ok(_cfg())
    lines = [
        "В Jarvis по API Авито доступно:",
        "• OAuth2 — профиль аккаунта;",
        "• статистика объявлений (просмотры, контакты) в SQLite;",
        "• messenger — загрузка чатов и сообщений в архив;",
        "• анализ переписок по фразам (собеседование, адрес, телефон);",
        "• очистка архива чата после выгрузки.",
    ]
    if not creds:
        lines.append("Ключи не заданы — панель «Коннектор Авито» слева.")
    else:
        lines.append(
            f"В архиве сейчас: {arch.get('chats_in_db', 0)} чатов, "
            f"{arch.get('messages_in_db', 0)} сообщений."
        )
        lines.append(
            "Скажите: «скачай чаты авито» — загружу в архив автоматически (без bash и скриптов)."
        )
    return "\n".join(lines)


def format_chats_summary(limit: int = 15) -> str:
    data = get_chats_from_db(limit=limit)
    chats = data.get("chats") or []
    stats = archive_stats()
    lines = [
        f"Архив чатов Авито (локально): {stats['chats_in_db']} чатов, "
        f"{stats['messages_in_db']} сообщений.",
    ]
    if stats.get("last_chats_sync_at"):
        lines.append(f"Последняя синхронизация: {stats['last_chats_sync_at']}.")
    else:
        lines.append(
            "Чаты ещё не синхронизированы — вызовите sync_avito_chats или POST /api/avito/sync/chats."
        )
    if not chats:
        lines.append("В локальной БД пока нет чатов.")
        return "\n".join(lines)
    lines.append("Последние чаты:")
    for c in chats[:limit]:
        name = c.get("counterpart_name") or c.get("chat_id")
        item = c.get("item_title") or ""
        preview = (c.get("last_message_text") or "")[:80]
        lines.append(f"• {name}" + (f" · {item[:40]}" if item else "") + f" — {preview}")
    return "\n".join(lines)

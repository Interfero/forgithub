"""
Локальная память Авито (SQLite, accountant.db): каталог, статистика, чаты, HR-интервью.
Совместимость с таблицами avito.py / avito_messenger.py + расширения по ТЗ.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any

from modules.documents import DB_PATH, init_db

# Только эти таблицы доступны для execute_local_sql_query
ALLOWED_SQL_TABLES = frozenset(
    {
        "avito_items",
        "avito_stats",
        "avito_chats",
        "avito_messages",
        "avito_account",
        "avito_sync_meta",
        "extracted_interviews",
        "avito_chat_analysis",
        "avito_inbound_leads",
    }
)

_FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM)\b",
    re.I,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_avito_storage() -> None:
    """Все таблицы Авито + миграции колонок."""
    init_db()
    from modules.avito_messenger import init_messenger_tables

    init_messenger_tables()
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS avito_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                item_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                views INTEGER NOT NULL DEFAULT 0,
                favorites INTEGER NOT NULL DEFAULT 0,
                contacts INTEGER NOT NULL DEFAULT 0,
                spend REAL NOT NULL DEFAULT 0,
                UNIQUE(date, item_id)
            );
            CREATE INDEX IF NOT EXISTS idx_avito_stats_date ON avito_stats(date);
            CREATE INDEX IF NOT EXISTS idx_avito_stats_item ON avito_stats(item_id);

            CREATE TABLE IF NOT EXISTS avito_items (
                item_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                price REAL,
                status TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL DEFAULT '{}',
                synced_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_avito_items_status ON avito_items(status);

            CREATE TABLE IF NOT EXISTS extracted_interviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_name TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                visit_at TEXT NOT NULL DEFAULT '',
                chat_id TEXT NOT NULL DEFAULT '',
                item_id TEXT NOT NULL DEFAULT '',
                source_message_id TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}',
                extracted_at TEXT NOT NULL,
                UNIQUE(chat_id, source_message_id)
            );
            CREATE INDEX IF NOT EXISTS idx_extracted_interviews_visit ON extracted_interviews(visit_at);

            CREATE TABLE IF NOT EXISTS avito_inbound_leads (
                chat_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT '',
                item_id TEXT NOT NULL DEFAULT '',
                item_title TEXT NOT NULL DEFAULT '',
                counterpart_name TEXT NOT NULL DEFAULT '',
                first_message_at TEXT NOT NULL DEFAULT '',
                first_message_text TEXT NOT NULL DEFAULT '',
                synced_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_avito_inbound_item ON avito_inbound_leads(item_id);
            CREATE INDEX IF NOT EXISTS idx_avito_inbound_date ON avito_inbound_leads(first_message_at);
            """
        )
        _migrate_stats_inbound(conn)
        _migrate_messages_role(conn)
        _migrate_chats_read(conn)
    _meta_set("storage_schema", "2")


def _migrate_stats_inbound(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(avito_stats)").fetchall()}
    if "inbound_leads" not in cols:
        conn.execute(
            "ALTER TABLE avito_stats ADD COLUMN inbound_leads INTEGER NOT NULL DEFAULT 0"
        )


def _migrate_messages_role(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(avito_messages)").fetchall()}
    if "role" not in cols:
        conn.execute("ALTER TABLE avito_messages ADD COLUMN role TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """
        UPDATE avito_messages SET role = CASE
            WHEN direction = 'out' THEN 'self'
            WHEN direction = 'in' THEN 'counterpart'
            ELSE COALESCE(NULLIF(role, ''), 'counterpart')
        END
        WHERE role IS NULL OR role = ''
        """
    )


def _migrate_chats_read(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(avito_chats)").fetchall()}
    if "is_read" not in cols:
        conn.execute(
            "ALTER TABLE avito_chats ADD COLUMN is_read INTEGER NOT NULL DEFAULT 1"
        )
    conn.execute(
        """
        UPDATE avito_chats SET is_read = CASE
            WHEN unread_count > 0 THEN 0 ELSE 1
        END
        WHERE is_read IS NULL
        """
    )


def _meta_set(key: str, value: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO avito_sync_meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def _meta_get(key: str) -> str:
    init_avito_storage()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT value FROM avito_sync_meta WHERE key = ?", (key,)
        ).fetchone()
    return row[0] if row else ""


def last_full_sync_date() -> str:
    return _meta_get("last_full_sync_date")


def mark_full_sync_done() -> None:
    _meta_set("last_full_sync_date", date.today().isoformat())
    _meta_set("last_full_sync_at", _now_iso())


def upsert_item(row: dict[str, Any]) -> None:
    init_avito_storage()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO avito_items (
                item_id, user_id, title, description, price, status,
                category, url, raw_json, synced_at
            ) VALUES (
                :item_id, :user_id, :title, :description, :price, :status,
                :category, :url, :raw_json, :synced_at
            )
            ON CONFLICT(item_id) DO UPDATE SET
                user_id=excluded.user_id,
                title=excluded.title,
                description=excluded.description,
                price=excluded.price,
                status=excluded.status,
                category=excluded.category,
                url=excluded.url,
                raw_json=excluded.raw_json,
                synced_at=excluded.synced_at
            """,
            row,
        )


def upsert_stat_row(
    day: str,
    item_id: str,
    title: str,
    *,
    views: int = 0,
    favorites: int = 0,
    contacts: int = 0,
    spend: float = 0.0,
    inbound_leads: int | None = None,
) -> None:
    init_avito_storage()
    with sqlite3.connect(DB_PATH) as conn:
        if inbound_leads is None:
            conn.execute(
                """
                INSERT INTO avito_stats (date, item_id, title, views, favorites, contacts, spend)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, item_id) DO UPDATE SET
                    title=excluded.title,
                    views=excluded.views,
                    favorites=excluded.favorites,
                    contacts=excluded.contacts,
                    spend=excluded.spend
                """,
                (day, str(item_id), title, views, favorites, contacts, spend),
            )
        else:
            conn.execute(
                """
                INSERT INTO avito_stats (
                    date, item_id, title, views, favorites, contacts, spend, inbound_leads
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, item_id) DO UPDATE SET
                    title=excluded.title,
                    views=excluded.views,
                    favorites=excluded.favorites,
                    contacts=excluded.contacts,
                    spend=excluded.spend,
                    inbound_leads=excluded.inbound_leads
                """,
                (day, str(item_id), title, views, favorites, contacts, spend, inbound_leads),
            )


def upsert_interview(row: dict[str, Any]) -> None:
    init_avito_storage()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO extracted_interviews (
                candidate_name, phone, visit_at, chat_id, item_id,
                source_message_id, confidence, raw_json, extracted_at
            ) VALUES (
                :candidate_name, :phone, :visit_at, :chat_id, :item_id,
                :source_message_id, :confidence, :raw_json, :extracted_at
            )
            ON CONFLICT(chat_id, source_message_id) DO UPDATE SET
                candidate_name=excluded.candidate_name,
                phone=excluded.phone,
                visit_at=excluded.visit_at,
                item_id=excluded.item_id,
                confidence=excluded.confidence,
                raw_json=excluded.raw_json,
                extracted_at=excluded.extracted_at
            """,
            row,
        )


def item_titles_from_chats() -> dict[str, str]:
    """Заголовки объявлений из архива чатов Messenger."""
    init_avito_storage()
    out: dict[str, str] = {}
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT item_id, item_title FROM avito_chats
            WHERE item_id != '' AND item_title != ''
            GROUP BY item_id
            """
        ).fetchall()
    for iid, title in rows:
        out[str(iid)] = str(title)[:500]
    return out


def sync_inbound_leads_from_messages() -> dict[str, Any]:
    """
    Отклики: чаты, где первое сообщение — от соискателя (direction=in / role=counterpart).
    Сохраняет в avito_inbound_leads и обновляет avito_stats.inbound_leads по дням.
    """
    init_avito_storage()
    now = _now_iso()
    leads: list[dict[str, Any]] = []

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        chats = conn.execute(
            "SELECT user_id, chat_id, item_id, item_title, counterpart_name FROM avito_chats"
        ).fetchall()
        for chat in chats:
            first = conn.execute(
                """
                SELECT direction, role, created_at, text
                FROM avito_messages
                WHERE chat_id = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (chat["chat_id"],),
            ).fetchone()
            if not first:
                continue
            direction = (first["direction"] or "").lower()
            role = (first["role"] or "").lower()
            if direction not in ("in",) and role not in ("counterpart",):
                continue
            leads.append(
                {
                    "chat_id": chat["chat_id"],
                    "user_id": chat["user_id"] or "",
                    "item_id": chat["item_id"] or "",
                    "item_title": chat["item_title"] or "",
                    "counterpart_name": chat["counterpart_name"] or "",
                    "first_message_at": (first["created_at"] or "")[:32],
                    "first_message_text": (first["text"] or "")[:2000],
                    "synced_at": now,
                }
            )

        conn.execute("DELETE FROM avito_inbound_leads")
        for row in leads:
            conn.execute(
                """
                INSERT INTO avito_inbound_leads (
                    chat_id, user_id, item_id, item_title, counterpart_name,
                    first_message_at, first_message_text, synced_at
                ) VALUES (
                    :chat_id, :user_id, :item_id, :item_title, :counterpart_name,
                    :first_message_at, :first_message_text, :synced_at
                )
                """,
                row,
            )

        conn.execute("UPDATE avito_stats SET inbound_leads = 0")
        daily = conn.execute(
            """
            SELECT SUBSTR(first_message_at, 1, 10) AS day, item_id, COUNT(*) AS cnt
            FROM avito_inbound_leads
            WHERE item_id != '' AND first_message_at != ''
            GROUP BY day, item_id
            """
        ).fetchall()
        for row in daily:
            day = row["day"]
            iid = str(row["item_id"])
            cnt = int(row["cnt"] or 0)
            title_row = conn.execute(
                "SELECT title FROM avito_stats WHERE item_id = ? AND title != '' LIMIT 1",
                (iid,),
            ).fetchone()
            title = (title_row[0] if title_row else "") or iid
            conn.execute(
                """
                INSERT INTO avito_stats (
                    date, item_id, title, views, favorites, contacts, spend, inbound_leads
                ) VALUES (?, ?, ?, 0, 0, 0, 0, ?)
                ON CONFLICT(date, item_id) DO UPDATE SET inbound_leads = excluded.inbound_leads
                """,
                (day, iid, title, cnt),
            )

    return {"ok": True, "count": len(leads)}


def storage_summary() -> dict[str, Any]:
    init_avito_storage()
    with sqlite3.connect(DB_PATH) as conn:
        items = conn.execute("SELECT COUNT(*) FROM avito_items").fetchone()[0]
        stats = conn.execute("SELECT COUNT(*) FROM avito_stats").fetchone()[0]
        chats = conn.execute("SELECT COUNT(*) FROM avito_chats").fetchone()[0]
        msgs = conn.execute("SELECT COUNT(*) FROM avito_messages").fetchone()[0]
        interviews = conn.execute("SELECT COUNT(*) FROM extracted_interviews").fetchone()[0]
        inbound = conn.execute("SELECT COUNT(*) FROM avito_inbound_leads").fetchone()[0]
    return {
        "items": items,
        "stats_rows": stats,
        "chats": chats,
        "messages": msgs,
        "interviews": interviews,
        "inbound_leads": inbound,
        "last_full_sync_date": last_full_sync_date(),
        "last_full_sync_at": _meta_get("last_full_sync_at"),
    }


def execute_local_sql_query(query: str, *, max_rows: int = 200) -> dict[str, Any]:
    """
    Только SELECT к разрешённым таблицам avito_* / extracted_interviews.
    """
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "Пустой SQL-запрос"}
    if ";" in q.rstrip().rstrip(";"):
        return {"ok": False, "error": "Один запрос без «;» в середине"}
    if _FORBIDDEN_SQL.search(q):
        return {"ok": False, "error": "Разрешены только SELECT-запросы"}
    if not re.match(r"^\s*SELECT\b", q, re.I):
        return {"ok": False, "error": "Запрос должен начинаться с SELECT"}
    tables = set(re.findall(r"\bFROM\s+([a-z_][a-z0-9_]*)", q, re.I))
    tables |= set(re.findall(r"\bJOIN\s+([a-z_][a-z0-9_]*)", q, re.I))
    bad = [t for t in tables if t.lower() not in ALLOWED_SQL_TABLES]
    if bad:
        return {
            "ok": False,
            "error": f"Таблицы не из белого списка: {', '.join(bad)}",
            "allowed": sorted(ALLOWED_SQL_TABLES),
        }
    limit = max(1, min(int(max_rows), 500))
    q_lim = q if re.search(r"\bLIMIT\b", q, re.I) else f"{q} LIMIT {limit}"

    init_avito_storage()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(q_lim)
            rows = [dict(r) for r in cur.fetchmany(limit + 1)]
    except sqlite3.Error as e:
        return {"ok": False, "error": str(e)[:500]}

    truncated = len(rows) > limit
    if truncated:
        rows = rows[:limit]
    return {
        "ok": True,
        "rows": rows,
        "count": len(rows),
        "truncated": truncated,
    }


def messages_for_hr_mining(
    *,
    hours: int = 48,
    limit: int = 400,
) -> list[dict[str, Any]]:
    """Сообщения собеседника за последние N часов."""
    init_avito_storage()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT m.chat_id, m.message_id, m.text, m.created_at, m.role,
                   c.counterpart_name, c.item_id, c.item_title
            FROM avito_messages m
            JOIN avito_chats c ON c.chat_id = m.chat_id AND c.user_id = m.user_id
            WHERE (m.role = 'counterpart' OR m.direction = 'in')
              AND m.text != ''
              AND m.created_at >= ?
            ORDER BY m.created_at DESC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def stats_aggregate(date_from: str, date_to: str) -> dict[str, Any]:
    init_avito_storage()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT item_id, title,
                   SUM(views) AS views,
                   SUM(contacts) AS contacts,
                   SUM(favorites) AS favorites,
                   SUM(inbound_leads) AS inbound_leads,
                   SUM(spend) AS spend
            FROM avito_stats
            WHERE date >= ? AND date <= ?
            GROUP BY item_id, title
            ORDER BY views DESC
            """,
            (date_from, date_to),
        ).fetchall()
        daily = conn.execute(
            """
            SELECT date,
                   SUM(views) AS views,
                   SUM(contacts) AS contacts,
                   SUM(favorites) AS favorites,
                   SUM(inbound_leads) AS inbound_leads
            FROM avito_stats
            WHERE date >= ? AND date <= ?
            GROUP BY date
            ORDER BY date
            """,
            (date_from, date_to),
        ).fetchall()
    items = [dict(r) for r in rows]
    for it in items:
        v = int(it.get("views") or 0)
        c = int(it.get("contacts") or 0)
        it["ctr_pct"] = round(100.0 * c / v, 2) if v else 0.0
    totals_v = sum(int(x.get("views") or 0) for x in items)
    totals_c = sum(int(x.get("contacts") or 0) for x in items)
    totals_f = sum(int(x.get("favorites") or 0) for x in items)
    totals_in = sum(int(x.get("inbound_leads") or 0) for x in items)
    avg_ctr = round(100.0 * totals_c / totals_v, 2) if totals_v else 0.0
    return {
        "date_from": date_from,
        "date_to": date_to,
        "items": items,
        "daily": [dict(r) for r in daily],
        "totals": {
            "views": totals_v,
            "contacts": totals_c,
            "favorites": totals_f,
            "inbound_leads": totals_in,
            "avg_ctr_pct": avg_ctr,
        },
    }


def items_with_stats(date_from: str, date_to: str) -> list[dict[str, Any]]:
    init_avito_storage()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT i.item_id, i.title, i.description, i.price, i.status, i.category, i.url,
                   COALESCE(SUM(s.views), 0) AS views,
                   COALESCE(SUM(s.contacts), 0) AS contacts,
                   COALESCE(SUM(s.favorites), 0) AS favorites
            FROM avito_items i
            LEFT JOIN avito_stats s ON s.item_id = i.item_id
                AND s.date >= ? AND s.date <= ?
            GROUP BY i.item_id
            """,
            (date_from, date_to),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        v = int(d.get("views") or 0)
        c = int(d.get("contacts") or 0)
        d["ctr_pct"] = round(100.0 * c / v, 2) if v else 0.0
        out.append(d)
    return out

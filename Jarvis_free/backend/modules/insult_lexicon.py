"""
Словарь оскорблений Jarvis в jarvis.db (до 10 000 активных записей).
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from modules.jarvis_db import _connect, init_db

MAX_LEXICON_SLOTS = 10_000
MIN_SEED_COUNT = 100

_word_cache: set[str] | None = None
_phrase_cache: tuple[str, ...] | None = None

_TOKEN_RE = re.compile(r"[а-яёa-z0-9]+", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    return (text or "").lower().replace("ё", "е").strip()


def ensure_lexicon_table() -> None:
    init_db()
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS insult_lexicon (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phrase TEXT NOT NULL,
                normalized TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'rude',
                source TEXT NOT NULL DEFAULT 'seed',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(normalized)
            );
            CREATE INDEX IF NOT EXISTS idx_insult_lexicon_active
                ON insult_lexicon(active);
            CREATE INDEX IF NOT EXISTS idx_insult_lexicon_normalized
                ON insult_lexicon(normalized);
            """
        )


def _active_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM insult_lexicon WHERE active = 1"
    ).fetchone()
    return int(row["c"] if row else 0)


def reload_lexicon_cache() -> None:
    global _word_cache, _phrase_cache
    ensure_lexicon_table()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT normalized FROM insult_lexicon
            WHERE active = 1
            ORDER BY LENGTH(normalized) DESC
            """
        ).fetchall()
    words: set[str] = set()
    phrases: list[str] = []
    for row in rows:
        norm = str(row["normalized"] or "")
        if not norm:
            continue
        if " " in norm:
            phrases.append(norm)
        else:
            words.add(norm)
    _word_cache = words
    _phrase_cache = tuple(phrases)


def _word_set() -> set[str]:
    if _word_cache is None:
        reload_lexicon_cache()
    return _word_cache or set()


def _phrase_list() -> tuple[str, ...]:
    if _phrase_cache is None:
        reload_lexicon_cache()
    return _phrase_cache or ()


def seed_lexicon_if_needed() -> int:
    """Заполнить словарь начальными фразами, если записей меньше MIN_SEED_COUNT."""
    from modules.insult_lexicon_seed import SEED_PHRASES

    ensure_lexicon_table()
    added = 0
    with _connect() as conn:
        if _active_count(conn) >= MIN_SEED_COUNT:
            return 0
        now = _now()
        for raw in SEED_PHRASES:
            if _active_count(conn) >= MAX_LEXICON_SLOTS:
                break
            phrase = raw.strip()
            if len(phrase) < 2:
                continue
            norm = _normalize(phrase)
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO insult_lexicon
                    (phrase, normalized, category, source, active, created_at)
                    VALUES (?, ?, 'rude', 'seed', 1, ?)
                    """,
                    (phrase, norm, now),
                )
                if conn.total_changes:
                    added += 1
            except sqlite3.Error:
                pass
        conn.commit()
    reload_lexicon_cache()
    return added


def ensure_lexicon_ready() -> None:
    ensure_lexicon_table()
    seed_lexicon_if_needed()
    reload_lexicon_cache()


def lexicon_hits(text: str) -> list[str]:
    """Совпадения с активным словарём (слова и многословные фразы)."""
    t = _normalize(text)
    if len(t) < 2:
        return []
    hits: list[str] = []
    seen: set[str] = set()
    for tok in _TOKEN_RE.findall(t):
        n = _normalize(tok)
        if n in _word_set() and n not in seen:
            seen.add(n)
            hits.append(n)
    for phrase in _phrase_list():
        if phrase in t and phrase not in seen:
            seen.add(phrase)
            hits.append(phrase)
    return hits


def message_matches_lexicon(text: str) -> bool:
    return bool(lexicon_hits(text))


def bulk_import_phrases(
    items: list[tuple[str, str]],
    *,
    max_total: int = MAX_LEXICON_SLOTS,
    category: str = "rude",
) -> dict[str, int]:
    """Пакетная загрузка (source = rbw / tg / import_*)."""
    ensure_lexicon_table()
    added = 0
    skipped = 0
    duplicate = 0
    now = _now()
    with _connect() as conn:
        active = _active_count(conn)
        for raw, source in items:
            if active >= max_total:
                skipped += 1
                continue
            phrase = (raw or "").strip()
            if len(phrase) < 2 or len(phrase) > 80:
                skipped += 1
                continue
            norm = _normalize(phrase)
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO insult_lexicon
                    (phrase, normalized, category, source, active, created_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (phrase, norm, category, source[:32], now),
                )
                if conn.total_changes:
                    added += 1
                    active += 1
                else:
                    duplicate += 1
            except sqlite3.Error:
                skipped += 1
        conn.commit()
    reload_lexicon_cache()
    with _connect() as conn2:
        active_after = _active_count(conn2)
    return {
        "added": added,
        "duplicate": duplicate,
        "skipped": skipped,
        "active": active_after,
    }


def add_lexicon_entry(
    phrase: str,
    *,
    source: str = "skill",
    category: str = "rude",
) -> tuple[bool, str]:
    raw = (phrase or "").strip()
    if len(raw) < 2:
        return False, "Фраза слишком короткая (минимум 2 символа)."
    if len(raw) > 160:
        return False, "Фраза слишком длинная (максимум 160 символов)."
    norm = _normalize(raw)
    ensure_lexicon_table()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT id, active FROM insult_lexicon WHERE normalized = ?",
            (norm,),
        ).fetchone()
        if existing:
            if int(existing["active"] or 0) == 1:
                reload_lexicon_cache()
                return True, f"«{raw}» уже есть в словаре оскорблений."
            conn.execute(
                """
                UPDATE insult_lexicon
                SET phrase = ?, active = 1, source = ?, category = ?, created_at = ?
                WHERE id = ?
                """,
                (raw, source, category, _now(), existing["id"]),
            )
            conn.commit()
            reload_lexicon_cache()
            return True, f"«{raw}» снова активировано в словаре."

        if _active_count(conn) >= MAX_LEXICON_SLOTS:
            return (
                False,
                f"Словарь заполнен ({MAX_LEXICON_SLOTS} записей). "
                "Удалите или деактивируйте старые записи.",
            )
        conn.execute(
            """
            INSERT INTO insult_lexicon
            (phrase, normalized, category, source, active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (raw, norm, category, source, _now()),
        )
        conn.commit()
    reload_lexicon_cache()
    stats = lexicon_stats_dict()
    return (
        True,
        f"Добавлено в словарь: «{raw}». "
        f"Занято {stats['active']}/{MAX_LEXICON_SLOTS} слотов.",
    )


def lexicon_stats_dict() -> dict[str, Any]:
    ensure_lexicon_table()
    with _connect() as conn:
        active = _active_count(conn)
        total = conn.execute("SELECT COUNT(*) AS c FROM insult_lexicon").fetchone()
    total_n = int(total["c"] if total else 0)
    return {
        "active": active,
        "total": total_n,
        "capacity": MAX_LEXICON_SLOTS,
        "free_slots": max(0, MAX_LEXICON_SLOTS - active),
    }


def lexicon_stats() -> str:
    ensure_lexicon_ready()
    s = lexicon_stats_dict()
    return (
        f"Словарь оскорблений Jarvis: {s['active']} активных из {s['capacity']} слотов "
        f"(всего записей в БД: {s['total']}, свободно: {s['free_slots']})."
    )

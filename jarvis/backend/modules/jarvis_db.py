"""
Единая SQLite-база Jarvis: режимы чатов, тексты предобучения, расширяемые ячейки.
Файл: backend/data/jarvis.db
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.app_paths import user_data_dir

DATA_DIR = user_data_dir()
DB_PATH = DATA_DIR / "jarvis.db"

# store_key → (mode_code | None, disk store id)
STORE_META: dict[str, tuple[str | None, str]] = {
    "unconscious": (None, "unconscious"),
    "conscious": ("standard", "conscious"),
    "mode_accountant": ("accountant", "mode-accountant"),
    "mode_marketer": ("marketer", "mode-marketer"),
    "mode_developer": ("developer", "mode-developer"),
}

CHAT_MODES = [
    ("standard", "Стандартный чат", 0),
    ("accountant", "Бухгалтер + Юрист", 1),
    ("marketer", "Маркетолог+Дизайнер", 1),
    ("developer", "Разработчик", 1),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_modes (
                code TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                is_profession INTEGER NOT NULL DEFAULT 0,
                isolated INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_stores (
                store_key TEXT PRIMARY KEY,
                mode_code TEXT,
                disk_store TEXT NOT NULL,
                label TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (mode_code) REFERENCES chat_modes(code) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS memory_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_key TEXT NOT NULL,
                mode_code TEXT,
                filename TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                size_bytes INTEGER NOT NULL DEFAULT 0,
                file_path TEXT,
                protected INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(store_key, filename),
                FOREIGN KEY (store_key) REFERENCES memory_stores(store_key) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS memory_cells (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode_code TEXT,
                namespace TEXT NOT NULL DEFAULT 'default',
                cell_key TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'system',
                UNIQUE(mode_code, namespace, cell_key)
            );

            CREATE INDEX IF NOT EXISTS idx_memory_files_store ON memory_files(store_key);
            CREATE INDEX IF NOT EXISTS idx_memory_files_mode ON memory_files(mode_code);
            CREATE INDEX IF NOT EXISTS idx_memory_cells_mode ON memory_cells(mode_code);

            CREATE TABLE IF NOT EXISTS menu_search_cells (
                cell_id TEXT PRIMARY KEY,
                cell_type TEXT NOT NULL,
                block_id TEXT,
                section_dom_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                label TEXT NOT NULL,
                search_text TEXT NOT NULL,
                path_json TEXT NOT NULL,
                weight INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'catalog',
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_menu_search_text ON menu_search_cells(search_text);
            CREATE INDEX IF NOT EXISTS idx_menu_search_section ON menu_search_cells(section_dom_id);
            CREATE INDEX IF NOT EXISTS idx_menu_search_block ON menu_search_cells(block_id);
            CREATE INDEX IF NOT EXISTS idx_menu_search_type ON menu_search_cells(cell_type);

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
            CREATE INDEX IF NOT EXISTS idx_insult_lexicon_active ON insult_lexicon(active);
            CREATE INDEX IF NOT EXISTS idx_insult_lexicon_normalized ON insult_lexicon(normalized);
            """
        )
        now = _now()
        for code, label, is_prof in CHAT_MODES:
            conn.execute(
                """
                INSERT OR IGNORE INTO chat_modes (code, label, is_profession, isolated, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (code, label, is_prof, now),
            )
        conn.execute(
            "UPDATE chat_modes SET isolated = 0 WHERE code = 'standard'"
        )
        stores = [
            (
                "unconscious",
                None,
                "unconscious",
                "Бессознательное",
                "Базовые правила поведения ИИ во всех режимах",
            ),
            (
                "conscious",
                "standard",
                "conscious",
                "Сознательное",
                "Личные настройки — только стандартный чат",
            ),
            (
                "mode_accountant",
                "accountant",
                "mode-accountant",
                "Бухгалтер + Юрист",
                "Предобучение режима бухгалтера (изолировано)",
            ),
            (
                "mode_marketer",
                "marketer",
                "mode-marketer",
                "Маркетолог+Дизайнер",
                "Предобучение маркетолога (изолировано)",
            ),
            (
                "mode_developer",
                "developer",
                "mode-developer",
                "Разработчик",
                "Предобучение режима разработчика (изолировано)",
            ),
        ]
        for row in stores:
            conn.execute(
                """
                INSERT OR IGNORE INTO memory_stores
                (store_key, mode_code, disk_store, label, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                row,
            )


def disk_store_to_key(disk_store: str) -> str:
    mapping = {
        "conscious": "conscious",
        "unconscious": "unconscious",
        "mode-standard": "conscious",
        "mode-accountant": "mode_accountant",
        "mode-marketer": "mode_marketer",
        "mode-developer": "mode_developer",
    }
    return mapping.get(disk_store, disk_store.replace("-", "_"))


def upsert_file_from_disk(
    disk_store: str,
    filename: str,
    content: str,
    *,
    protected: bool = False,
    file_path: str | None = None,
) -> None:
    store_key = disk_store_to_key(disk_store)
    mode_code, _ = STORE_META.get(store_key, (None, disk_store))
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO memory_files
            (store_key, mode_code, filename, content, size_bytes, file_path, protected, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(store_key, filename) DO UPDATE SET
                content = excluded.content,
                size_bytes = excluded.size_bytes,
                file_path = excluded.file_path,
                protected = excluded.protected,
                updated_at = excluded.updated_at
            """,
            (
                store_key,
                mode_code,
                filename,
                content,
                len(content.encode("utf-8")),
                file_path,
                1 if protected else 0,
                now,
            ),
        )


def delete_file(disk_store: str, filename: str) -> None:
    store_key = disk_store_to_key(disk_store)
    with _connect() as conn:
        conn.execute(
            "DELETE FROM memory_files WHERE store_key = ? AND filename = ?",
            (store_key, Path(filename).name),
        )


def read_store_text(
    disk_store: str,
    max_chars: int = 12000,
    *,
    exclude_filenames: frozenset[str] | None = None,
) -> str:
    store_key = disk_store_to_key(disk_store)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT filename, content FROM memory_files
            WHERE store_key = ? ORDER BY filename
            """,
            (store_key,),
        ).fetchall()
    parts: list[str] = []
    total = 0
    skip = exclude_filenames or frozenset()
    for row in rows:
        if row["filename"] in skip:
            continue
        text = (row["content"] or "").strip()
        if not text:
            continue
        chunk = f"### {row['filename']}\n{text}"
        if total + len(chunk) > max_chars:
            parts.append(chunk[: max_chars - total] + "…")
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n".join(parts)


def mode_has_training_files(mode_code: str) -> bool:
    ctx = read_context_for_mode(mode_code, max_chars=500)
    if mode_code == "standard":
        return bool(ctx["conscious"].strip())
    return bool(ctx["mode"].strip())


def read_context_for_mode(mode_value: str, max_chars: int = 6000) -> dict[str, str]:
    """Контекст с изоляцией профессиональных режимов."""
    from modules.memory_store import INTERNAL_UNCONSCIOUS_FILES

    out: dict[str, str] = {
        "unconscious": read_store_text(
            "unconscious",
            max_chars=max_chars,
            exclude_filenames=INTERNAL_UNCONSCIOUS_FILES,
        ),
        "conscious": "",
        "mode": "",
    }
    if mode_value == "standard":
        from modules.memory_store import STEREOTYPES_FILENAMES

        out["conscious"] = read_store_text(
            "conscious",
            max_chars=max_chars,
            exclude_filenames=STEREOTYPES_FILENAMES,
        )
    elif mode_value == "accountant":
        out["mode"] = read_store_text("mode-accountant", max_chars=max_chars)
    elif mode_value == "marketer":
        out["mode"] = read_store_text("mode-marketer", max_chars=max_chars)
    elif mode_value == "developer":
        out["mode"] = read_store_text("mode-developer", max_chars=max_chars)
    return out


def set_cell(
    *,
    mode_code: str | None,
    namespace: str,
    cell_key: str,
    content: str,
    source: str = "user",
) -> dict:
    """Расширяемая ячейка — пользователь или команда из чата."""
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO memory_cells (mode_code, namespace, cell_key, content, updated_at, source)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(mode_code, namespace, cell_key) DO UPDATE SET
                content = excluded.content,
                updated_at = excluded.updated_at,
                source = excluded.source
            """,
            (mode_code, namespace, cell_key, content, now, source),
        )
    return {"ok": True, "mode_code": mode_code, "cell_key": cell_key}


def list_cells(
    namespace: str = "default",
    mode_code: str | None = None,
) -> list[dict[str, str]]:
    with _connect() as conn:
        if mode_code is None:
            rows = conn.execute(
                """
                SELECT cell_key, content, updated_at FROM memory_cells
                WHERE namespace = ? AND mode_code IS NULL
                ORDER BY updated_at DESC
                """,
                (namespace,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT cell_key, content, updated_at FROM memory_cells
                WHERE namespace = ? AND mode_code = ?
                ORDER BY updated_at DESC
                """,
                (namespace, mode_code),
            ).fetchall()
    return [
        {
            "cell_key": str(row["cell_key"]),
            "content": str(row["content"]),
            "updated_at": str(row["updated_at"]),
        }
        for row in rows
    ]


def read_cells_text(mode_code: str | None, namespace: str = "default", max_chars: int = 4000) -> str:
    rows = list_cells(namespace=namespace, mode_code=mode_code)
    parts = []
    total = 0
    for row in rows:
        chunk = f"### {row['cell_key']}\n{row['content']}"
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n".join(parts)


def training_context_for_router(mode_value: str, preview_chars: int = 400) -> str:
    """Краткая сводка предобучения для роутера Qwen (файлы на диске / в БД)."""
    has = mode_has_training_files(mode_value)
    if mode_value == "standard":
        if not has:
            return "Предобучение стандартного чата (сознательное): файлов нет."
        ctx = read_context_for_mode("standard", max_chars=preview_chars)
        preview = (ctx["conscious"] or "").strip()[:preview_chars]
        return (
            "Предобучение стандартного чата: файлы есть.\n"
            f"Начало сознательного:\n{preview or '—'}"
        )
    if mode_value not in ("accountant", "marketer", "developer"):
        return "Предобучение режима: не применимо."
    if not has:
        return f"Предобучение режима «{mode_value}»: файлов нет (режим ведёт себя как стандартный)."
    ctx = read_context_for_mode(mode_value, max_chars=preview_chars)
    preview = (ctx["mode"] or "").strip()[:preview_chars]
    return (
        f"Предобучение режима «{mode_value}»: файлы есть — Qwen и облако должны опираться на них.\n"
        f"Начало текста:\n{preview or '—'}"
    )


def sync_all_from_disk() -> int:
    """Синхронизация файлов с диска в БД (при старте, exe-сборке и после загрузки)."""
    from modules import memory_store

    init_db()
    memory_store._ensure_dirs()
    count = 0
    for disk_store in memory_store.STORE_DIRS:
        for meta in memory_store.list_files(disk_store):
            data = memory_store.read_file(disk_store, meta["name"])
            if not data:
                continue
            upsert_file_from_disk(
                disk_store,
                meta["name"],
                data["content"],
                protected=memory_store.is_protected(disk_store, meta["name"]),
                file_path=str(memory_store.STORE_DIRS[disk_store] / meta["name"]),
            )
            count += 1
    return count


def sync_db_to_disk() -> int:
    """Восстановить на диск файлы из БД, если их удалили вручную (не затирает существующие)."""
    from modules import memory_store

    init_db()
    memory_store._ensure_dirs()
    restored = 0
    with _connect() as conn:
        rows = conn.execute(
            "SELECT store_key, filename, content FROM memory_files ORDER BY store_key, filename"
        ).fetchall()
    for row in rows:
        meta = STORE_META.get(row["store_key"])
        if not meta:
            continue
        disk_store = meta[1]
        if disk_store not in memory_store.STORE_DIRS:
            continue
        d = memory_store.STORE_DIRS[disk_store]
        path = d / Path(row["filename"]).name
        if path.exists():
            continue
        content = (row["content"] or "").strip()
        if not content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        restored += 1
    return restored


def get_schema_summary() -> dict[str, Any]:
    with _connect() as conn:
        modes = [dict(r) for r in conn.execute("SELECT * FROM chat_modes ORDER BY code")]
        stores = [dict(r) for r in conn.execute("SELECT * FROM memory_stores ORDER BY store_key")]
        file_counts = {
            row["store_key"]: row["c"]
            for row in conn.execute(
                "SELECT store_key, COUNT(*) as c FROM memory_files GROUP BY store_key"
            )
        }
    return {"modes": modes, "stores": stores, "file_counts": file_counts, "db_path": str(DB_PATH)}

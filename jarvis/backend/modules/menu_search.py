"""
Индекс поиска по меню настроек Jarvis — отдельная ячейка в jarvis.db на каждый
пункт, блок и поисковое слово (приоритет у названий блоков).
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from modules.jarvis_db import _connect, init_db
from modules.keyboard_layout import latin_to_ru_phonetic, ru_to_latin_phonetic, search_query_variants

# Держите в синхроне с frontend/src/lib/settingsMenu.ts (SETTINGS_NAV_GROUPS)
MENU_NAV_GROUPS: list[dict[str, Any]] = [
    {
        "block_id": "appearance",
        "label": "Оформление",
        "section_dom_id": "settings-block-appearance",
        "keywords": ["тема", "светлая", "тёмная", "оформление"],
        "children": [],
    },
    {
        "block_id": "core",
        "label": "Ядро Jarvis",
        "section_dom_id": "settings-block-core",
        "keywords": ["ядро", "jarvis", "стандарт"],
        "children": [
            {
                "label": "Qwen 2.5 14B",
                "section_dom_id": "settings-section-qwen",
                "focus": "qwen",
                "keywords": ["qwen", "озу", "ram", "локаль", "нейросеть", "gguf"],
            },
            {
                "label": "DeepSeek",
                "section_dom_id": "settings-section-deepseek",
                "focus": "deepseek",
                "keywords": ["deepseek", "sk-", "бухгалтер", "облако"],
            },
        ],
    },
    {
        "block_id": "api-modes",
        "label": "API для режимов",
        "section_dom_id": "settings-block-api-modes",
        "keywords": ["api", "ключ", "режим"],
        "children": [
            {
                "label": "Perplexity",
                "section_dom_id": "settings-section-perplexity",
                "focus": "perplexity",
                "keywords": ["perplexity", "pplx", "разработчик", "код"],
            },
            {
                "label": "Ideogram",
                "section_dom_id": "settings-section-ideogram",
                "focus": "ideogram",
                "keywords": ["ideogram", "ideogram.ai", "картин", "изображен", "логотип"],
            },
            {
                "label": "Nano Banana",
                "section_dom_id": "settings-section-nanobanana",
                "focus": "nanobanana",
                "keywords": ["nano", "banana", "google", "картин", "маркетолог", "aiza"],
            },
            {
                "label": "OpenAI",
                "section_dom_id": "settings-section-openai",
                "keywords": ["openai", "chatgpt", "gpt"],
            },
            {
                "label": "Grok (xAI)",
                "section_dom_id": "settings-section-xai",
                "keywords": ["grok", "xai"],
            },
        ],
    },
    {
        "block_id": "voice",
        "label": "Голос и озвучка",
        "section_dom_id": "settings-block-voice",
        "keywords": ["голос", "озвучка", "студия"],
        "children": [
            {
                "label": "Silero TTS",
                "section_dom_id": "settings-section-voice",
                "keywords": ["silero", "голос", "озвучка", "tts", "aidar"],
            },
        ],
    },
    {
        "block_id": "telephony",
        "label": "Телефония",
        "section_dom_id": "settings-block-telephony",
        "keywords": ["телефон", "атс", "mango", "zadarma", "звонок"],
        "children": [
            {
                "label": "Входящие звонки",
                "section_dom_id": "settings-section-telephony",
                "focus": "telephony",
                "keywords": ["mango", "zadarma", "webhook", "приветствие"],
            },
        ],
    },
    {
        "block_id": "mail",
        "label": "Почтовый клиент",
        "section_dom_id": "settings-block-mail",
        "keywords": ["почта", "email", "imap", "gmail", "ящик", "письм"],
        "children": [
            {
                "label": "Почтовые ящики",
                "section_dom_id": "settings-section-mail",
                "focus": "mail",
                "keywords": ["imap", "gmail", "yandex", "mail.ru", "логин"],
            },
        ],
    },
    {
        "block_id": "hf",
        "label": "Навыки Hugging Face",
        "section_dom_id": "settings-block-hf",
        "keywords": ["huggingface", "hf", "модель", "gguf", "навык", "hub"],
        "children": [
            {
                "label": "Поиск и установка",
                "section_dom_id": "settings-section-hf",
                "focus": "hf",
                "keywords": ["скачать", "download", "dataset", "space"],
            },
        ],
    },
    {
        "block_id": "telegram",
        "label": "Коннектор Телеграм",
        "section_dom_id": "settings-block-telegram",
        "keywords": ["telegram", "телеграм", "бот"],
        "children": [
            {
                "label": "Telegram-бот",
                "section_dom_id": "settings-section-telegram",
                "focus": "telegram",
                "keywords": ["botfather", "токен", "прокси", "bot_logic"],
            },
        ],
    },
    {
        "block_id": "avito",
        "label": "Коннектор Авито",
        "section_dom_id": "settings-block-avito",
        "keywords": ["авито", "avito", "oauth"],
        "children": [
            {
                "label": "Авито API",
                "section_dom_id": "settings-section-avito",
                "focus": "avito",
                "keywords": ["client id", "secret", "синхрон"],
            },
        ],
    },
]

MENU_ROOT = {
    "item_id": "settings-root",
    "block_id": None,
    "section_dom_id": "settings-dialog-root",
    "label": "Настройки",
    "path": ["Приложение", "Настройки"],
    "keywords": ["настройки", "settings", "параметры", "меню"],
}

MENU_SIDEBAR_ACTIONS = [
    {
        "item_id": "sidebar-settings",
        "block_id": None,
        "section_dom_id": "settings-dialog-root",
        "label": "Настройки",
        "path": ["Приложение", "Настройки"],
        "keywords": ["настройки", "шестеренка", "параметры"],
    },
]

# Веса: блоки — в первую очередь
WEIGHT_BLOCK = 100
WEIGHT_SECTION = 85
WEIGHT_PATH = 70
WEIGHT_KEYWORD = 45
WEIGHT_TOKEN = 30
WEIGHT_ACTION = 55


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", (text or "").strip().lower())
    return t.replace("ё", "е")


def _slug(text: str, max_len: int = 48) -> str:
    s = _norm(text)
    s = re.sub(r"[^a-z0-9а-я]+", "-", s).strip("-")
    return (s[:max_len] or "x")


def _split_words(text: str) -> list[str]:
    parts = re.split(r"[\s,/\-_+.()]+", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        w = _norm(p)
        if len(w) < 2 or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def _cell(
    *,
    item_id: str,
    cell_type: str,
    block_id: str | None,
    section_dom_id: str,
    label: str,
    search_text: str,
    path: list[str],
    weight: int,
    sort_order: int,
) -> dict[str, Any]:
    st = _norm(search_text)
    return {
        "cell_id": f"{item_id}:{cell_type}:{_slug(st)}",
        "cell_type": cell_type,
        "block_id": block_id,
        "section_dom_id": section_dom_id,
        "item_id": item_id,
        "label": label,
        "search_text": st,
        "path_json": json.dumps(path, ensure_ascii=False),
        "weight": weight,
        "sort_order": sort_order,
    }


def _add_label_cells(
    rows: list[dict[str, Any]],
    *,
    item_id: str,
    cell_type: str,
    block_id: str | None,
    section_dom_id: str,
    label: str,
    path: list[str],
    weight: int,
    sort_order: int,
) -> None:
    rows.append(
        _cell(
            item_id=item_id,
            cell_type=cell_type,
            block_id=block_id,
            section_dom_id=section_dom_id,
            label=label,
            search_text=label,
            path=path,
            weight=weight,
            sort_order=sort_order,
        )
    )
    for i, word in enumerate(_split_words(label)):
        rows.append(
            _cell(
                item_id=item_id,
                cell_type="token",
                block_id=block_id,
                section_dom_id=section_dom_id,
                label=label,
                search_text=word,
                path=path,
                weight=WEIGHT_TOKEN + (5 if cell_type == "block" else 0),
                sort_order=sort_order + i + 1,
            )
        )


def _add_keyword_cells(
    rows: list[dict[str, Any]],
    *,
    item_id: str,
    block_id: str | None,
    section_dom_id: str,
    label: str,
    path: list[str],
    keywords: list[str],
    sort_order: int,
) -> None:
    for ki, kw in enumerate(keywords):
        kw = (kw or "").strip()
        if not kw:
            continue
        rows.append(
            _cell(
                item_id=item_id,
                cell_type="keyword",
                block_id=block_id,
                section_dom_id=section_dom_id,
                label=label,
                search_text=kw,
                path=path,
                weight=WEIGHT_KEYWORD,
                sort_order=sort_order + ki,
            )
        )
        for alt in {ru_to_latin_phonetic(kw), latin_to_ru_phonetic(kw)}:
            if not alt or alt == _norm(kw):
                continue
            rows.append(
                _cell(
                    item_id=item_id,
                    cell_type="token",
                    block_id=block_id,
                    section_dom_id=section_dom_id,
                    label=label,
                    search_text=alt,
                    path=path,
                    weight=WEIGHT_KEYWORD,
                    sort_order=sort_order + ki + 1,
                )
            )
        for wi, word in enumerate(_split_words(kw)):
            rows.append(
                _cell(
                    item_id=item_id,
                    cell_type="token",
                    block_id=block_id,
                    section_dom_id=section_dom_id,
                    label=label,
                    search_text=word,
                    path=path,
                    weight=WEIGHT_TOKEN,
                    sort_order=sort_order + ki * 10 + wi,
                )
            )


def build_catalog_cells() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    order = 0

    def add_path_segments(path: list[str], section_dom_id: str, block_id: str | None, label: str, item_id: str):
        nonlocal order
        for seg in path:
            order += 1
            rows.append(
                _cell(
                    item_id=item_id,
                    cell_type="path",
                    block_id=block_id,
                    section_dom_id=section_dom_id,
                    label=label,
                    search_text=seg,
                    path=path,
                    weight=WEIGHT_PATH,
                    sort_order=order,
                )
            )
            for wi, word in enumerate(_split_words(seg)):
                rows.append(
                    _cell(
                        item_id=item_id,
                        cell_type="token",
                        block_id=block_id,
                        section_dom_id=section_dom_id,
                        label=label,
                        search_text=word,
                        path=path,
                        weight=WEIGHT_TOKEN,
                        sort_order=order + wi,
                    )
                )

    # Корень и действия сайдбара
    for action in [MENU_ROOT, *MENU_SIDEBAR_ACTIONS]:
        order += 1
        item_id = action["item_id"]
        path = list(action["path"])
        _add_label_cells(
            rows,
            item_id=item_id,
            cell_type="action",
            block_id=action.get("block_id"),
            section_dom_id=action["section_dom_id"],
            label=action["label"],
            path=path,
            weight=WEIGHT_ACTION,
            sort_order=order,
        )
        _add_keyword_cells(
            rows,
            item_id=item_id,
            block_id=action.get("block_id"),
            section_dom_id=action["section_dom_id"],
            label=action["label"],
            path=path,
            keywords=action.get("keywords", []),
            sort_order=order,
        )
        add_path_segments(path, action["section_dom_id"], action.get("block_id"), action["label"], item_id)

    for group in MENU_NAV_GROUPS:
        block_id = group["block_id"]
        block_label = group["label"]
        block_dom = group["section_dom_id"]
        block_path = ["Настройки", block_label]
        order += 1

        _add_label_cells(
            rows,
            item_id=block_id,
            cell_type="block",
            block_id=block_id,
            section_dom_id=block_dom,
            label=block_label,
            path=block_path,
            weight=WEIGHT_BLOCK,
            sort_order=order,
        )
        _add_keyword_cells(
            rows,
            item_id=block_id,
            block_id=block_id,
            section_dom_id=block_dom,
            label=block_label,
            path=block_path,
            keywords=group.get("keywords", []),
            sort_order=order,
        )
        add_path_segments(block_path, block_dom, block_id, block_label, block_id)

        for child in group.get("children", []):
            order += 1
            child_label = child["label"]
            child_dom = child["section_dom_id"]
            child_path = ["Настройки", block_label, child_label]
            item_id = child_dom

            _add_label_cells(
                rows,
                item_id=item_id,
                cell_type="section",
                block_id=block_id,
                section_dom_id=child_dom,
                label=child_label,
                path=child_path,
                weight=WEIGHT_SECTION,
                sort_order=order,
            )
            _add_keyword_cells(
                rows,
                item_id=item_id,
                block_id=block_id,
                section_dom_id=child_dom,
                label=child_label,
                path=child_path,
                keywords=child.get("keywords", []),
                sort_order=order,
            )
            add_path_segments(child_path, child_dom, block_id, child_label, item_id)

    # Уникальность cell_id (последний побеждает при коллизии slug)
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_id[row["cell_id"]] = row
    return list(by_id.values())


def sync_catalog() -> dict[str, int]:
    """Пересобрать все ячейки меню в jarvis.db."""
    init_db()
    cells = build_catalog_cells()
    now = _now()
    with _connect() as conn:
        conn.execute("DELETE FROM menu_search_cells WHERE source = 'catalog'")
        conn.executemany(
            """
            INSERT INTO menu_search_cells (
                cell_id, cell_type, block_id, section_dom_id, item_id,
                label, search_text, path_json, weight, sort_order, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'catalog', ?)
            """,
            [
                (
                    c["cell_id"],
                    c["cell_type"],
                    c["block_id"],
                    c["section_dom_id"],
                    c["item_id"],
                    c["label"],
                    c["search_text"],
                    c["path_json"],
                    c["weight"],
                    c["sort_order"],
                    now,
                )
                for c in cells
            ],
        )
        total = conn.execute("SELECT COUNT(*) AS c FROM menu_search_cells").fetchone()["c"]
        blocks = conn.execute(
            "SELECT COUNT(*) AS c FROM menu_search_cells WHERE cell_type = 'block'"
        ).fetchone()["c"]
    return {"cells_upserted": len(cells), "cells_total": int(total), "block_cells": int(blocks)}


def _row_to_item(row: Any, *, is_block: bool = False) -> dict[str, Any]:
    path = json.loads(row["path_json"] or "[]")
    return {
        "id": row["item_id"],
        "block_id": row["block_id"],
        "section_dom_id": row["section_dom_id"],
        "label": row["label"],
        "path": path,
        "is_block": is_block,
        "weight": int(row["weight"]),
    }


def search_menu(query: str, *, limit: int = 24) -> dict[str, Any]:
    variants = search_query_variants(query)
    if not variants:
        return {
            "query": "",
            "items": list_default_items(limit=limit),
            "cells_matched": 0,
            "blocks_matched": [],
        }

    where = " OR ".join(["search_text LIKE ?"] * len(variants))
    params = [f"%{v}%" for v in variants]
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT cell_id, cell_type, block_id, section_dom_id, item_id,
                   label, path_json, weight
            FROM menu_search_cells
            WHERE {where}
            ORDER BY weight DESC, sort_order ASC
            LIMIT 400
            """,
            params,
        ).fetchall()

    if not rows:
        return {
            "query": query,
            "items": [],
            "cells_matched": 0,
            "blocks_matched": [],
        }

    best_by_section: dict[str, Any] = {}
    matched_blocks: set[str] = set()
    for row in rows:
        sid = row["section_dom_id"]
        prev = best_by_section.get(sid)
        if prev is None or int(row["weight"]) > int(prev["weight"]):
            best_by_section[sid] = row
        if row["block_id"]:
            matched_blocks.add(row["block_id"])
        if row["cell_type"] == "block" and row["item_id"]:
            matched_blocks.add(str(row["item_id"]))

    items: list[dict[str, Any]] = []
    seen_item: set[str] = set()

    # Сначала блоки (высокий приоритет)
    block_rows = sorted(
        [r for r in best_by_section.values() if r["cell_type"] == "block"],
        key=lambda r: -int(r["weight"]),
    )
    for row in block_rows:
        key = f"block:{row['section_dom_id']}"
        if key in seen_item:
            continue
        seen_item.add(key)
        items.append(_row_to_item(row, is_block=True))

    # Затем разделы и прочие пункты
    other_rows = sorted(
        [r for r in best_by_section.values() if r["cell_type"] != "block"],
        key=lambda r: -int(r["weight"]),
    )
    for row in other_rows:
        key = f"{row['cell_type']}:{row['section_dom_id']}"
        if key in seen_item:
            continue
        # Не дублировать блок, если уже показан как block
        if row["cell_type"] != "block" and row["section_dom_id"] in {
            b["section_dom_id"] for b in items if b.get("is_block")
        }:
            if row["cell_type"] in ("keyword", "token", "path") and row["section_dom_id"].startswith(
                "settings-block-"
            ):
                continue
        seen_item.add(key)
        items.append(_row_to_item(row, is_block=False))

    # Родительские блоки для совпавших дочерних разделов
    for block_id in matched_blocks:
        group = next((g for g in MENU_NAV_GROUPS if g["block_id"] == block_id), None)
        if not group:
            continue
        dom = group["section_dom_id"]
        if any(i["section_dom_id"] == dom and i.get("is_block") for i in items):
            continue
        path = ["Настройки", group["label"]]
        items.append(
            {
                "id": block_id,
                "block_id": block_id,
                "section_dom_id": dom,
                "label": group["label"],
                "path": path,
                "is_block": True,
                "weight": WEIGHT_BLOCK - 5,
            }
        )

    items.sort(key=lambda i: -int(i.get("weight") or 0))
    items = items[:limit]

    return {
        "query": query,
        "items": items,
        "cells_matched": len(rows),
        "blocks_matched": sorted(matched_blocks),
    }


def list_default_items(*, limit: int = 12) -> list[dict[str, Any]]:
    """Пункты по умолчанию при пустом запросе (подразделы, без заголовков блоков)."""
    out: list[dict[str, Any]] = []
    for group in MENU_NAV_GROUPS:
        for child in group.get("children", []):
            out.append(
                {
                    "id": child["section_dom_id"],
                    "block_id": group["block_id"],
                    "section_dom_id": child["section_dom_id"],
                    "label": child["label"],
                    "path": ["Настройки", group["label"], child["label"]],
                    "is_block": False,
                    "weight": WEIGHT_SECTION,
                }
            )
    if len(out) < limit:
        for group in MENU_NAV_GROUPS:
            if len(out) >= limit:
                break
            out.append(
                {
                    "id": group["block_id"],
                    "block_id": group["block_id"],
                    "section_dom_id": group["section_dom_id"],
                    "label": group["label"],
                    "path": ["Настройки", group["label"]],
                    "is_block": True,
                    "weight": WEIGHT_BLOCK,
                }
            )
    return out[:limit]


def block_ids_for_query(query: str) -> list[str]:
    """Какие блоки настроек показывать при фильтрации (для дерева и секций)."""
    q = _norm(query)
    if not q:
        return [g["block_id"] for g in MENU_NAV_GROUPS]
    data = search_menu(query, limit=64)
    ids: set[str] = set(data.get("blocks_matched") or [])
    for item in data.get("items") or []:
        bid = item.get("block_id")
        if bid:
            ids.add(bid)
    if ids:
        return [g["block_id"] for g in MENU_NAV_GROUPS if g["block_id"] in ids]
    return []


def catalog_stats() -> dict[str, Any]:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM menu_search_cells").fetchone()["c"]
        by_type = {
            row["cell_type"]: row["c"]
            for row in conn.execute(
                "SELECT cell_type, COUNT(*) AS c FROM menu_search_cells GROUP BY cell_type"
            )
        }
    return {"cells_total": int(total), "by_type": by_type}


def section_visible_in_query(section_dom_id: str, query: str) -> bool:
    variants = search_query_variants(query)
    if not variants:
        return True
    data = search_menu(query, limit=64)
    for item in data.get("items") or []:
        if item.get("section_dom_id") == section_dom_id:
            return True
    where = " OR ".join(["search_text LIKE ?"] * len(variants))
    params = [section_dom_id, *[f"%{v}%" for v in variants]]
    with _connect() as conn:
        row = conn.execute(
            f"""
            SELECT 1 FROM menu_search_cells
            WHERE section_dom_id = ? AND ({where})
            LIMIT 1
            """,
            params,
        ).fetchone()
    return row is not None

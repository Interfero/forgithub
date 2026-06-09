"""
Коннектор Авито — OAuth2, сбор дневной статистики, SQLite avito_stats.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

from modules.documents import DB_PATH, init_db
from modules.http_proxy import httpx_client

from modules.app_paths import user_data_dir

DATA_DIR = user_data_dir()
AVITO_DIR = DATA_DIR / "avito"
CONFIG_FILE = AVITO_DIR / "config.json"
API_BASE = "https://api.avito.ru"
_HTTP = httpx.Timeout(45.0, connect=15.0)


class AvitoStatus(str, Enum):
    OFF = "off"
    WAITING = "waiting"
    ACTIVE = "active"
    NEED_CREDS = "need_creds"
    ERROR = "error"


@dataclass
class AvitoState:
    enabled: bool = False
    status: AvitoStatus = AvitoStatus.OFF
    last_event: str = ""
    error: str | None = None
    last_sync_date: str | None = None
    items_synced: int = 0


_state = AvitoState()
_lock = threading.Lock()
_scheduler_stop = threading.Event()
_scheduler_thread: threading.Thread | None = None
_token_cache: dict[str, Any] = {"access_token": "", "expires_at": 0.0}


def _default_config() -> dict:
    return {
        "client_id": "",
        "client_secret": "",
        "user_id": "",
        "sync_enabled": False,
        "last_sync_date": "",
    }


def _load_config() -> dict:
    AVITO_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            return {**_default_config(), **json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return _default_config()


def _save_config(data: dict) -> None:
    AVITO_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps({**_default_config(), **data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _mask_secret(value: str) -> str:
    v = (value or "").strip()
    if len(v) < 8:
        return ""
    return v[:4] + "••••" + v[-2:]


def _creds_ok(cfg: dict | None = None) -> bool:
    c = cfg or _load_config()
    return bool((c.get("client_id") or "").strip() and (c.get("client_secret") or "").strip())


def init_avito_db() -> None:
    from modules.avito_storage import init_avito_storage

    init_avito_storage()


def get_config() -> dict:
    cfg = _load_config()
    cid = (cfg.get("client_id") or "").strip()
    secret = (cfg.get("client_secret") or "").strip()
    return {
        "client_id": _mask_secret(cid) if cid else "",
        "client_id_configured": bool(cid),
        "client_secret_configured": bool(secret),
        "user_id": (cfg.get("user_id") or "").strip(),
        "sync_enabled": bool(cfg.get("sync_enabled")),
        "last_sync_date": cfg.get("last_sync_date") or _state.last_sync_date,
        "ready": _creds_ok(cfg),
    }


def save_config(
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    user_id: str | None = None,
) -> dict:
    cfg = _load_config()
    if client_id is not None and "•" not in client_id:
        cfg["client_id"] = client_id.strip()
    if client_secret is not None and "•" not in client_secret:
        cfg["client_secret"] = client_secret.strip()
    if user_id is not None:
        cfg["user_id"] = user_id.strip()
    _save_config(cfg)
    out = get_config()
    out["save_ok"] = True
    out["message"] = "Настройки Авито сохранены"
    return out


def _get_token() -> str:
    now = time.time()
    if _token_cache.get("access_token") and now < float(_token_cache.get("expires_at", 0)) - 60:
        return str(_token_cache["access_token"])

    cfg = _load_config()
    if not _creds_ok(cfg):
        raise RuntimeError("Укажите Client ID и Client Secret")

    with httpx_client(timeout=_HTTP, proxy=None) as client:
        r = client.post(
            f"{API_BASE}/token",
            data={
                "grant_type": "client_credentials",
                "client_id": cfg["client_id"].strip(),
                "client_secret": cfg["client_secret"].strip(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        data = r.json()

    token = data.get("access_token", "")
    if not token:
        raise RuntimeError("Авито не вернул access_token")
    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    return token


def _api_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_token()}", "Content-Type": "application/json"}


def _resolve_user_id(cfg: dict) -> str:
    uid = (cfg.get("user_id") or "").strip()
    if uid:
        return uid
    with httpx_client(timeout=_HTTP, proxy=None) as client:
        r = client.get(f"{API_BASE}/core/v1/accounts/self", headers=_api_headers())
        r.raise_for_status()
        data = r.json()
    uid = str(data.get("id") or data.get("user_id") or "")
    if not uid:
        raise RuntimeError("Не удалось получить user_id — укажите вручную")
    cfg["user_id"] = uid
    _save_config(cfg)
    return uid


def _title_from_url(url: str) -> str:
    """Заголовок из slug URL объявления Avito."""
    u = (url or "").strip().rstrip("/")
    if not u:
        return ""
    slug = u.split("/")[-1]
    if "_" in slug and slug.rsplit("_", 1)[-1].isdigit():
        slug = slug.rsplit("_", 1)[0]
    return slug.replace("_", " ").replace("-", " ").strip().title()[:500]


def _fetch_single_item_meta(user_id: str, item_id: int | str) -> dict[str, Any]:
    """GET /core/v1/accounts/{uid}/items/{id}/ — единственный рабочий endpoint карточки."""
    with httpx_client(timeout=_HTTP, proxy=None) as client:
        r = client.get(
            f"{API_BASE}/core/v1/accounts/{user_id}/items/{item_id}/",
            headers=_api_headers(),
        )
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json() if r.content else {}


def _fetch_stats_bulk(
    user_id: str,
    date_from: str,
    date_to: str,
    item_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """
    POST /stats/v1/accounts/{uid}/items с itemIds=[] — все объявления за период.
    Возвращает плоский список {item_id, date, views, contacts, favorites, spend}.
    """
    body: dict[str, Any] = {
        "itemIds": item_ids or [],
        "dateFrom": date_from,
        "dateTo": date_to,
        "periodGrouping": "day",
        "fields": ["uniqViews", "uniqContacts", "uniqFavorites"],
    }
    with httpx_client(timeout=httpx.Timeout(90.0, connect=20.0), proxy=None) as client:
        r = client.post(
            f"{API_BASE}/stats/v1/accounts/{user_id}/items",
            headers=_api_headers(),
            json=body,
        )
        if r.status_code == 403:
            raise RuntimeError(
                "Нет доступа к stats:read — включите «Статистика объявлений» в developers.avito.ru"
            )
        if r.status_code == 404:
            return []
        r.raise_for_status()
        payload = r.json()

    items_block = payload.get("result", payload).get("items", [])
    if isinstance(items_block, dict):
        items_block = [{"itemId": k, "stats": v} for k, v in items_block.items()]

    flat: list[dict[str, Any]] = []
    for row in items_block or []:
        iid = int(row.get("itemId") or row.get("item_id") or 0)
        if iid <= 0:
            continue
        stats_list = row.get("stats") or []
        if not stats_list and row.get("date"):
            stats_list = [row]
        for day_row in stats_list:
            day_str = str(day_row.get("date") or "")[:10]
            if not day_str:
                continue
            flat.append(
                {
                    "item_id": iid,
                    "date": day_str,
                    "views": int(day_row.get("uniqViews") or day_row.get("views") or 0),
                    "contacts": int(
                        day_row.get("uniqContacts") or day_row.get("contacts") or 0
                    ),
                    "favorites": int(
                        day_row.get("uniqFavorites") or day_row.get("favorites") or 0
                    ),
                    "spend": float(day_row.get("spend") or day_row.get("promotion") or 0),
                }
            )
    return flat


def _item_titles_map() -> dict[str, str]:
    from modules.avito_storage import item_titles_from_chats

    return item_titles_from_chats()


def _list_items(user_id: str, *, lookback_days: int = 30) -> list[dict]:
    """Список объявлений через stats API (GET /items — 404 на этом аккаунте)."""
    date_to = (date.today() - timedelta(days=1)).isoformat()
    date_from = (date.today() - timedelta(days=lookback_days)).isoformat()
    flat = _fetch_stats_bulk(user_id, date_from, date_to)
    titles = _item_titles_map()
    seen: dict[int, dict] = {}
    for row in flat:
        iid = int(row["item_id"])
        if iid not in seen:
            seen[iid] = {
                "id": iid,
                "title": titles.get(str(iid), f"#{iid}"),
            }
    return list(seen.values())


def _fetch_item_stats(user_id: str, item_ids: list[int], day: str) -> dict[int, dict]:
    """Метрики за один день (обёртка над bulk API)."""
    out: dict[int, dict] = {}
    if not item_ids:
        flat = _fetch_stats_bulk(user_id, day, day)
    else:
        flat = _fetch_stats_bulk(user_id, day, day, item_ids=item_ids)
    for row in flat:
        iid = int(row["item_id"])
        out[iid] = {
            "views": row["views"],
            "contacts": row["contacts"],
            "favorites": row["favorites"],
            "spend": row["spend"],
        }
    for iid in item_ids:
        out.setdefault(iid, {"views": 0, "contacts": 0, "favorites": 0, "spend": 0.0})
    return out


def _upsert_stat(day: str, item_id: str, title: str, metrics: dict) -> None:
    init_avito_db()
    with sqlite3.connect(DB_PATH) as conn:
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
            (
                day,
                str(item_id),
                title,
                metrics.get("views", 0),
                metrics.get("favorites", 0),
                metrics.get("contacts", 0),
                metrics.get("spend", 0.0),
            ),
        )


def sync_day(target: date | None = None) -> dict:
    """Сбор статистики за день (по умолчанию — вчера)."""
    global _state
    day = (target or (date.today() - timedelta(days=1))).isoformat()
    cfg = _load_config()

    with _lock:
        _state.status = AvitoStatus.WAITING
        _state.last_event = f"Синхронизация за {day}…"
        _state.error = None

    try:
        if not _creds_ok(cfg):
            raise RuntimeError("Нужны Client ID и Client Secret")

        user_id = _resolve_user_id(cfg)
        items = _list_items(user_id)
        if not items:
            with _lock:
                _state.last_event = f"Нет объявлений за {day}"
                _state.last_sync_date = day
            cfg["last_sync_date"] = day
            _save_config(cfg)
            return {"ok": True, "date": day, "items": 0}

        ids = [int(x["id"]) for x in items]
        titles = {int(x["id"]): x["title"] for x in items}
        saved = 0
        for i in range(0, len(ids), 200):
            chunk = ids[i : i + 200]
            stats_map = _fetch_item_stats(user_id, chunk, day)
            for iid in chunk:
                m = stats_map.get(iid, {"views": 0, "contacts": 0, "favorites": 0, "spend": 0.0})
                _upsert_stat(day, str(iid), titles.get(iid, ""), m)
                saved += 1

        cfg["last_sync_date"] = day
        _save_config(cfg)
        with _lock:
            _state.status = AvitoStatus.ACTIVE
            _state.items_synced = saved
            _state.last_sync_date = day
            _state.last_event = f"Сохранено {saved} объявлений за {day}"
            _state.error = None
        return {"ok": True, "date": day, "items": saved}
    except Exception as e:
        with _lock:
            _state.status = AvitoStatus.ERROR
            _state.error = str(e)[:500]
            _state.last_event = f"Ошибка синхронизации: {e}"
        return {"ok": False, "error": str(e)}


def get_metrics(date_from: str | None = None, date_to: str | None = None) -> dict:
    init_avito_db()
    if not date_to:
        date_to = date.today().isoformat()
    if not date_from:
        date_from = (date.today() - timedelta(days=7)).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT date, item_id, title, views, favorites, contacts, spend
            FROM avito_stats
            WHERE date >= ? AND date <= ?
            ORDER BY date, item_id
            """,
            (date_from, date_to),
        ).fetchall()

    by_date: dict[str, dict] = {}
    items_map: dict[str, str] = {}
    for r in rows:
        d = r["date"]
        items_map[r["item_id"]] = r["title"]
        if d not in by_date:
            by_date[d] = {"views": 0, "favorites": 0, "contacts": 0, "spend": 0.0}
        by_date[d]["views"] += int(r["views"])
        by_date[d]["favorites"] += int(r["favorites"])
        by_date[d]["contacts"] += int(r["contacts"])
        by_date[d]["spend"] += float(r["spend"])

    series = [{"date": d, **by_date[d]} for d in sorted(by_date.keys())]
    totals = {
        "views": sum(s["views"] for s in series),
        "favorites": sum(s["favorites"] for s in series),
        "contacts": sum(s["contacts"] for s in series),
        "spend": round(sum(s["spend"] for s in series), 2),
    }
    return {
        "date_from": date_from,
        "date_to": date_to,
        "totals": totals,
        "series": series,
        "rows": [dict(r) for r in rows],
        "items_count": len(items_map),
    }


def toggle(enabled: bool) -> dict:
    cfg = _load_config()
    cfg["sync_enabled"] = enabled
    _save_config(cfg)

    with _lock:
        _state.enabled = enabled
        if not enabled:
            _state.status = AvitoStatus.OFF
            _state.last_event = "Синхронизация Авито выключена"
            _state.error = None
            return to_dict()

        if not _creds_ok(cfg):
            _state.enabled = False
            _state.status = AvitoStatus.NEED_CREDS
            _state.last_event = "Укажите Client ID и Client Secret"
            cfg["sync_enabled"] = False
            _save_config(cfg)
            return to_dict()

        _state.status = AvitoStatus.WAITING
        _state.last_event = "Запуск коннектора Авито…"

    threading.Thread(target=_run_sync_worker, daemon=True).start()
    return to_dict()


def _run_sync_worker() -> None:
    sync_day()
    with _lock:
        if _state.status != AvitoStatus.ERROR:
            _state.status = AvitoStatus.ACTIVE


def _scheduler_loop() -> None:
    while not _scheduler_stop.is_set():
        try:
            cfg = _load_config()
            if cfg.get("sync_enabled") and _creds_ok(cfg):
                yesterday = (date.today() - timedelta(days=1)).isoformat()
                if cfg.get("last_sync_date") != yesterday:
                    with _lock:
                        _state.enabled = True
                    sync_day(date.today() - timedelta(days=1))
        except Exception as e:
            with _lock:
                _state.error = str(e)[:300]
        _scheduler_stop.wait(3600)


def _ensure_memory_cells() -> None:
    from modules import jarvis_db

    jarvis_db.init_db()
    cells = {
        "archive_db": (
            "Локальный архив чатов Авито: таблицы avito_chats, avito_messages, avito_account "
            "в accountant.db (рядом с avito_stats). Синхронизация: POST /api/avito/sync/chats."
        ),
        "archive_tools": (
            "Инструменты Qwen: sync_all_avito_data, execute_local_sql_query, avito_press_button "
            "(цена/статус/VAS; без отправки в чаты), avito_report_stats, avito_mine_hr, "
            "avito_audit_listings, sync_avito_chats, get_stored_metrics."
        ),
    }
    for key, content in cells.items():
        jarvis_db.set_cell(
            mode_code=None,
            namespace="avito",
            cell_key=key,
            content=content,
            source="system",
        )


def _seed_avito_agent_prompt() -> None:
    try:
        from modules.app_paths import bundled_data_dir
        from modules.memory_store import UNCONSCIOUS_DIR

        src = bundled_data_dir() / "memory" / "unconscious" / "avito_agent_prompt.txt"
        dst = UNCONSCIOUS_DIR / "avito_agent_prompt.txt"
        if src.is_file() and not dst.is_file():
            UNCONSCIOUS_DIR.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        pass


def bootstrap() -> None:
    init_avito_db()
    _seed_avito_agent_prompt()
    _ensure_memory_cells()
    cfg = _load_config()
    with _lock:
        _state.enabled = bool(cfg.get("sync_enabled"))
        if not _creds_ok(cfg):
            _state.status = AvitoStatus.NEED_CREDS if cfg.get("sync_enabled") else AvitoStatus.OFF
            return
        if cfg.get("sync_enabled"):
            _state.status = AvitoStatus.ACTIVE
            _state.last_sync_date = cfg.get("last_sync_date")
    _start_scheduler()


def _start_scheduler() -> None:
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, name="avito-scheduler", daemon=True)
    _scheduler_thread.start()


def shutdown() -> None:
    _scheduler_stop.set()
    with _lock:
        _state.enabled = False
        _state.status = AvitoStatus.OFF


def to_dict() -> dict:
    from modules.avito_messenger import archive_stats

    labels = {
        "off": "Выключен",
        "waiting": "Синхронизация…",
        "active": "Работает",
        "need_creds": "Нужны ключи API",
        "error": "Ошибка",
    }
    cfg = get_config()
    arch = archive_stats()
    return {
        "enabled": _state.enabled,
        "status": _state.status.value,
        "status_label": labels.get(_state.status.value, "?"),
        "last_event": _state.last_event,
        "error": _state.error,
        "last_sync_date": _state.last_sync_date or cfg.get("last_sync_date"),
        "items_synced": _state.items_synced,
        "client_id_configured": cfg["client_id_configured"],
        "client_secret_configured": cfg["client_secret_configured"],
        "user_id": cfg.get("user_id", ""),
        "ready": cfg["ready"],
        "chats_in_db": arch.get("chats_in_db", 0),
        "messages_in_db": arch.get("messages_in_db", 0),
        "last_chats_sync_at": arch.get("last_chats_sync_at") or None,
    }

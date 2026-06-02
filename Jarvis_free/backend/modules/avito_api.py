"""
Клиент Авито API: синхронизация в SQLite (чтение) и действия в кабинете (запись).
OAuth: client_credentials + опционально refresh_token в config.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import date, timedelta
from typing import Any

import httpx

from modules.avito_storage import (
    init_avito_storage,
    mark_full_sync_done,
    storage_summary,
    upsert_item,
    upsert_stat_row,
)
from modules.http_proxy import httpx_client

API_BASE = "https://api.avito.ru"
_HTTP = httpx.Timeout(60.0, connect=20.0)

_sync_lock = threading.Lock()
_full_sync_running = False

# Типы продвижения → slug для API (если доступен в аккаунте)
BOOST_SERVICE_MAP = {
    "x2": "x2_1",
    "x5": "x5_1",
    "x10": "x10_1",
    "xl": "xl",
    "highlight": "highlight",
}


def _cfg() -> dict:
    from modules.avito import _load_config

    return _load_config()


def _headers() -> dict[str, str]:
    from modules.avito import _api_headers

    return _api_headers()


def _user_id() -> str:
    from modules.avito import _creds_ok, _resolve_user_id

    cfg = _cfg()
    if not _creds_ok(cfg):
        raise RuntimeError("Укажите Client ID и Client Secret Авито в настройках")
    return _resolve_user_id(cfg)


def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    with httpx_client(timeout=_HTTP, proxy=None) as client:
        return client.request(method, url, headers=_headers(), **kwargs)


def _extract_list(body: Any, keys: tuple[str, ...] = ("resources", "items", "result", "data")) -> list:
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


# --- Чтение / синхронизация ---


def fetch_and_sync_profile() -> dict[str, Any]:
    from modules.avito_messenger import fetch_account_profile

    profile = fetch_account_profile()
    return {"ok": True, "profile": profile}


def fetch_and_sync_items() -> dict[str, Any]:
    """Каталог объявлений → avito_items (через stats API + карточка каждого id)."""
    from modules.avito import (
        _fetch_single_item_meta,
        _item_titles_map,
        _list_items,
        _title_from_url,
    )

    uid = _user_id()
    init_avito_storage()
    items = _list_items(uid)
    titles = _item_titles_map()
    saved = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for it in items:
        iid = int(it["id"])
        meta = _fetch_single_item_meta(uid, iid)
        url = str(meta.get("url") or "")
        title = (
            titles.get(str(iid))
            or _title_from_url(url)
            or it.get("title")
            or f"#{iid}"
        )
        upsert_item(
            {
                "item_id": str(iid),
                "user_id": uid,
                "title": str(title)[:500],
                "description": "",
                "price": None,
                "status": str(meta.get("status") or "")[:64],
                "category": "",
                "url": url[:512],
                "raw_json": json.dumps(meta, ensure_ascii=False)[:12000],
                "synced_at": now,
            }
        )
        saved += 1

    return {"ok": True, "items_saved": saved}


def fetch_and_sync_stats(
    item_id: str | None = None,
    *,
    period_days: int = 14,
) -> dict[str, Any]:
    """Посуточная статистика → avito_stats (bulk stats API, itemIds=[])."""
    from modules.avito import _fetch_stats_bulk, _item_titles_map

    uid = _user_id()
    init_avito_storage()
    titles = _item_titles_map()
    saved = 0
    end = date.today() - timedelta(days=1)
    item_ids = [int(item_id)] if item_id else None

    left = period_days
    cursor = end
    while left > 0:
        chunk = min(7, left)
        start = cursor - timedelta(days=chunk - 1)
        flat = _fetch_stats_bulk(
            uid,
            start.isoformat(),
            cursor.isoformat(),
            item_ids,
        )
        for row in flat:
            iid = int(row["item_id"])
            title = titles.get(str(iid)) or f"#{iid}"
            upsert_stat_row(
                row["date"],
                str(iid),
                title,
                views=row["views"],
                favorites=row["favorites"],
                contacts=row["contacts"],
                spend=row["spend"],
            )
            saved += 1
        cursor = start - timedelta(days=1)
        left -= chunk

    from modules.avito_storage import sync_inbound_leads_from_messages

    inbound = sync_inbound_leads_from_messages()
    return {
        "ok": True,
        "rows_upserted": saved,
        "period_days": period_days,
        "inbound_leads": inbound.get("count", 0),
    }


def fetch_and_sync_chats_and_messages(
    *,
    max_chats: int = 500,
    messages_per_chat: int = 150,
) -> dict[str, Any]:
    from modules.avito_messenger import sync_chats

    return sync_chats(max_chats=max_chats, messages_per_chat=messages_per_chat)


def sync_all_avito_data(
    *,
    stats_days: int = 14,
    max_chats: int = 500,
    force: bool = False,
) -> dict[str, Any]:
    """Полная синхронизация API → SQLite (фоново безопасно вызывать из tool)."""
    global _full_sync_running
    from modules.avito_storage import last_full_sync_date

    if not force and last_full_sync_date() == date.today().isoformat():
        return {
            "ok": True,
            "skipped": True,
            "message": "Полная синхронизация уже была сегодня",
            "storage": storage_summary(),
        }

    with _sync_lock:
        if _full_sync_running:
            return {"ok": True, "in_progress": True, "message": "Синхронизация уже идёт"}
        _full_sync_running = True

    report: dict[str, Any] = {"ok": True, "steps": []}
    try:
        for name, fn, kwargs in (
            ("profile", fetch_and_sync_profile, {}),
            ("stats", fetch_and_sync_stats, {"period_days": stats_days}),
            ("items", fetch_and_sync_items, {}),
            ("chats", fetch_and_sync_chats_and_messages, {"max_chats": max_chats}),
        ):
            try:
                step = fn(**kwargs)
                report["steps"].append({"step": name, **step})
            except Exception as e:
                report["steps"].append({"step": name, "ok": False, "error": str(e)[:400]})
        from modules.avito_storage import sync_inbound_leads_from_messages

        try:
            report["steps"].append(
                {"step": "inbound", **sync_inbound_leads_from_messages()}
            )
        except Exception as e:
            report["steps"].append({"step": "inbound", "ok": False, "error": str(e)[:400]})
        from modules import avito as avito_module

        avito_module.sync_day(date.today() - timedelta(days=1))
        mark_full_sync_done()
        report["storage"] = storage_summary()
    finally:
        with _sync_lock:
            _full_sync_running = False
    return report


# --- Действия («кнопки») ---

# Jarvis Free: только чтение чатов (архив), без исходящих сообщений соискателям.
AVITO_MESSENGER_WRITE_ENABLED = False

_CHAT_WRITE_DISABLED = (
    "Отправка сообщений в чаты Авито отключена в Jarvis Free. "
    "Доступны только загрузка и анализ переписок (messenger:read)."
)


def send_message(chat_id: str, text: str) -> dict[str, Any]:
    """Заблокировано: Jarvis не пишет соискателям в Messenger."""
    _ = chat_id, text
    return {
        "ok": False,
        "error": _CHAT_WRITE_DISABLED,
        "code": "avito_chat_write_disabled",
    }


def update_item_price(item_id: str, new_price: float) -> dict[str, Any]:
    uid = _user_id()
    item_id = str(item_id).strip()
    price_int = int(round(float(new_price)))
    paths_bodies = (
        (
            f"/core/v1/accounts/{uid}/items/{item_id}/price",
            {"price": price_int},
        ),
        (
            f"/core/v1/accounts/{uid}/items/{item_id}",
            {"price": price_int},
        ),
        (
            f"/autoload/v1/accounts/{uid}/items/{item_id}/price",
            {"price": price_int},
        ),
    )
    last_err = ""
    for path, body in paths_bodies:
        for method in ("PUT", "PATCH", "POST"):
            r = _request(method, path, json=body)
            if r.status_code in (200, 201, 204):
                fetch_and_sync_items()
                return {"ok": True, "item_id": item_id, "price": price_int, "path": path}
            last_err = f"{method} {path}: {r.status_code} {r.text[:180]}"
    return {
        "ok": False,
        "error": last_err or "API изменения цены недоступен — проверьте права items",
    }


def toggle_item_status(item_id: str, action: str) -> dict[str, Any]:
    uid = _user_id()
    item_id = str(item_id).strip()
    act = (action or "").strip().lower()
    if act not in ("activate", "deactivate", "close", "publish"):
        return {"ok": False, "error": "action: activate | deactivate | close | publish"}

    slug = "activate" if act in ("activate", "publish") else "deactivate"
    paths = (
        f"/core/v1/accounts/{uid}/items/{item_id}/{slug}",
        f"/core/v1/accounts/{uid}/items/{item_id}/status",
    )
    bodies = ({}, {"status": "active" if slug == "activate" else "inactive"})
    last_err = ""
    for path in paths:
        for body in bodies:
            r = _request("POST", path, json=body if body else None)
            if r.status_code in (200, 201, 204):
                fetch_and_sync_items()
                return {"ok": True, "item_id": item_id, "action": slug}
            r2 = _request("PUT", path, json=body if body else None)
            if r2.status_code in (200, 201, 204):
                fetch_and_sync_items()
                return {"ok": True, "item_id": item_id, "action": slug}
            last_err = f"{path}: {r.status_code}/{r2.status_code}"
    return {"ok": False, "error": last_err or "Не удалось сменить статус объявления"}


def apply_boosting_service(item_id: str, service_type: str) -> dict[str, Any]:
    uid = _user_id()
    item_id = str(item_id).strip()
    st = (service_type or "").strip().lower()
    slug = BOOST_SERVICE_MAP.get(st, st)
    paths = (
        f"/core/v1/accounts/{uid}/items/{item_id}/vas",
        f"/core/v1/accounts/{uid}/items/{item_id}/services",
    )
    body = {"vas_id": slug, "service": slug, "slug": slug}
    last_err = ""
    for path in paths:
        r = _request("POST", path, json=body)
        if r.status_code in (200, 201, 204):
            return {"ok": True, "item_id": item_id, "service": slug}
        last_err = f"{path}: {r.status_code} {r.text[:200]}"
    return {
        "ok": False,
        "error": last_err or "VAS/продвижение: проверьте права и тип услуги (x2, x5, xl)",
    }


def avito_press_button(action_type: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Единая точка действий для LLM (валидация параметров).
    action_type: update_price | toggle_status | apply_boost
    (отправка в чаты отключена)
    """
    p = dict(params or {})
    act = (action_type or "").strip().lower().replace("-", "_")

    if act in ("send_message", "message", "reply", "write", "send"):
        return send_message(str(p.get("chat_id", "")), str(p.get("text", "")))
    if act in ("update_price", "price"):
        return update_item_price(str(p.get("item_id", "")), float(p.get("new_price", 0)))
    if act in ("toggle_status", "status", "activate", "deactivate"):
        action = str(p.get("action") or act)
        if action in ("activate", "deactivate"):
            pass
        elif act in ("activate", "deactivate"):
            action = act
        else:
            action = str(p.get("action", "deactivate"))
        return toggle_item_status(str(p.get("item_id", "")), action)
    if act in ("apply_boost", "boost", "vas"):
        return apply_boosting_service(
            str(p.get("item_id", "")),
            str(p.get("service_type", p.get("service", "x2"))),
        )
    return {
        "ok": False,
        "error": "action_type: update_price | toggle_status | apply_boost",
        "params": p,
    }

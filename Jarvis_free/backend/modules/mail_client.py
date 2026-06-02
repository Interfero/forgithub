"""
Почтовый клиент Jarvis — до 3 ящиков через IMAP (логин/пароль пользователя).
Только проверка подключения и чтение по запросу; без агрессивного polling.
"""

from __future__ import annotations

import imaplib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from modules.app_paths import user_data_dir

MAIL_DIR = user_data_dir() / "mail"
ACCOUNTS_FILE = MAIL_DIR / "accounts.json"
MAX_ACCOUNTS = 3

IMAP_PRESETS: dict[str, tuple[str, int, bool]] = {
    "gmail": ("imap.gmail.com", 993, True),
    "yandex": ("imap.yandex.ru", 993, True),
    "mailru": ("imap.mail.ru", 993, True),
    "outlook": ("outlook.office365.com", 993, True),
    "rambler": ("imap.rambler.ru", 993, True),
}


class MailAccountStatus(str, Enum):
    OFF = "off"
    OK = "ok"
    NEED_CREDS = "need_creds"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class MailAccount:
    id: str
    label: str
    email: str
    imap_host: str
    imap_port: int
    imap_ssl: bool
    password: str = ""
    enabled: bool = True
    preset: str = ""
    status: MailAccountStatus = MailAccountStatus.OFF
    status_label: str = "Не настроено"
    last_event: str = ""
    error: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_file() -> dict:
    return {"accounts": [], "updated_at": _now()}


def _load_raw() -> dict:
    MAIL_DIR.mkdir(parents=True, exist_ok=True)
    if not ACCOUNTS_FILE.exists():
        return _default_file()
    try:
        return {**_default_file(), **json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))}
    except Exception:
        return _default_file()


def _save_raw(data: dict) -> None:
    MAIL_DIR.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    ACCOUNTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _row_to_account(row: dict, prev: MailAccount | None = None) -> MailAccount:
    st = row.get("status") or (prev.status.value if prev else MailAccountStatus.OFF.value)
    try:
        status = MailAccountStatus(st)
    except ValueError:
        status = MailAccountStatus.OFF
    return MailAccount(
        id=str(row.get("id") or uuid.uuid4().hex[:10]),
        label=str(row.get("label") or "").strip() or "Почта",
        email=str(row.get("email") or "").strip(),
        imap_host=str(row.get("imap_host") or "").strip(),
        imap_port=int(row.get("imap_port") or 993),
        imap_ssl=bool(row.get("imap_ssl", True)),
        password=str(row.get("password") or ""),
        enabled=bool(row.get("enabled", True)),
        preset=str(row.get("preset") or ""),
        status=status,
        status_label=str(row.get("status_label") or "—"),
        last_event=str(row.get("last_event") or ""),
        error=row.get("error"),
    )


def _account_to_row(a: MailAccount) -> dict:
    return {
        "id": a.id,
        "label": a.label,
        "email": a.email,
        "imap_host": a.imap_host,
        "imap_port": a.imap_port,
        "imap_ssl": a.imap_ssl,
        "password": a.password,
        "enabled": a.enabled,
        "preset": a.preset,
        "status": a.status.value,
        "status_label": a.status_label,
        "last_event": a.last_event,
        "error": a.error,
    }


def list_accounts() -> list[MailAccount]:
    raw = _load_raw()
    return [_row_to_account(r) for r in raw.get("accounts") or []]


def get_config() -> dict[str, Any]:
    accounts = list_accounts()
    return {
        "max_accounts": MAX_ACCOUNTS,
        "presets": list(IMAP_PRESETS.keys()),
        "accounts": [
            {
                "id": a.id,
                "label": a.label,
                "email": a.email,
                "imap_host": a.imap_host,
                "imap_port": a.imap_port,
                "imap_ssl": a.imap_ssl,
                "password_configured": bool((a.password or "").strip()),
                "enabled": a.enabled,
                "preset": a.preset,
            }
            for a in accounts
        ],
    }


def save_accounts(payload: list[dict]) -> dict[str, Any]:
    if len(payload) > MAX_ACCOUNTS:
        raise ValueError(f"Не более {MAX_ACCOUNTS} почтовых ящиков")
    prev = {a.id: a for a in list_accounts()}
    out: list[MailAccount] = []
    for row in payload:
        aid = str(row.get("id") or "").strip() or uuid.uuid4().hex[:10]
        old = prev.get(aid)
        preset = str(row.get("preset") or "").strip().lower()
        host = str(row.get("imap_host") or "").strip()
        port = int(row.get("imap_port") or 993)
        ssl = bool(row.get("imap_ssl", True))
        if preset in IMAP_PRESETS:
            host, port, ssl = IMAP_PRESETS[preset]
        pwd = str(row.get("password") or "")
        if not pwd.strip() and old:
            pwd = old.password
        acc = MailAccount(
            id=aid,
            label=str(row.get("label") or "").strip() or "Почта",
            email=str(row.get("email") or "").strip(),
            imap_host=host,
            imap_port=port,
            imap_ssl=ssl,
            password=pwd.strip(),
            enabled=bool(row.get("enabled", True)),
            preset=preset,
            status=old.status if old else MailAccountStatus.OFF,
            status_label=old.status_label if old else "Не проверено",
            last_event=old.last_event if old else "",
            error=old.error if old else None,
        )
        if not acc.email or not acc.password:
            acc.status = MailAccountStatus.NEED_CREDS
            acc.status_label = "Нужен email и пароль"
        elif not acc.enabled:
            acc.status = MailAccountStatus.DISABLED
            acc.status_label = "Выключено"
        out.append(acc)
    _save_raw({"accounts": [_account_to_row(a) for a in out]})
    return get_config()


def _test_imap(acc: MailAccount) -> tuple[bool, str]:
    if not acc.email or not acc.password:
        return False, "Укажите email и пароль (или пароль приложения)"
    if not acc.imap_host:
        return False, "Укажите IMAP-сервер или выберите пресет"
    try:
        if acc.imap_ssl:
            conn = imaplib.IMAP4_SSL(acc.imap_host, acc.imap_port, timeout=20)
        else:
            conn = imaplib.IMAP4(acc.imap_host, acc.imap_port, timeout=20)
        conn.login(acc.email, acc.password)
        conn.select("INBOX", readonly=True)
        conn.logout()
        return True, "IMAP: вход выполнен"
    except imaplib.IMAP4.error as e:
        return False, f"IMAP: {e}"
    except OSError as e:
        return False, f"Сеть: {e}"
    except Exception as e:
        return False, str(e)


def test_account(account_id: str) -> dict[str, Any]:
    accounts = list_accounts()
    acc = next((a for a in accounts if a.id == account_id), None)
    if not acc:
        raise ValueError("Ящик не найден")
    ok, msg = _test_imap(acc)
    acc.last_event = msg
    acc.error = None if ok else msg
    if ok:
        acc.status = MailAccountStatus.OK
        acc.status_label = "Подключено"
    else:
        acc.status = MailAccountStatus.ERROR
        acc.status_label = "Ошибка"
    _persist_accounts(accounts)
    return {"ok": ok, "message": msg, "account_id": account_id}


def refresh_all_statuses() -> None:
    accounts = list_accounts()
    changed = False
    for acc in accounts:
        if not acc.enabled:
            acc.status = MailAccountStatus.DISABLED
            acc.status_label = "Выключено"
            changed = True
            continue
        if not acc.email or not acc.password:
            acc.status = MailAccountStatus.NEED_CREDS
            acc.status_label = "Нужен email и пароль"
            changed = True
            continue
    if changed:
        _persist_accounts(accounts)


def _persist_accounts(accounts: list[MailAccount]) -> None:
    _save_raw({"accounts": [_account_to_row(a) for a in accounts]})


def bootstrap() -> None:
    refresh_all_statuses()


def to_dict() -> dict[str, Any]:
    accounts = list_accounts()
    any_ok = any(a.status == MailAccountStatus.OK for a in accounts if a.enabled)
    any_warn = any(
        a.status in (MailAccountStatus.NEED_CREDS, MailAccountStatus.ERROR)
        for a in accounts
        if a.enabled
    )
    return {
        "enabled": any(a.enabled for a in accounts),
        "ready": any_ok,
        "status": "ok" if any_ok else ("warn" if any_warn else "off"),
        "status_label": (
            f"Подключено: {sum(1 for a in accounts if a.status == MailAccountStatus.OK)}"
            if any_ok
            else ("Нужна настройка" if any_warn else "Выключено")
        ),
        "last_event": accounts[0].last_event if accounts else "",
        "accounts": [
            {
                "id": a.id,
                "label": a.label,
                "email": a.email,
                "enabled": a.enabled,
                "configured": bool(a.email and a.password),
                "status": a.status.value,
                "status_label": a.status_label,
                "last_event": a.last_event,
                "error": a.error,
            }
            for a in accounts
        ],
        "slots": _pad_slots(accounts),
    }


def _pad_slots(accounts: list[MailAccount]) -> list[dict[str, Any]]:
    """Ровно 3 слота для индикаторов."""
    slots: list[dict[str, Any]] = []
    for i in range(MAX_ACCOUNTS):
        if i < len(accounts):
            a = accounts[i]
            slots.append(
                {
                    "slot": i + 1,
                    "id": a.id,
                    "label": a.label,
                    "email": a.email,
                    "enabled": a.enabled,
                    "configured": bool(a.email and a.password),
                    "status": a.status.value,
                    "status_label": a.status_label,
                    "last_event": a.last_event,
                    "error": a.error,
                }
            )
        else:
            slots.append(
                {
                    "slot": i + 1,
                    "id": None,
                    "label": f"Ящик {i + 1}",
                    "email": "",
                    "enabled": False,
                    "configured": False,
                    "status": "off",
                    "status_label": "Не добавлен",
                    "last_event": "",
                    "error": None,
                }
            )
    return slots

"""
Почтовый клиент Jarvis — 4 ящика провайдеров (Gmail, Яндекс, iCloud, Mail.ru)
и 1 слот legacy IMAP. Чтение писем, пометка прочитанным и т.п. через IMAP.
"""

from __future__ import annotations

import email
import imaplib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Any

from modules.app_paths import user_data_dir

MAIL_DIR = user_data_dir() / "mail"
ACCOUNTS_FILE = MAIL_DIR / "accounts.json"
MAX_ACCOUNTS = 5

IMAP_PRESETS: dict[str, tuple[str, int, bool]] = {
    "gmail": ("imap.gmail.com", 993, True),
    "yandex": ("imap.yandex.ru", 993, True),
    "icloud": ("imap.mail.me.com", 993, True),
    "mailru": ("imap.mail.ru", 993, True),
    "outlook": ("outlook.office365.com", 993, True),
    "rambler": ("imap.rambler.ru", 993, True),
}

SLOT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "slot": 1,
        "provider": "gmail",
        "preset": "gmail",
        "label": "Google Gmail",
        "hint": "Пароль приложения Google (не обычный пароль аккаунта).",
    },
    {
        "slot": 2,
        "provider": "yandex",
        "preset": "yandex",
        "label": "Яндекс Почта",
        "hint": "Пароль приложения или пароль для внешних клиентов в настройках Яндекса.",
    },
    {
        "slot": 3,
        "provider": "icloud",
        "preset": "icloud",
        "label": "Apple iCloud",
        "hint": "Пароль для приложений на appleid.apple.com (не пароль Apple ID).",
    },
    {
        "slot": 4,
        "provider": "mailru",
        "preset": "mailru",
        "label": "Mail.ru",
        "hint": "Пароль для внешнего почтового клиента в настройках Mail.ru.",
    },
    {
        "slot": 5,
        "provider": "legacy",
        "preset": "",
        "label": "IMAP (legacy)",
        "hint": "Любой IMAP-сервер вручную — для редких провайдеров.",
    },
]

_PROVIDER_BY_PRESET = {s["preset"]: s["provider"] for s in SLOT_DEFINITIONS if s["preset"]}


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
    provider: str = ""
    slot: int = 0
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


def _slot_meta(index: int) -> dict[str, Any]:
    return SLOT_DEFINITIONS[index]


def _default_account(index: int, prev: MailAccount | None = None) -> MailAccount:
    meta = _slot_meta(index)
    slot_id = f"mail-{meta['provider']}"
    host, port, ssl = ("", 993, True)
    preset = str(meta.get("preset") or "")
    if preset in IMAP_PRESETS:
        host, port, ssl = IMAP_PRESETS[preset]
    return MailAccount(
        id=prev.id if prev else slot_id,
        label=str(prev.label if prev and prev.label else meta["label"]),
        email=prev.email if prev else "",
        imap_host=prev.imap_host if prev and prev.imap_host else host,
        imap_port=prev.imap_port if prev else port,
        imap_ssl=prev.imap_ssl if prev else ssl,
        password=prev.password if prev else "",
        enabled=prev.enabled if prev else True,
        preset=preset,
        provider=str(meta["provider"]),
        slot=int(meta["slot"]),
        status=prev.status if prev else MailAccountStatus.OFF,
        status_label=prev.status_label if prev else "Не настроено",
        last_event=prev.last_event if prev else "",
        error=prev.error if prev else None,
    )


def _row_to_account(row: dict, prev: MailAccount | None = None) -> MailAccount:
    st = row.get("status") or (prev.status.value if prev else MailAccountStatus.OFF.value)
    try:
        status = MailAccountStatus(st)
    except ValueError:
        status = MailAccountStatus.OFF
    preset = str(row.get("preset") or (prev.preset if prev else "")).strip().lower()
    provider = str(row.get("provider") or (prev.provider if prev else "") or _PROVIDER_BY_PRESET.get(preset, "")).strip()
    return MailAccount(
        id=str(row.get("id") or (prev.id if prev else uuid.uuid4().hex[:10])),
        label=str(row.get("label") or (prev.label if prev else "")).strip() or "Почта",
        email=str(row.get("email") or (prev.email if prev else "")).strip(),
        imap_host=str(row.get("imap_host") or (prev.imap_host if prev else "")).strip(),
        imap_port=int(row.get("imap_port") or (prev.imap_port if prev else 993)),
        imap_ssl=bool(row.get("imap_ssl", prev.imap_ssl if prev else True)),
        password=str(row.get("password") or (prev.password if prev else "")),
        enabled=bool(row.get("enabled", prev.enabled if prev else True)),
        preset=preset,
        provider=provider,
        slot=int(row.get("slot") or (prev.slot if prev else 0)),
        status=status,
        status_label=str(row.get("status_label") or (prev.status_label if prev else "—")),
        last_event=str(row.get("last_event") or (prev.last_event if prev else "")),
        error=row.get("error") if row.get("error") is not None else (prev.error if prev else None),
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
        "provider": a.provider,
        "slot": a.slot,
        "status": a.status.value,
        "status_label": a.status_label,
        "last_event": a.last_event,
        "error": a.error,
    }


def _migrate_accounts(old_rows: list[dict]) -> list[MailAccount]:
    parsed = [_row_to_account(r) for r in old_rows]
    by_preset: dict[str, MailAccount] = {}
    legacy_pool: list[MailAccount] = []
    for acc in parsed:
        preset = (acc.preset or "").lower()
        provider = (acc.provider or _PROVIDER_BY_PRESET.get(preset, "")).lower()
        if provider in ("gmail", "yandex", "icloud", "mailru") and provider not in by_preset:
            by_preset[provider] = acc
        elif preset in _PROVIDER_BY_PRESET and preset not in by_preset:
            by_preset[preset] = acc
        else:
            legacy_pool.append(acc)

    out: list[MailAccount] = []
    for i, meta in enumerate(SLOT_DEFINITIONS):
        provider = str(meta["provider"])
        preset = str(meta.get("preset") or "")
        picked: MailAccount | None = None
        if provider == "legacy":
            picked = legacy_pool.pop(0) if legacy_pool else None
            if not picked:
                for acc in parsed:
                    if acc.preset not in IMAP_PRESETS or acc.preset in ("outlook", "rambler"):
                        picked = acc
                        break
        else:
            picked = by_preset.get(provider)
            if not picked and i < len(parsed) and parsed[i].email:
                picked = parsed[i]
        base = _default_account(i, picked)
        base.slot = int(meta["slot"])
        base.provider = provider
        if provider != "legacy":
            base.preset = preset
            if preset in IMAP_PRESETS:
                host, port, ssl = IMAP_PRESETS[preset]
                base.imap_host, base.imap_port, base.imap_ssl = host, port, ssl
        elif not base.imap_host and base.preset in IMAP_PRESETS:
            host, port, ssl = IMAP_PRESETS[base.preset]
            base.imap_host, base.imap_port, base.imap_ssl = host, port, ssl
        if not base.label or base.label.startswith("Ящик "):
            base.label = str(meta["label"])
        out.append(base)
    return out


def list_accounts() -> list[MailAccount]:
    raw = _load_raw()
    rows = raw.get("accounts") or []
    if len(rows) != MAX_ACCOUNTS or any(not r.get("provider") for r in rows):
        accounts = _migrate_accounts(rows)
        _persist_accounts(accounts)
        return accounts
    accounts = [_row_to_account(r) for r in rows]
    for i, acc in enumerate(accounts):
        meta = _slot_meta(i)
        acc.slot = int(meta["slot"])
        acc.provider = str(meta["provider"])
        if acc.provider != "legacy":
            acc.preset = str(meta.get("preset") or "")
            if acc.preset in IMAP_PRESETS:
                host, port, ssl = IMAP_PRESETS[acc.preset]
                acc.imap_host, acc.imap_port, acc.imap_ssl = host, port, ssl
    return accounts


def _resolve_account(
    account_id: str | None = None,
    slot: int | None = None,
    provider: str | None = None,
) -> MailAccount:
    accounts = list_accounts()
    if account_id:
        acc = next((a for a in accounts if a.id == account_id), None)
        if acc:
            return acc
        raise ValueError("Ящик не найден")
    if slot is not None:
        if slot < 1 or slot > MAX_ACCOUNTS:
            raise ValueError(f"Слот должен быть от 1 до {MAX_ACCOUNTS}")
        return accounts[slot - 1]
    if provider:
        p = provider.strip().lower()
        aliases = {
            "google": "gmail",
            "gmail": "gmail",
            "яндекс": "yandex",
            "yandex": "yandex",
            "apple": "icloud",
            "icloud": "icloud",
            "mail.ru": "mailru",
            "mailru": "mailru",
            "legacy": "legacy",
            "imap": "legacy",
        }
        p = aliases.get(p, p)
        acc = next((a for a in accounts if a.provider == p), None)
        if acc:
            return acc
        raise ValueError(f"Ящик провайдера «{provider}» не найден")
    raise ValueError("Укажите account_id, slot (1–5) или provider")


def get_config() -> dict[str, Any]:
    accounts = list_accounts()
    return {
        "max_accounts": MAX_ACCOUNTS,
        "presets": [s["preset"] for s in SLOT_DEFINITIONS if s.get("preset")],
        "slots": SLOT_DEFINITIONS,
        "accounts": [
            {
                "id": a.id,
                "slot": a.slot,
                "provider": a.provider,
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
    prev_list = list_accounts()
    prev = {a.id: a for a in prev_list}
    out: list[MailAccount] = []
    for i in range(MAX_ACCOUNTS):
        meta = _slot_meta(i)
        row = payload[i] if i < len(payload) else {}
        aid = str(row.get("id") or "").strip() or f"mail-{meta['provider']}"
        old = prev.get(aid) or (prev_list[i] if i < len(prev_list) else None)
        preset = str(meta.get("preset") or "").strip().lower()
        provider = str(meta["provider"])
        host = str(row.get("imap_host") or "").strip()
        port = int(row.get("imap_port") or 993)
        ssl = bool(row.get("imap_ssl", True))
        if provider != "legacy" and preset in IMAP_PRESETS:
            host, port, ssl = IMAP_PRESETS[preset]
        elif provider == "legacy":
            custom_preset = str(row.get("preset") or "").strip().lower()
            if custom_preset in IMAP_PRESETS:
                host, port, ssl = IMAP_PRESETS[custom_preset]
                preset = custom_preset
            elif not host and old:
                host, port, ssl = old.imap_host, old.imap_port, old.imap_ssl
        pwd = str(row.get("password") or "")
        if not pwd.strip() and old:
            pwd = old.password
        label = str(row.get("label") or "").strip() or str(meta["label"])
        acc = MailAccount(
            id=aid,
            label=label,
            email=str(row.get("email") or "").strip(),
            imap_host=host,
            imap_port=port,
            imap_ssl=ssl,
            password=pwd.strip(),
            enabled=bool(row.get("enabled", True)),
            preset=preset if provider == "legacy" else str(meta.get("preset") or ""),
            provider=provider,
            slot=int(meta["slot"]),
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
        elif provider == "legacy" and not acc.imap_host:
            acc.status = MailAccountStatus.NEED_CREDS
            acc.status_label = "Укажите IMAP-сервер"
        out.append(acc)
    _save_raw({"accounts": [_account_to_row(a) for a in out]})
    return get_config()


def _connect(acc: MailAccount) -> imaplib.IMAP4:
    if not acc.email or not acc.password:
        raise ValueError("Укажите email и пароль (или пароль приложения)")
    if not acc.imap_host:
        raise ValueError("Укажите IMAP-сервер")
    if acc.imap_ssl:
        conn = imaplib.IMAP4_SSL(acc.imap_host, acc.imap_port, timeout=25)
    else:
        conn = imaplib.IMAP4(acc.imap_host, acc.imap_port, timeout=25)
    conn.login(acc.email, acc.password)
    return conn


def _test_imap(acc: MailAccount) -> tuple[bool, str]:
    try:
        conn = _connect(acc)
        conn.select("INBOX", readonly=True)
        conn.logout()
        label = acc.label or acc.provider or "Почта"
        return True, f"{label}: вход выполнен"
    except imaplib.IMAP4.error as e:
        return False, f"IMAP: {e}"
    except OSError as e:
        return False, f"Сеть: {e}"
    except ValueError as e:
        return False, str(e)
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


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for chunk, enc in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return " ".join(parts).strip()


def _message_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        texts: list[str] = []
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                continue
            ctype = part.get_content_type()
            if ctype not in ("text/plain", "text/html"):
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            texts.append(payload.decode(charset, errors="replace"))
        return "\n\n".join(texts).strip()
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    charset = msg.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace").strip()


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_msg_summary(uid: bytes, raw: bytes, flags: list[str]) -> dict[str, Any]:
    msg = email.message_from_bytes(raw)
    subject = _decode_mime_header(msg.get("Subject"))
    from_addr = _decode_mime_header(msg.get("From"))
    date_raw = msg.get("Date") or ""
    date_iso = ""
    try:
        if date_raw:
            date_iso = parsedate_to_datetime(date_raw).isoformat()
    except Exception:
        date_iso = date_raw
    seen = any("\\Seen" in f or "Seen" in f for f in flags)
    return {
        "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
        "subject": subject or "(без темы)",
        "from": from_addr,
        "date": date_iso or date_raw,
        "seen": seen,
        "flags": flags,
    }


def list_messages(
    account_id: str | None = None,
    *,
    slot: int | None = None,
    provider: str | None = None,
    folder: str = "INBOX",
    limit: int = 20,
    unread_only: bool = False,
) -> dict[str, Any]:
    acc = _resolve_account(account_id, slot, provider)
    if not acc.enabled:
        raise ValueError(f"Ящик «{acc.label}» выключен")
    limit = max(1, min(int(limit or 20), 50))
    conn = _connect(acc)
    try:
        status, _ = conn.select(folder, readonly=True)
        if status != "OK":
            raise ValueError(f"Не удалось открыть папку {folder}")
        criteria = "UNSEEN" if unread_only else "ALL"
        _, data = conn.uid("search", None, criteria)
        uids = data[0].split() if data and data[0] else []
        uids = uids[-limit:]
        messages: list[dict[str, Any]] = []
        for uid in reversed(uids):
            _, fetched = conn.uid(
                "fetch",
                uid,
                "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)] FLAGS)",
            )
            if not fetched or not fetched[0]:
                continue
            block = fetched[0]
            if isinstance(block, tuple):
                meta_raw = block[0].decode(errors="replace") if isinstance(block[0], bytes) else str(block[0])
                body_raw = block[1] if len(block) > 1 and isinstance(block[1], bytes) else b""
            else:
                meta_raw = block.decode(errors="replace") if isinstance(block, bytes) else str(block)
                body_raw = b""
            flags = re.findall(r"\\[\w]+", meta_raw)
            messages.append(_parse_msg_summary(uid, body_raw, flags))
        return {
            "ok": True,
            "account_id": acc.id,
            "provider": acc.provider,
            "label": acc.label,
            "email": acc.email,
            "folder": folder,
            "count": len(messages),
            "messages": messages,
        }
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def get_message(
    uid: str,
    account_id: str | None = None,
    *,
    slot: int | None = None,
    provider: str | None = None,
    folder: str = "INBOX",
    max_chars: int = 12000,
) -> dict[str, Any]:
    acc = _resolve_account(account_id, slot, provider)
    if not acc.enabled:
        raise ValueError(f"Ящик «{acc.label}» выключен")
    conn = _connect(acc)
    try:
        status, _ = conn.select(folder, readonly=True)
        if status != "OK":
            raise ValueError(f"Не удалось открыть папку {folder}")
        _, fetched = conn.uid("fetch", uid.encode() if isinstance(uid, str) else uid, "(BODY.PEEK[] FLAGS)")
        if not fetched or not fetched[0] or not isinstance(fetched[0], tuple):
            raise ValueError("Письмо не найдено")
        meta_raw = fetched[0][0].decode(errors="replace") if isinstance(fetched[0][0], bytes) else str(fetched[0][0])
        raw = fetched[0][1]
        if not isinstance(raw, bytes):
            raise ValueError("Пустое письмо")
        flags = re.findall(r"\\[\w]+", meta_raw)
        msg = email.message_from_bytes(raw)
        body = _message_body(msg)
        if msg.get_content_type() == "text/html" or "<html" in body[:200].lower():
            body = _strip_html(body)
        if len(body) > max_chars:
            body = body[:max_chars] + "\n… (обрезано)"
        return {
            "ok": True,
            "account_id": acc.id,
            "provider": acc.provider,
            "uid": str(uid),
            "folder": folder,
            "subject": _decode_mime_header(msg.get("Subject")) or "(без темы)",
            "from": _decode_mime_header(msg.get("From")),
            "to": _decode_mime_header(msg.get("To")),
            "date": _decode_mime_header(msg.get("Date")),
            "seen": any("\\Seen" in f for f in flags),
            "body": body,
        }
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def set_read_flag(
    uid: str,
    read: bool = True,
    account_id: str | None = None,
    *,
    slot: int | None = None,
    provider: str | None = None,
    folder: str = "INBOX",
) -> dict[str, Any]:
    acc = _resolve_account(account_id, slot, provider)
    if not acc.enabled:
        raise ValueError(f"Ящик «{acc.label}» выключен")
    conn = _connect(acc)
    try:
        status, _ = conn.select(folder, readonly=False)
        if status != "OK":
            raise ValueError(f"Не удалось открыть папку {folder}")
        op = "+FLAGS" if read else "-FLAGS"
        st, _ = conn.uid("store", str(uid).encode(), op, "(\\Seen)")
        if st != "OK":
            raise ValueError("Не удалось изменить статус письма")
        action = "прочитанным" if read else "непрочитанным"
        return {
            "ok": True,
            "account_id": acc.id,
            "uid": str(uid),
            "read": read,
            "message": f"Письмо {uid} помечено {action}",
        }
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def format_accounts_for_agent() -> str:
    lines = ["Настроенные почтовые ящики Jarvis:"]
    for acc in list_accounts():
        state = "выкл" if not acc.enabled else ("OK" if acc.status == MailAccountStatus.OK else acc.status_label)
        creds = "да" if acc.email and acc.password else "нет"
        lines.append(
            f"  • слот {acc.slot} | {acc.label} ({acc.provider}) | id={acc.id} | "
            f"email={acc.email or '—'} | учётные данные: {creds} | {state}"
        )
    lines.append("Для чтения: mail_list_messages (slot/provider/account_id), mail_get_message, mail_mark_read.")
    return "\n".join(lines)


def format_messages_for_agent(data: dict[str, Any]) -> str:
    lines = [
        f"Почта: {data.get('label')} ({data.get('email')}), папка {data.get('folder')}, "
        f"писем: {data.get('count', 0)}",
    ]
    for m in data.get("messages") or []:
        mark = "прочитано" if m.get("seen") else "НОВОЕ"
        lines.append(
            f"  uid={m.get('uid')} | [{mark}] {m.get('date', '')} | "
            f"от: {m.get('from', '')} | {m.get('subject', '')}"
        )
    if not data.get("messages"):
        lines.append("  (писем нет)")
    return "\n".join(lines)


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
        if acc.provider == "legacy" and not acc.imap_host:
            acc.status = MailAccountStatus.NEED_CREDS
            acc.status_label = "Укажите IMAP-сервер"
            changed = True
    if changed:
        _persist_accounts(accounts)


def _persist_accounts(accounts: list[MailAccount]) -> None:
    _save_raw({"accounts": [_account_to_row(a) for a in accounts]})


def bootstrap() -> None:
    list_accounts()
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
                "slot": a.slot,
                "provider": a.provider,
                "label": a.label,
                "email": a.email,
                "enabled": a.enabled,
                "configured": bool(a.email and a.password and (a.imap_host or a.provider != "legacy")),
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
    slots: list[dict[str, Any]] = []
    for i in range(MAX_ACCOUNTS):
        meta = _slot_meta(i)
        if i < len(accounts):
            a = accounts[i]
            slots.append(
                {
                    "slot": a.slot or i + 1,
                    "id": a.id,
                    "provider": a.provider,
                    "label": a.label or meta["label"],
                    "email": a.email,
                    "enabled": a.enabled,
                    "configured": bool(
                        a.email and a.password and (a.imap_host or a.provider != "legacy")
                    ),
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
                    "id": f"mail-{meta['provider']}",
                    "provider": meta["provider"],
                    "label": meta["label"],
                    "email": "",
                    "enabled": False,
                    "configured": False,
                    "status": "off",
                    "status_label": "Не настроен",
                    "last_event": "",
                    "error": None,
                }
            )
    return slots

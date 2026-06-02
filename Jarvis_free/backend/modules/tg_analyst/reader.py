"""Чтение диалогов userbot: сброс непрочитанного, семплирование истории. Без отправки сообщений."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from modules.tg_analyst import runtime


def _normalize_blocklist_entry(raw: str) -> str:
    s = str(raw).strip()
    if not s:
        return ""
    if s.lstrip("-").isdigit():
        return s
    name = s.lstrip("@").lower()
    return f"@{name}" if name else ""


def split_blocklist(entries: list[str]) -> tuple[list[int], list[str]]:
    peer_ids: list[int] = []
    usernames: list[str] = []
    for raw in entries:
        norm = _normalize_blocklist_entry(raw)
        if not norm:
            continue
        if norm.lstrip("-").isdigit():
            peer_ids.append(int(norm))
        else:
            usernames.append(norm)
    return peer_ids, usernames


async def _resolve_blocklist(client, entries: list[str]) -> tuple[set[int], set[str]]:
    numeric, usernames = split_blocklist(entries)
    peer_ids: set[int] = set(numeric)
    username_tags: set[str] = set(usernames)
    for tag in usernames:
        try:
            entity = await client.get_entity(tag)
            peer_ids.add(entity.id)
        except Exception:
            pass
    return peer_ids, username_tags


def _dialog_username(entity) -> str | None:
    username = getattr(entity, "username", None)
    return f"@{str(username).lower()}" if username else None


def _is_blocked(dialog, peer_blocklist: set[int], username_blocklist: set[str]) -> bool:
    if dialog.id in peer_blocklist:
        return True
    uname = _dialog_username(dialog.entity)
    return bool(uname and uname in username_blocklist)


async def mark_all_read_async(blocklist: list[str]) -> dict:
    client = await runtime.get_client(connect=True)
    if not await client.is_user_authorized():
        raise RuntimeError("Telegram не авторизован")

    peer_bl, user_bl = await _resolve_blocklist(client, blocklist)
    marked = 0
    skipped = 0
    async for dialog in client.iter_dialogs():
        if _is_blocked(dialog, peer_bl, user_bl):
            skipped += 1
            continue
        try:
            await client.send_read_acknowledge(dialog.entity)
            marked += 1
        except Exception:
            try:
                await client.mark_read(dialog.entity)
                marked += 1
            except Exception:
                pass
    return {
        "ok": True,
        "marked": marked,
        "skipped_blocklist": skipped,
        "message": f"Помечено прочитанными: {marked}, пропущено: {skipped}",
    }


async def fetch_samples_async(
    blocklist: list[str],
    sample_hours: int,
    limit_per_chat: int,
    only_unread: bool = False,
) -> list[dict[str, Any]]:
    """
    Собирает семплы сообщений по диалогам. Только get_messages / iter_dialogs.
    """
    client = await runtime.get_client(connect=True)
    if not await client.is_user_authorized():
        raise RuntimeError("Telegram не авторизован")

    peer_bl, user_bl = await _resolve_blocklist(client, blocklist)
    since = datetime.now(timezone.utc) - timedelta(hours=sample_hours)
    results: list[dict[str, Any]] = []

    async for dialog in client.iter_dialogs():
        if _is_blocked(dialog, peer_bl, user_bl):
            continue
        if only_unread and dialog.unread_count <= 0:
            continue

        messages = []
        async for msg in client.iter_messages(dialog.entity, limit=limit_per_chat):
            if msg.date and msg.date.replace(tzinfo=timezone.utc) < since:
                break
            text = msg.message or getattr(msg, "raw_text", None) or ""
            if not text and not msg.media:
                continue
            sender = await msg.get_sender() if msg.sender_id else None
            sender_name = getattr(sender, "first_name", None) or getattr(sender, "title", None) or "?"
            messages.append(
                {
                    "id": msg.id,
                    "date": msg.date.isoformat() if msg.date else None,
                    "sender": sender_name,
                    "text": text[:4000],
                    "out": bool(msg.out),
                }
            )
        messages.reverse()
        if not messages:
            continue

        results.append(
            {
                "chat_id": dialog.id,
                "title": dialog.title or dialog.name or str(dialog.id),
                "username": getattr(dialog.entity, "username", None),
                "unread_count": dialog.unread_count,
                "messages": messages,
            }
        )
    return results


def mark_all_read(blocklist: list[str]) -> dict:
    return runtime.run_async(mark_all_read_async(blocklist))


def fetch_samples(
    blocklist: list[str],
    sample_hours: int,
    limit_per_chat: int,
    only_unread: bool = False,
) -> list[dict]:
    return runtime.run_async(
        fetch_samples_async(blocklist, sample_hours, limit_per_chat, only_unread)
    )

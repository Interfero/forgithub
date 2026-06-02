"""
Сводный отчёт userbot: личка, группы, упоминания @вас.
Только чтение через Telethon (ваш аккаунт, не Bot API).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from telethon.tl.types import MessageEntityMention, MessageEntityMentionName


@dataclass
class ActivityReport:
    generated_at: str
    dialogs_scanned: int = 0
    messages_scanned: int = 0
    private_top: list[tuple[str, int]] = field(default_factory=list)
    groups_top: list[dict[str, Any]] = field(default_factory=list)
    mentions: list[dict[str, Any]] = field(default_factory=list)
    total_mentions: int = 0
    text: str = ""

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "dialogs_scanned": self.dialogs_scanned,
            "messages_scanned": self.messages_scanned,
            "private_top": [{"name": n, "count": c} for n, c in self.private_top],
            "groups_top": self.groups_top,
            "mentions": self.mentions,
            "total_mentions": self.total_mentions,
            "text": self.text,
        }


def _count_mentions(text: str, entities, my_id: int, my_username: str) -> int:
    if not text:
        text = ""
    low = text.lower()
    n = 0
    if my_username:
        needle = f"@{my_username}"
        start = 0
        while True:
            i = low.find(needle, start)
            if i < 0:
                break
            n += 1
            start = i + len(needle)
    if entities:
        for ent in entities:
            if isinstance(ent, MessageEntityMentionName) and ent.user_id == my_id:
                n += 1
            elif isinstance(ent, MessageEntityMention):
                frag = text[ent.offset : ent.offset + ent.length]
                if my_username and frag.lower().strip("@") == my_username:
                    n += 1
    return n


async def _sender_label(client, msg) -> str:
    if not msg.sender_id:
        return "?"
    try:
        sender = await msg.get_sender()
        if sender is None:
            return str(msg.sender_id)
        parts = [
            getattr(sender, "first_name", None),
            getattr(sender, "last_name", None),
        ]
        name = " ".join(p for p in parts if p)
        if name:
            return name
        if getattr(sender, "username", None):
            return f"@{sender.username}"
        if getattr(sender, "title", None):
            return str(sender.title)
    except Exception:
        pass
    return str(msg.sender_id)


async def build_activity_report(
    client,
    *,
    limit_per_chat: int,
    report_hours: int,
    peer_blocklist: set[int],
    username_blocklist: set[str],
    is_blocked_fn,
) -> ActivityReport:
    me = await client.get_me()
    my_id = me.id
    my_username = (me.username or "").lower()
    since = datetime.now(timezone.utc) - timedelta(hours=report_hours)
    now_iso = datetime.now(timezone.utc).isoformat()

    private_incoming: Counter[str] = Counter()
    group_activity: list[dict[str, Any]] = []
    mention_rows: list[dict[str, Any]] = []

    dialogs_scanned = 0
    messages_scanned = 0

    async for dialog in client.iter_dialogs():
        if is_blocked_fn(dialog, peer_blocklist, username_blocklist):
            continue
        dialogs_scanned += 1
        title = dialog.title or dialog.name or str(dialog.id)
        chat_msgs = 0
        chat_mentions = 0

        async for msg in client.iter_messages(dialog.entity, limit=limit_per_chat):
            if msg.date:
                md = msg.date.replace(tzinfo=timezone.utc)
                if md < since:
                    break
            messages_scanned += 1
            chat_msgs += 1

            text = msg.message or ""
            mcnt = _count_mentions(text, msg.entities, my_id, my_username)
            if mcnt:
                chat_mentions += mcnt

            if dialog.is_user and not msg.out:
                label = await _sender_label(client, msg)
                private_incoming[label] += 1

        if dialog.is_group or dialog.is_channel:
            group_activity.append(
                {
                    "title": title,
                    "messages": chat_msgs,
                    "mentions": chat_mentions,
                    "unread": dialog.unread_count,
                }
            )
            if chat_mentions > 0:
                mention_rows.append(
                    {
                        "title": title,
                        "count": chat_mentions,
                        "chat_id": dialog.id,
                    }
                )

    private_top = private_incoming.most_common(12)
    groups_top = sorted(group_activity, key=lambda x: x["messages"], reverse=True)[:12]
    mention_rows.sort(key=lambda x: x["count"], reverse=True)
    total_mentions = sum(r["count"] for r in mention_rows)

    lines = [
        "📊 **Отчёт Двойника Jarvis** (ваш аккаунт, userbot)",
        f"🕐 {now_iso[:19].replace('T', ' ')} UTC · окно **{report_hours} ч**",
        f"📂 Чатов: **{dialogs_scanned}** · сообщений: **{messages_scanned}**",
        "",
        "👤 **Личные — кто писал вам больше всего:**",
    ]
    if private_top:
        for i, (name, cnt) in enumerate(private_top[:8], 1):
            lines.append(f"  {i}. {name} — **{cnt}**")
    else:
        lines.append("  _(нет входящих в личке за период)_")

    lines.append("")
    lines.append("👥 **Группы и каналы — активность:**")
    if groups_top:
        for i, g in enumerate(groups_top[:8], 1):
            ment = f", @вас **{g['mentions']}**" if g["mentions"] else ""
            lines.append(f"  {i}. {g['title']} — **{g['messages']}** сообщ.{ment}")
    else:
        lines.append("  _(нет данных)_")

    lines.append("")
    lines.append("🔔 **Где вас @упоминали:**")
    if mention_rows:
        for r in mention_rows[:10]:
            lines.append(f"  • {r['title']} — **{r['count']}** раз")
        lines.append(f"\nВсего упоминаний: **{total_mentions}**")
    else:
        lines.append("  _(за период не найдено)_")

    lines.append("")
    lines.append(
        "_Двойник читает чаты локально. В чужие чаты ничего не пишет — только этот отчёт в «Чат с двойником»._"
    )

    return ActivityReport(
        generated_at=now_iso,
        dialogs_scanned=dialogs_scanned,
        messages_scanned=messages_scanned,
        private_top=private_top,
        groups_top=groups_top,
        mentions=mention_rows,
        total_mentions=total_mentions,
        text="\n".join(lines),
    )

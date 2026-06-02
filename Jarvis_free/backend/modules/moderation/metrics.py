"""Простые счётчики модерации (in-process; позже — Prometheus)."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock

_lock = Lock()
_actions_total: dict[str, int] = defaultdict(int)
_false_positive_feedback = 0


def inc_action(action: str) -> None:
    key = (action or "ok").lower()
    with _lock:
        _actions_total[key] += 1


def inc_false_positive_feedback() -> None:
    global _false_positive_feedback
    with _lock:
        _false_positive_feedback += 1


def snapshot() -> dict[str, int | dict[str, int]]:
    with _lock:
        return {
            "moderation_actions_total": dict(_actions_total),
            "moderation_false_positive_feedback": _false_positive_feedback,
        }

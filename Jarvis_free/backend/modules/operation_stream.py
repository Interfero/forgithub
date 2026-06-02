"""
Потоковые события прогресса длительных операций (SSE → чат).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

ProgressFn = Callable[[str, str, int, int], None]
# (phase, message, current, total) — total=0 если неизвестно


def sse_progress(
    phase: str,
    message: str,
    *,
    current: int = 0,
    total: int = 0,
) -> str:
    percent: int | None = None
    if total > 0 and current >= 0:
        percent = min(100, int(100 * current / total))
    payload = {
        "type": "progress",
        "phase": phase,
        "message": message,
        "current": current,
        "total": total,
        "percent": percent,
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_log(tool: str, message: str) -> str:
    return f"data: {json.dumps({'type': 'log', 'tool': tool, 'message': message}, ensure_ascii=False)}\n\n"


def make_progress_logger(phase: str, on_line: ProgressFn | None = None) -> ProgressFn:
    """Лог в runtime + опциональный колбэк (очередь для SSE)."""

    def _emit(message: str, current: int = 0, total: int = 0) -> None:
        from modules.agent import get_runtime

        get_runtime().log(phase, message[:200])
        if on_line:
            on_line(phase, message, current, total)

    return _emit

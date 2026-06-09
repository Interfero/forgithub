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


def sse_think(line: str) -> str:
    return f"data: {json.dumps({'type': 'think', 'line': line}, ensure_ascii=False)}\n\n"


def sse_think_end() -> str:
    return f"data: {json.dumps({'type': 'think_end'}, ensure_ascii=False)}\n\n"


def clear_thinking_trace() -> None:
    from modules.agent import get_runtime

    rt = get_runtime()
    rt.thinking_trace = []


def append_thinking(line: str) -> None:
    """Runtime-трейс для SSE «рассуждения Jarvis» (не в chats.json)."""
    import time

    from modules.agent import get_runtime

    s = (line or "").strip()
    if not s:
        return
    rt = get_runtime()
    trace = getattr(rt, "thinking_trace", None)
    if not isinstance(trace, list):
        rt.thinking_trace = []
        trace = rt.thinking_trace
    entry = f"[{time.strftime('%H:%M:%S')}] {s}"
    if trace and trace[-1] == entry:
        return
    trace.append(entry)
    rt.thinking_trace = trace[-48:]
    # Только UI/SSE — не rt.log и не TTS.


def make_progress_logger(phase: str, on_line: ProgressFn | None = None) -> ProgressFn:
    """Лог в runtime + опциональный колбэк (очередь для SSE)."""

    def _emit(message: str, current: int = 0, total: int = 0) -> None:
        from modules.agent import get_runtime

        get_runtime().log(phase, message[:200])
        if on_line:
            on_line(phase, message, current, total)

    return _emit

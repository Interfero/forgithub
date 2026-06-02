"""Глобальное состояние агента для панели разработчика (в памяти процесса)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock

from app.schemas import AgentStatus, ToolLogEntry


@dataclass
class RuntimeAgentState:
    status: AgentStatus = "IDLE"
    session_tokens: int = 0
    model: str = ""
    tool_logs: list[ToolLogEntry] = field(default_factory=list)

    def set_status(self, status: AgentStatus) -> None:
        self.status = status

    def add_tokens(self, n: int) -> None:
        self.session_tokens += max(0, n)

    def log(self, tool: str, message: str) -> ToolLogEntry:
        entry = ToolLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=time.strftime("%H:%M:%S"),
            tool=tool,
            message=message,
        )
        self.tool_logs = [entry, *self.tool_logs[:19]]
        return entry


_lock = Lock()
_state = RuntimeAgentState()


def get_agent_state() -> RuntimeAgentState:
    return _state


def with_agent_lock():
    return _lock

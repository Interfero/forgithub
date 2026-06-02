"""Типы результата модерации сообщений."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ModerationAction = Literal["OK", "WARN", "BLOCK"]


@dataclass
class RuleEngineResult:
    is_flagged: bool
    action: ModerationAction
    response: str | None = None
    rule_name: str | None = None


@dataclass
class ModerationOutcome:
    action: ModerationAction
    response: str | None = None
    triggered_by: list[str] = field(default_factory=list)
    rule_name: str | None = None
    ml_score: float = 0.0
    jarvis_directed: bool = False
    counts_as_insult: bool = False
    response_time_ms: float = 0.0
    consecutive_warnings: int = 0

    @property
    def is_message_ok(self) -> bool:
        return self.action == "OK"

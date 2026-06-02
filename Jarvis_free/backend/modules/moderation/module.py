"""
ModerationModule — оркестратор слоёв 1–3.
Приоритет: минимум ложных срабатываний (консервативные правила, ML по умолчанию выключен).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from modules.moderation.context_tracker import ModerationContextTracker
from modules.moderation.metrics import inc_action
from modules.moderation.ml_detector import predict_aggression_score, warmup_ml_detector
from modules.moderation.rule_engine import ModerationRuleEngine
from modules.moderation.types import ModerationAction, ModerationOutcome

_log = logging.getLogger("jarvis.moderation")

_BLOCK_ESCALATION_RESPONSE = (
    "Шеф, диалог приостановлен на ~30 минут после серии грубых сообщений. "
    "Продолжим, когда тон станет рабочим."
)


def is_directed_at_jarvis(text: str) -> bool:
    from modules.insult_handler import AT_JARVIS_RE

    t = (text or "").strip()
    if len(t) < 2:
        return False
    return bool(AT_JARVIS_RE.search(t))


class ModerationModule:
    def __init__(self) -> None:
        self.rules = ModerationRuleEngine()
        settings = self.rules.settings
        self.ml_threshold = float(settings.get("ml_threshold", 0.85))
        self.ml_enabled = bool(settings.get("ml_enabled", False))
        self.context = ModerationContextTracker(
            warn_to_block=int(settings.get("context_warn_to_block", 3)),
            silence_reset_sec=int(settings.get("context_silence_reset_sec", 600)),
            block_sec=int(settings.get("context_block_sec", 1800)),
        )
        self.slow_ms_warn = float(settings.get("slow_ms_warn", 50))

    def warmup(self) -> None:
        self.rules.reload()
        warmup_ml_detector()

    def moderate(
        self,
        user_message: str,
        user_session_id: str,
        *,
        apply_context: bool = True,
    ) -> ModerationOutcome:
        start = time.perf_counter()
        triggered: list[str] = []
        text = (user_message or "").strip()
        jarvis_directed = is_directed_at_jarvis(text)

        rule_res = self.rules.evaluate(text, jarvis_directed=jarvis_directed)
        raw_action: ModerationAction = rule_res.action
        response = rule_res.response
        rule_name = rule_res.rule_name
        ml_score = 0.0

        if rule_res.is_flagged:
            triggered.append(f"rules:{rule_name}")

        if raw_action == "OK" and self.ml_enabled:
            try:
                ml_score = predict_aggression_score(text)
                if ml_score >= self.ml_threshold:
                    raw_action = "WARN"
                    triggered.append("ml")
                    if not response:
                        response = "Агрессивный тон. Переформулируйте запрос по делу."
            except Exception:
                _log.exception("moderation: ML слой недоступен — только правила")

        if apply_context:
            final_action, override_response, consecutive = self.context.get_final_action(
                user_session_id,
                raw_action,
                block_response=_BLOCK_ESCALATION_RESPONSE,
            )
            if override_response:
                response = override_response
                if final_action == "BLOCK" and "context" not in triggered:
                    triggered.append("context:escalation")
        else:
            final_action = raw_action
            consecutive = 0

        counts_as_insult = final_action in ("WARN", "BLOCK") and jarvis_directed

        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > self.slow_ms_warn:
            _log.warning(
                "moderation slow: %.1f ms session=%s action=%s",
                elapsed_ms,
                user_session_id,
                final_action,
            )

        inc_action(final_action)

        outcome = ModerationOutcome(
            action=final_action,
            response=response,
            triggered_by=triggered,
            rule_name=rule_name,
            ml_score=ml_score,
            jarvis_directed=jarvis_directed,
            counts_as_insult=counts_as_insult,
            response_time_ms=elapsed_ms,
            consecutive_warnings=consecutive,
        )
        self._log_decision(user_session_id, text, outcome)
        return outcome

    def _log_decision(
        self,
        session_id: str,
        text: str,
        outcome: ModerationOutcome,
    ) -> None:
        if outcome.action == "OK" and not outcome.triggered_by:
            return
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "session_id": session_id,
            "original_text": text[:500],
            "triggered_by": outcome.triggered_by,
            "final_action": outcome.action,
            "jarvis_directed": outcome.jarvis_directed,
            "ml_score": round(outcome.ml_score, 4),
            "response_time_ms": round(outcome.response_time_ms, 2),
            "consecutive_warnings": outcome.consecutive_warnings,
        }
        _log.info("moderation %s", json.dumps(payload, ensure_ascii=False))

    def is_message_ok(self, user_message: str, user_session_id: str) -> bool:
        return self.moderate(user_message, user_session_id).is_message_ok


_module: ModerationModule | None = None


def get_moderation_module() -> ModerationModule:
    global _module
    if _module is None:
        _module = ModerationModule()
    return _module


def warmup_moderation() -> None:
    get_moderation_module().warmup()


def moderate_message(
    text: str,
    session_id: str,
    *,
    apply_context: bool = True,
) -> ModerationOutcome:
    return get_moderation_module().moderate(
        text, session_id, apply_context=apply_context
    )


def moderation_log_to_runtime(rt: Any, outcome: ModerationOutcome) -> None:
    if outcome.action == "OK":
        return
    try:
        rt.log(
            "moderation",
            f"{outcome.action} ({','.join(outcome.triggered_by) or '—'}) "
            f"{outcome.response_time_ms:.0f} ms",
        )
    except Exception:
        pass

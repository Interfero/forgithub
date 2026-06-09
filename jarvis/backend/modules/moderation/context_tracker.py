"""
Слой 3: контекст сессии — нарастание WARN, эскалация до BLOCK, остывание.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from modules.moderation.types import ModerationAction

try:
    from cachetools import TTLCache
except ImportError:
    TTLCache = None  # type: ignore[misc, assignment]


@dataclass
class SessionModerationState:
    consecutive_warnings: int = 0
    last_action_ts: float = 0.0
    block_until: float = 0.0
    last_raw_action: ModerationAction = "OK"


class ModerationContextTracker:
    def __init__(
        self,
        *,
        warn_to_block: int = 3,
        silence_reset_sec: int = 600,
        block_sec: int = 1800,
        max_sessions: int = 4096,
    ) -> None:
        self.warn_to_block = warn_to_block
        self.silence_reset_sec = silence_reset_sec
        self.block_sec = block_sec
        if TTLCache is not None:
            self._sessions: dict[str, SessionModerationState] | TTLCache = TTLCache(
                maxsize=max_sessions,
                ttl=silence_reset_sec,
            )
        else:
            self._sessions = {}

    def _get(self, session_id: str) -> SessionModerationState:
        sid = (session_id or "default").strip() or "default"
        if TTLCache is not None and isinstance(self._sessions, TTLCache):
            if sid not in self._sessions:
                self._sessions[sid] = SessionModerationState()
            return self._sessions[sid]
        store = self._sessions
        if sid not in store:
            store[sid] = SessionModerationState()
        return store[sid]

    def get_final_action(
        self,
        session_id: str,
        raw_action: ModerationAction,
        *,
        block_response: str,
    ) -> tuple[ModerationAction, str | None, int]:
        """
        Возвращает (final_action, override_response, consecutive_warnings).
        """
        now = time.time()
        st = self._get(session_id)

        if st.block_until > now:
            return "BLOCK", block_response, st.consecutive_warnings

        if st.last_action_ts and (now - st.last_action_ts) > self.silence_reset_sec:
            st.consecutive_warnings = 0

        st.last_action_ts = now
        st.last_raw_action = raw_action

        if raw_action == "OK":
            st.consecutive_warnings = 0
            return "OK", None, 0

        if raw_action == "WARN":
            st.consecutive_warnings += 1
            if st.consecutive_warnings >= self.warn_to_block:
                st.block_until = now + self.block_sec
                return "BLOCK", block_response, st.consecutive_warnings
            return "WARN", None, st.consecutive_warnings

        if raw_action == "BLOCK":
            st.block_until = now + self.block_sec
            st.consecutive_warnings = self.warn_to_block
            return "BLOCK", None, st.consecutive_warnings

        return raw_action, None, st.consecutive_warnings

    def reset_session(self, session_id: str) -> None:
        sid = (session_id or "default").strip() or "default"
        if TTLCache is not None and isinstance(self._sessions, TTLCache):
            self._sessions.pop(sid, None)
        else:
            self._sessions.pop(sid, None)  # type: ignore[union-attr]

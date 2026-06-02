"""Smoke-test insult lexicon and session counter."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.insult_handler import message_looks_like_insult, process_user_message_insult
from modules.insult_lexicon import ensure_lexicon_ready, lexicon_hits, lexicon_stats_dict


class _Rt:
    session_insult_count = 0
    offended_until = 0.0
    last_insult_angry_until = 0.0
    last_insult_request_id = ""
    last_insult_at_jarvis = False
    last_insult_excerpt = ""

    def log(self, *_a, **_k):
        pass


def main() -> None:
    ensure_lexicon_ready()
    stats = lexicon_stats_dict()
    print("stats:", stats)
    assert stats["active"] >= 100, stats
    assert message_looks_like_insult("ты чучело")
    assert lexicon_hits("ты чучело")
    rt = _Rt()
    r = process_user_message_insult("ты чучело", rt, request_id="t1")
    assert r["insult"]["session_count"] == 1, r
    r2 = process_user_message_insult("ты чучело", rt, request_id="t1")
    assert r2["insult"]["session_count"] == 1, r2
    print("ok")


if __name__ == "__main__":
    main()

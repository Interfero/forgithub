"""Юнит-тесты модерации (слои 1 и 3)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.moderation.context_tracker import ModerationContextTracker
from modules.moderation.module import is_directed_at_jarvis
from modules.moderation.rule_engine import ModerationRuleEngine
from modules.moderation.text_normalize import normalize_for_rules


class TestTextNormalize(unittest.TestCase):
    def test_leet_digit(self) -> None:
        self.assertIn("пошел", normalize_for_rules("п0шел"))


class TestRuleEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ModerationRuleEngine()

    def test_threat_blocks(self) -> None:
        r = self.engine.evaluate("чтобы ты сдох", jarvis_directed=False)
        self.assertEqual(r.action, "BLOCK")

    def test_profanity_without_jarvis_ok(self) -> None:
        r = self.engine.evaluate("блять да устал сегодня", jarvis_directed=False)
        self.assertEqual(r.action, "OK")

    def test_profanity_at_jarvis_warns(self) -> None:
        r = self.engine.evaluate("ты сука jarvis", jarvis_directed=True)
        self.assertEqual(r.action, "WARN")

    def test_neutral_ok(self) -> None:
        r = self.engine.evaluate("привет, как дела?", jarvis_directed=False)
        self.assertEqual(r.action, "OK")


class TestContextTracker(unittest.TestCase):
    def test_escalation_to_block(self) -> None:
        tr = ModerationContextTracker(warn_to_block=3, block_sec=60)
        sid = "test-session"
        for _ in range(2):
            action, _, _ = tr.get_final_action(sid, "WARN", block_response="blocked")
            self.assertEqual(action, "WARN")
        action, resp, n = tr.get_final_action(sid, "WARN", block_response="blocked")
        self.assertEqual(action, "BLOCK")
        self.assertEqual(n, 3)
        self.assertEqual(resp, "blocked")

    def test_ok_resets(self) -> None:
        tr = ModerationContextTracker(warn_to_block=3)
        sid = "s2"
        tr.get_final_action(sid, "WARN", block_response="x")
        action, _, n = tr.get_final_action(sid, "OK", block_response="x")
        self.assertEqual(action, "OK")
        self.assertEqual(n, 0)


class TestJarvisDirected(unittest.TestCase):
    def test_you(self) -> None:
        self.assertTrue(is_directed_at_jarvis("ты дурак"))

    def test_not_you(self) -> None:
        self.assertFalse(is_directed_at_jarvis("начальник дурак"))


if __name__ == "__main__":
    unittest.main()

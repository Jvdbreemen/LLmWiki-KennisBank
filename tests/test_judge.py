"""Tests voor scripts/_judge.py - de oordeel-seam. _llm.generate wordt
gemonkeypatcht; geen echt model."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import unittest
import _judge  # noqa: E402
import _llm  # noqa: E402


class JudgeTest(unittest.TestCase):
    def setUp(self):
        self._orig = _llm.generate

    def tearDown(self):
        _llm.generate = self._orig

    def test_high_confidence_current(self):
        _llm.generate = lambda *a, **k: '{"verdict": "current", "reason": "duidelijke lesson learned"}'
        out = _judge.judge("Bug X opgelost door Y.")
        self.assertEqual(out["verdict"], "current")

    def test_doubt_is_unverified(self):
        _llm.generate = lambda *a, **k: '{"verdict": "unverified", "reason": "vaag"}'
        self.assertEqual(_judge.judge("iets vaags")["verdict"], "unverified")

    def test_model_none_is_failsafe_unverified(self):
        _llm.generate = lambda *a, **k: None
        self.assertEqual(_judge.judge("x")["verdict"], "unverified")

    def test_unparseable_is_failsafe_unverified(self):
        _llm.generate = lambda *a, **k: "ik ben geen json"
        self.assertEqual(_judge.judge("x")["verdict"], "unverified")

    def test_unknown_verdict_is_failsafe(self):
        _llm.generate = lambda *a, **k: '{"verdict": "weet-niet"}'
        self.assertEqual(_judge.judge("x")["verdict"], "unverified")


if __name__ == "__main__":
    unittest.main()

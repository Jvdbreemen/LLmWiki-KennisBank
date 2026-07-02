"""Tests voor scripts/_reconcile.py - write-time invalidatie (ADD/SUPERSEDE/NOOP).

LLM-seam (judge_reconcile) gemockt via _llm.generate of judge_fn-injectie;
geen echt model, geen filesystem.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _reconcile  # noqa: E402


def _item(path: str, vec, body: str = "b", valid_from: str = "2026-01-01",
          status: str = "current"):
    return {"path": path, "title": path, "status": status, "created": valid_from,
            "valid_from": valid_from, "body": body, "vec": vec}


class TestSimilarExisting(unittest.TestCase):
    def test_orders_high_to_low_and_caps_k(self):
        target = [1.0, 0.0, 0.0]
        items = [
            _item("laag.md", [0.8, 0.6, 0.0]),      # cosine 0.8
            _item("hoog.md", [0.9, 0.4358899, 0.0]),  # cosine 0.9
            _item("mid.md", [0.85, 0.5267827, 0.0]),  # cosine 0.85
        ]
        got = _reconcile.similar_existing(target, items, threshold=0.75, k=2)
        self.assertEqual([it["path"] for it in got], ["hoog.md", "mid.md"])

    def test_below_threshold_excluded(self):
        target = [1.0, 0.0, 0.0]
        items = [_item("ortho.md", [0.0, 1.0, 0.0])]
        self.assertEqual(_reconcile.similar_existing(target, items), [])

    def test_items_without_vec_skipped(self):
        target = [1.0, 0.0, 0.0]
        items = [{"path": "kaal.md", "body": "x"}]
        self.assertEqual(_reconcile.similar_existing(target, items), [])


class TestJudgeReconcile(unittest.TestCase):
    def setUp(self):
        import _llm
        self._llm = _llm
        self._orig = _llm.generate

    def tearDown(self):
        self._llm.generate = self._orig

    def test_valid_supersede(self):
        self._llm.generate = lambda *a, **k: '{"action": "SUPERSEDE", "reason": "vervangt"}'
        self.assertEqual(_reconcile.judge_reconcile("nieuw", "oud"), "SUPERSEDE")

    def test_no_response_failsafe_add(self):
        self._llm.generate = lambda *a, **k: None
        self.assertEqual(_reconcile.judge_reconcile("nieuw", "oud"), "ADD")

    def test_garbage_failsafe_add(self):
        self._llm.generate = lambda *a, **k: "geen json hier"
        self.assertEqual(_reconcile.judge_reconcile("nieuw", "oud"), "ADD")

    def test_unknown_action_failsafe_add(self):
        self._llm.generate = lambda *a, **k: '{"action": "DELETE"}'
        self.assertEqual(_reconcile.judge_reconcile("nieuw", "oud"), "ADD")


class TestMaySupersede(unittest.TestCase):
    def test_newer_may_supersede_older(self):
        self.assertTrue(_reconcile.may_supersede("2026-06-25", "2026-01-01"))

    def test_same_date_may_supersede(self):
        self.assertTrue(_reconcile.may_supersede("2026-06-25", "2026-06-25"))

    def test_older_fact_never_invalidates_newer(self):
        self.assertFalse(_reconcile.may_supersede("2026-01-01", "2026-06-25"))

    def test_missing_old_date_does_not_block(self):
        self.assertTrue(_reconcile.may_supersede("2026-06-25", ""))


class TestReconcileFlow(unittest.TestCase):
    def setUp(self):
        self.target = [1.0, 0.0, 0.0]
        self.buur = _item("buur.md", [0.9, 0.4358899, 0.0], valid_from="2026-01-01")

    def test_noop_wins_immediately(self):
        r = _reconcile.reconcile("nieuw", "2026-06-25", self.target, [self.buur],
                                 judge_fn=lambda n, o: "NOOP")
        self.assertEqual(r, {"action": "NOOP", "supersedes": []})

    def test_supersede_collects_neighbor(self):
        r = _reconcile.reconcile("nieuw", "2026-06-25", self.target, [self.buur],
                                 judge_fn=lambda n, o: "SUPERSEDE")
        self.assertEqual(r["action"], "ADD")
        self.assertEqual([it["path"] for it in r["supersedes"]], ["buur.md"])

    def test_supersede_blocked_by_temporal_guard(self):
        # Kandidaat uit een OUDER transcript mag een nieuwer feit niet sluiten.
        r = _reconcile.reconcile("nieuw", "2025-01-01", self.target, [self.buur],
                                 judge_fn=lambda n, o: "SUPERSEDE")
        self.assertEqual(r["action"], "ADD")
        self.assertEqual(r["supersedes"], [])

    def test_add_when_no_neighbors(self):
        called = []
        r = _reconcile.reconcile("nieuw", "2026-06-25", self.target, [],
                                 judge_fn=lambda n, o: called.append(1) or "NOOP")
        self.assertEqual(r["action"], "ADD")
        self.assertEqual(called, [])  # judge niet aangeroepen zonder buren

    def test_noop_against_unverified_neighbor_does_not_win(self):
        # Quarantaine-kennis mag nieuw bewijs niet wegdrukken: NOOP tegen een
        # unverified buur telt niet, de kandidaat wordt gewoon ge-ADD.
        onbevestigd = _item("q.md", [0.9, 0.4358899, 0.0], status="unverified")
        r = _reconcile.reconcile("nieuw", "2026-06-25", self.target, [onbevestigd],
                                 judge_fn=lambda n, o: "NOOP")
        self.assertEqual(r["action"], "ADD")
        self.assertEqual(r["supersedes"], [])


if __name__ == "__main__":
    unittest.main()

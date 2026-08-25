"""Contracts for persistent exposure attribution and weak outcome evidence."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _outcome  # noqa: E402
import _usage  # noqa: E402


class OutcomeLedgerContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = self.tmp.name
        self.addCleanup(self._restore)

    def _restore(self):
        if self.saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self.saved

    def test_exposure_ledger_preserves_layer_rank_query_and_task(self):
        n = _usage.log_exposures(
            [{"item_id": "memory-a", "layer": "memory", "rank": 1},
             {"item_id": "source-b#0", "layer": "source", "rank": 2}],
            session_id="session-1", task_id="task-1", query="fix timeout",
            ts="2026-08-25T10:00:00Z")
        self.assertEqual(n, 2)
        rows = _usage.exposures_for("session-1", task_id="task-1")
        self.assertEqual([(r["item_id"], r["layer"], r["rank"]) for r in rows],
                         [("memory-a", "memory", 1), ("source-b#0", "source", 2)])
        self.assertEqual({r["query"] for r in rows}, {"fix timeout"})

    def test_exposures_survive_pending_cleanup(self):
        _usage.log_injected(["memory-a"], session_id="session-1", today="2026-08-25")
        _usage.log_exposures(
            [{"item_id": "memory-a", "layer": "memory", "rank": 1}],
            session_id="session-1", ts="2026-08-25T10:00:00Z")
        _usage.clear_pending("session-1")
        self.assertEqual(len(_usage.exposures_for("session-1")), 1)

    def test_no_signal_is_unknown_not_failure(self):
        outcome = _outcome.derive_outcome({})
        self.assertEqual(outcome["state"], "unknown")
        self.assertEqual(outcome["evidence"], [])

    def test_green_test_plus_commit_is_success_evidence_not_causality(self):
        outcome = _outcome.derive_outcome({"tests": ["passed"], "commit": "abc123"})
        self.assertEqual(outcome["state"], "success")
        self.assertGreaterEqual(len(outcome["evidence"]), 2)
        self.assertEqual(outcome["attribution_strength"], "none")

    def test_revert_or_failed_test_prevents_success(self):
        outcome = _outcome.derive_outcome(
            {"tests": ["passed", "failed"], "commit": "abc123", "reverted": True})
        self.assertIn(outcome["state"], {"failure", "mixed"})
        self.assertNotEqual(outcome["state"], "success")

    def test_explicit_feedback_can_strengthen_attribution(self):
        outcome = _outcome.derive_outcome(
            {"tests": ["passed"], "user_feedback": "memory-a helped solve this"})
        self.assertEqual(outcome["attribution_strength"], "explicit")


if __name__ == "__main__":
    unittest.main()


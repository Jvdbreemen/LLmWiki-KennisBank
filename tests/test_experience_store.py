"""Contracts for append-only experience events and evidence-gated projections."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _experience as exp  # noqa: E402


class ExperienceStoreContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "experience.db"
        self.conn = exp.connect(self.db)
        self.addCleanup(self.conn.close)
        exp.ensure_schema(self.conn)

    def test_events_are_append_only_and_idempotent(self):
        event = dict(event_id="event-1", session_id="s1", task_id="t1",
                     event_type="attempt", observed_at="2026-08-25T10:00:00Z",
                     payload={"approach": "bounded timeout"},
                     source_refs=["01-raw/a.md#0:20"])
        self.assertTrue(exp.append_event(self.conn, **event))
        self.assertFalse(exp.append_event(self.conn, **event))
        changed = dict(event)
        changed["payload"] = {"approach": "unbounded wait"}
        with self.assertRaises(ValueError):
            exp.append_event(self.conn, **changed)

    def test_outcome_preserves_evidence_and_unknown(self):
        exp.record_outcome(self.conn, outcome_id="out-1", session_id="s1",
                           task_id="t1", state="unknown", evidence=[],
                           attribution_strength="none")
        row = exp.outcome(self.conn, "out-1")
        self.assertEqual(row["state"], "unknown")
        self.assertEqual(row["evidence"], [])

    def test_validated_experience_requires_source_and_outcome_evidence(self):
        common = dict(
            experience_id="exp-1", session_id="s1", task_id="t1",
            situation="child hung", approach="bound timeout",
            observed_result="process stopped", lesson="bound subprocess waits",
            applicability="shutdown helpers", outcome_state="success",
            confidence=0.9)
        with self.assertRaises(ValueError):
            exp.save_experience(self.conn, status="validated", source_refs=[],
                                outcome_refs=[], **common)
        exp.record_outcome(self.conn, outcome_id="out-1", session_id="s1",
                           task_id="t1", state="success",
                           evidence=[{"kind": "test", "value": "passed"}],
                           attribution_strength="none")
        exp.save_experience(self.conn, status="validated",
                            source_refs=["01-raw/a.md#0:20"],
                            outcome_refs=["out-1"], **common)
        self.assertEqual(exp.experience(self.conn, "exp-1")["status"], "validated")

    def test_candidate_may_preserve_uncertainty_but_not_become_validated_implicitly(self):
        exp.save_experience(
            self.conn, experience_id="exp-c", session_id="s1", task_id="t1",
            status="candidate", situation="parser failed", approach="retry",
            observed_result="unknown", lesson="retry may help",
            applicability="unknown", outcome_state="unknown", confidence=0.2,
            source_refs=[], outcome_refs=[])
        self.assertEqual(exp.experience(self.conn, "exp-c")["status"], "candidate")
        with self.assertRaises(ValueError):
            exp.transition(self.conn, "exp-c", "validated")

    def test_supersession_keeps_the_original_record(self):
        for eid in ("old", "new"):
            exp.save_experience(
                self.conn, experience_id=eid, session_id="s", task_id="t",
                status="candidate", situation="s", approach="a",
                observed_result="r", lesson=eid, applicability="scope",
                outcome_state="unknown", confidence=0.4,
                source_refs=[], outcome_refs=[])
        exp.transition(self.conn, "old", "superseded", superseded_by="new")
        old = exp.experience(self.conn, "old")
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["superseded_by"], "new")
        self.assertIsNotNone(exp.experience(self.conn, "new"))


if __name__ == "__main__":
    unittest.main()


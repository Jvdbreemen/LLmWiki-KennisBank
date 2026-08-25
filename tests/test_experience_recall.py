"""Retrieval and advisory-warning contracts for experience memory."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _experience as exp  # noqa: E402


class ExperienceRecallContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = exp.connect(Path(self.tmp.name) / "experience.db")
        self.addCleanup(self.conn.close)
        exp.ensure_schema(self.conn)
        exp.ensure_recall_schema(self.conn, dim=4, embed_id="fake:4")
        for eid, state, status, vector, lesson, refs in (
            ("good", "success", "validated", [1, 0, 0, 0],
             "Use a bounded timeout", (["source#a"], ["out-good"])),
            ("bad", "failure", "validated", [0, 1, 0, 0],
             "Avoid graph-community scene priors", (["source#b"], ["out-bad"])),
            ("guess", "unknown", "candidate", [1, 0, 0, 0],
             "Retry everything", ([], [])),
        ):
            if refs[1]:
                exp.record_outcome(self.conn, outcome_id=refs[1][0], session_id="s",
                                   task_id="t", state=state,
                                   evidence=[{"kind": "test", "value": state}],
                                   attribution_strength="none")
            exp.save_experience(
                self.conn, experience_id=eid, session_id="s", task_id="t",
                status=status, situation=lesson, approach=lesson,
                observed_result=state, lesson=lesson, applicability="repo",
                outcome_state=state, confidence=0.9 if status == "validated" else 0.2,
                source_refs=refs[0], outcome_refs=refs[1])
            exp.index_experience(self.conn, eid, vector=vector)

    def test_default_recall_returns_validated_only(self):
        hits = exp.experience_hits(
            self.conn, query_vector=[1, 0, 0, 0], query_text="bounded timeout", k=5)
        self.assertEqual([h["experience_id"] for h in hits], ["good"])
        self.assertTrue(all(h["status"] == "validated" for h in hits))

    def test_diagnostic_mode_can_show_candidate_with_status_label(self):
        hits = exp.experience_hits(
            self.conn, query_vector=[1, 0, 0, 0], query_text="retry everything", k=5,
            statuses=("candidate",))
        self.assertEqual(hits[0]["experience_id"], "guess")
        self.assertEqual(hits[0]["status"], "candidate")

    def test_failure_advisory_requires_validated_failure_and_evidence(self):
        warning = exp.failure_advisory(
            self.conn, query_vector=[0, 1, 0, 0],
            query_text="restore graph community scene prior", min_score=0.0)
        self.assertEqual(warning["experience_id"], "bad")
        self.assertEqual(warning["outcome_state"], "failure")
        self.assertEqual(warning["advisory"], True)
        self.assertTrue(warning["source_refs"])
        self.assertTrue(warning["outcome_refs"])

    def test_unrelated_or_candidate_match_produces_no_warning(self):
        self.assertIsNone(exp.failure_advisory(
            self.conn, query_vector=[0, 0, 1, 0], query_text="unrelated", min_score=0.8))


if __name__ == "__main__":
    unittest.main()


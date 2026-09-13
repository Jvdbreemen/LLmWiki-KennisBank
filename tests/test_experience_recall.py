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
import _source_ref as source_ref  # noqa: E402


class ExperienceRecallContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = exp.connect(Path(self.tmp.name) / "experience.db")
        self.addCleanup(self.conn.close)
        exp.ensure_schema(self.conn)
        exp.ensure_recall_schema(self.conn, dim=4, embed_id="fake:4")
        source = Path(self.tmp.name) / "01-raw" / "transcripts" / "recall.md"
        source.parent.mkdir(parents=True)
        text = "good evidence\nbad evidence\nresolved evidence\n"
        source.write_text(text, encoding="utf-8")
        self.source_refs = {}
        for name, passage in (
            ("good", "good evidence"),
            ("bad", "bad evidence"),
            ("resolved", "resolved evidence"),
        ):
            start = text.index(passage)
            self.source_refs[name] = source_ref.make_source_ref(
                Path(self.tmp.name), "01-raw/transcripts/recall.md",
                start=start, end=start + len(passage), chunk_id=name)
        for eid, state, status, vector, lesson, refs in (
            ("good", "success", "validated", [1, 0, 0, 0],
             "Use a bounded timeout", ([self.source_refs["good"]], ["out-good"])),
            ("bad", "failure", "validated", [0, 1, 0, 0],
             "Avoid graph-community scene priors", ([self.source_refs["bad"]], ["out-bad"])),
            ("guess", "unknown", "candidate", [1, 0, 0, 0],
             "Retry everything", ([], [])),
        ):
            if refs[1]:
                exp.record_outcome(self.conn, outcome_id=refs[1][0], session_id="s",
                                   task_id="t", state=state,
                                   evidence=[{"kind": "test", "value": state}],
                                   attribution_strength="none")
            self._save_fixture(eid=eid, state=state, status=status,
                               lesson=lesson, source_refs=refs[0],
                               outcome_refs=refs[1])
            exp.index_experience(self.conn, eid, vector=vector)

    def _save_fixture(self, *, eid, state, status, lesson, source_refs,
                      outcome_refs, attempt_state="unknown",
                      resolution_state="not_applicable"):
        exp.save_experience(
            self.conn, experience_id=eid, session_id="s", task_id="t",
            status="candidate", situation=lesson, approach=lesson,
            observed_result=state, lesson=lesson, applicability="repo",
            outcome_state=state, attempt_state=attempt_state,
            resolution_state=resolution_state, confidence=0.2,
            source_refs=source_refs, outcome_refs=outcome_refs)
        if status != "validated":
            return
        self.assertTrue(all(
            source_ref.resolve_source_ref(Path(self.tmp.name), ref)["fresh"]
            for ref in source_refs))
        record = exp.experience(self.conn, eid)
        exp.record_review(
            self.conn, review_id=f"review-{eid}", experience_id=eid,
            decision="accepted", actor="test-human",
            reviewed_at="2026-09-05T10:00:00Z",
            reason="reviewed fixture", content_hash=record["content_hash"])
        exp.transition(self.conn, eid, "validated", vault=Path(self.tmp.name))

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

    def test_failure_advisory_default_is_the_calibrated_constant(self):
        import inspect

        default = inspect.signature(exp.failure_advisory).parameters["min_score"].default
        self.assertEqual(default, exp.FAILURE_ADVISORY_MIN_COS)
        self.assertEqual(default, 0.50)

    def test_failure_advisory_uses_failed_attempt_even_when_fix_succeeded(self):
        exp.record_outcome(
            self.conn, outcome_id="resolved-outcome", session_id="s", task_id="t",
            state="success",
            evidence=[{"source_refs": [self.source_refs["resolved"]]}],
            attribution_strength="reviewed")
        lesson = "do not hide rollback failures"
        self._save_fixture(
            eid="resolved-dead-end", state="success", status="validated",
            lesson=lesson, source_refs=[self.source_refs["resolved"]],
            outcome_refs=["resolved-outcome"], attempt_state="failure",
            resolution_state="fix_validated")
        exp.index_experience(self.conn, "resolved-dead-end", vector=[1.0, 0.0, 0.0, 0.0])

        warning = exp.failure_advisory(
            self.conn, query_vector=[1.0, 0.0, 0.0, 0.0],
            query_text="rollback failure", min_score=0.8)

        self.assertIsNotNone(warning)
        self.assertEqual(warning["experience_id"], "resolved-dead-end")
        self.assertEqual(warning["attempt_state"], "failure")
        self.assertEqual(warning["outcome_state"], "success")
        self.assertEqual(warning["resolution_state"], "fix_validated")


if __name__ == "__main__":
    unittest.main()

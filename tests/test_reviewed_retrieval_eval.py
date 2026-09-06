"""End-to-end reviewed experience retrieval evaluation contracts."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _reviewed_retrieval_eval as live  # noqa: E402
import _source_ref  # noqa: E402


class ReviewedRetrievalEvalTest(unittest.TestCase):
    def test_experience_eval_uses_real_projection_and_emits_aggregates_only(self):
        cases = [
            {"id": "E-1", "query": "bounded timeout",
             "expected_experience": "timeout", "expected_state": "success",
             "records": [{"experience_id": "timeout", "status": "validated",
                          "outcome_state": "success", "situation": "child hangs",
                          "approach": "bounded timeout", "action": "bound timeout",
                          "observed_result": "shutdown works",
                          "lesson": "use bounded timeout", "applicability": "shutdown",
                          "source_refs": ["raw#1"], "outcome_refs": ["out-1"]}]},
            {"id": "E-2", "query": "restore scene prior",
             "expected_experience": "scene", "expected_state": "failure",
             "records": [{"experience_id": "scene", "status": "validated",
                          "outcome_state": "failure", "situation": "scene prior",
                          "approach": "restore scene", "action": "avoid scene",
                          "observed_result": "recall regressed",
                          "lesson": "avoid scene prior", "applicability": "ranking",
                          "source_refs": ["raw#2"], "outcome_refs": ["out-2"]}]},
            {"id": "X-1", "query": "unrelated weather",
             "expected_experience": None, "expected_state": "unknown", "records": []},
        ]
        vectors = {
            "child hangs  bounded timeout bound timeout use bounded timeout shutdown": [1, 0, 0],
            "scene prior  restore scene avoid scene avoid scene prior ranking": [0, 1, 0],
            "bounded timeout": [1, 0, 0],
            "restore scene prior": [0, 1, 0],
            "unrelated weather": [0, 0, 1],
        }
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            source = vault / "01-raw" / "transcripts" / "eval.md"
            source.parent.mkdir(parents=True)
            text = "bounded timeout\nrestore scene prior\n"
            source.write_text(text, encoding="utf-8")
            for record, passage in ((cases[0]["records"][0], "bounded timeout"),
                                    (cases[1]["records"][0], "restore scene prior")):
                start = text.index(passage)
                record["source_refs"] = [_source_ref.make_source_ref(
                    vault, "01-raw/transcripts/eval.md", start=start,
                    end=start + len(passage), chunk_id=record["experience_id"])]
                record["review"] = {
                    "decision": "accepted", "actor": "test-owner",
                    "reviewed_at": "2026-09-05T10:00:00Z",
                    "reason": "reviewed evaluation fixture",
                }
            db = vault / "experience.db"
            report = live.evaluate_experience_holdout(
                cases, db_path=db, embed_fn=lambda text: vectors[text],
                embed_id="fake:3", advisory_min_cos=0.8, vault=vault)
        self.assertEqual(report["hybrid"]["retrieval"]["hit@3"], 1.0)
        self.assertEqual(report["hybrid"]["evidence_precision"], 1.0)
        self.assertEqual(report["hybrid"]["failure_hit@3"], 1.0)
        self.assertEqual(report["hybrid"]["false_warning_rate"], 0.0)
        self.assertEqual(report["advisory_precision"], 1.0)
        self.assertEqual(report["warning_probes"], 1)
        self.assertEqual(report["false_warnings"], 0)
        self.assertEqual(report["latency_ms"]["n"], 3)
        self.assertEqual(report["candidate_leakage"], 0)
        self.assertNotIn("query", repr(report).lower())
        self.assertNotIn("bounded timeout", repr(report).lower())

    def test_resolved_failed_attempt_counts_as_correct_advisory(self):
        cases = [{
            "id": "E-resolved", "query": "installer rollback failure",
            "expected_experience": "resolved", "expected_state": "success",
            "expected_attempt_state": "failure",
            "expected_resolution_state": "fix_validated",
            "records": [{
                "experience_id": "resolved", "status": "validated",
                "outcome_state": "success", "attempt_state": "failure",
                "resolution_state": "fix_validated",
                "situation": "installer rollback failure", "approach": "hide rollback",
                "action": "show both errors", "observed_result": "fix works",
                "lesson": "preserve both failures", "applicability": "installers",
                "source_refs": ["raw#1"], "outcome_refs": ["out-1"],
            }],
        }]
        vectors = {
            "installer rollback failure  hide rollback show both errors preserve both failures installers": [1, 0],
            "installer rollback failure": [1, 0],
        }
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            source = vault / "01-raw" / "transcripts" / "resolved.md"
            source.parent.mkdir(parents=True)
            passage = "installer rollback failure"
            source.write_text(passage, encoding="utf-8")
            cases[0]["records"][0]["source_refs"] = [_source_ref.make_source_ref(
                vault, "01-raw/transcripts/resolved.md", start=0,
                end=len(passage), chunk_id="resolved")]
            cases[0]["records"][0]["review"] = {
                "decision": "accepted", "actor": "test-owner",
                "reviewed_at": "2026-09-05T10:00:00Z",
                "reason": "reviewed evaluation fixture",
            }
            report = live.evaluate_experience_holdout(
                cases, db_path=vault / "experience.db",
                embed_fn=lambda text: vectors[text], embed_id="fake:2",
                advisory_min_cos=0.8, vault=vault)

        self.assertEqual(report["hybrid"]["failure_hit@3"], 1.0)
        self.assertEqual(report["advisories"], 1)
        self.assertEqual(report["correct_advisories"], 1)
        self.assertEqual(report["advisory_precision"], 1.0)


if __name__ == "__main__":
    unittest.main()

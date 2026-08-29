"""End-to-end reviewed experience retrieval evaluation contracts."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _reviewed_retrieval_eval as live  # noqa: E402


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
            db = Path(temp) / "experience.db"
            report = live.evaluate_experience_holdout(
                cases, db_path=db, embed_fn=lambda text: vectors[text],
                embed_id="fake:3", advisory_min_cos=0.8)
        self.assertEqual(report["hybrid"]["retrieval"]["hit@3"], 1.0)
        self.assertEqual(report["hybrid"]["failure_hit@3"], 1.0)
        self.assertEqual(report["hybrid"]["false_warning_rate"], 0.0)
        self.assertEqual(report["advisory_precision"], 1.0)
        self.assertEqual(report["warning_probes"], 1)
        self.assertEqual(report["false_warnings"], 0)
        self.assertEqual(report["latency_ms"]["n"], 3)
        self.assertEqual(report["candidate_leakage"], 0)
        self.assertNotIn("query", repr(report).lower())
        self.assertNotIn("bounded timeout", repr(report).lower())


if __name__ == "__main__":
    unittest.main()

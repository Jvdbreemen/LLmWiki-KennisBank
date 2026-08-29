"""Evaluation runner contracts; reports contain aggregates, never raw prompts."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _layer_eval_runner as runner  # noqa: E402


class LayerEvalRunnerTest(unittest.TestCase):
    def test_source_runner_measures_provenance_and_downstream_pair(self):
        cases = [
            {"id": "s1", "expected_source": "a.md"},
            {"id": "s2", "expected_source": None},
        ]
        def retrieve(case):
            if case["id"] == "s1":
                return [{"source_path": "a.md", "fresh": True,
                         "source_hash": "sha256:a", "start": 0, "end": 2,
                         "passage": "ok"}]
            return []
        result = runner.evaluate_source(cases, retrieve,
                                        answer_baseline=[False, True],
                                        answer_experiment=[True, True])
        self.assertEqual(result["retrieval"]["hit@5"], 1.0)
        self.assertEqual(result["provenance_precision"], 1.0)
        self.assertEqual(result["answer_delta"]["delta"], 0.5)
        self.assertNotIn("query", result)

    def test_source_runner_reports_conflict_handling(self):
        cases = [
            {"id": "conflict", "expected_source": "a.md", "expected_conflict": True},
            {"id": "plain", "expected_source": "b.md", "expected_conflict": False},
        ]
        def retrieve(case):
            return [{"source_path": case["expected_source"], "fresh": True,
                     "source_hash": "sha256:x", "start": 0, "end": 2,
                     "passage": "ok", "conflict": case["expected_conflict"]}]
        result = runner.evaluate_source(cases, retrieve)
        self.assertEqual(result["conflict_handling"], {"n": 2, "accuracy": 1.0})

    def test_experience_runner_counts_candidate_leakage_and_advisory_precision(self):
        cases = [
            {"id": "e1", "expected_experience": "good", "expected_state": "success"},
            {"id": "e2", "expected_experience": None, "expected_state": "unknown"},
        ]
        def retrieve(case):
            if case["id"] == "e1":
                return [{"experience_id": "good", "status": "validated",
                         "outcome_state": "success", "source_refs": ["a"],
                         "outcome_refs": ["o"]}]
            return [{"experience_id": "guess", "status": "candidate",
                     "outcome_state": "unknown", "source_refs": [],
                     "outcome_refs": []}]
        result = runner.evaluate_experience(cases, retrieve)
        self.assertEqual(result["retrieval"]["hit@3"], 1.0)
        self.assertEqual(result["candidate_leakage"], 1)
        self.assertEqual(result["evidence_precision"], 1.0)

    def test_experience_runner_reports_reuse_failure_rate_and_calibration(self):
        cases = [
            {"id": "s", "expected_experience": "good", "expected_state": "success"},
            {"id": "f", "expected_experience": "bad", "expected_state": "failure"},
            {"id": "u", "expected_experience": None, "expected_state": "unknown"},
        ]
        def retrieve(case):
            if case["id"] == "s":
                return [{"experience_id": "good", "status": "validated",
                         "outcome_state": "success", "source_refs": ["a"],
                         "outcome_refs": ["o"]}]
            if case["id"] == "f":
                return [{"experience_id": "bad", "status": "validated",
                         "outcome_state": "failure", "source_refs": ["b"],
                         "outcome_refs": ["p"]}]
            return []
        result = runner.evaluate_experience(cases, retrieve)
        self.assertEqual(result["useful_reuse@3"], 1.0)
        self.assertEqual(result["repeated_failure_rate"], 1.0)
        self.assertEqual(result["outcome_calibration"], 1.0)
        self.assertEqual(result["unsupported_lessons"], 0)


if __name__ == "__main__":
    unittest.main()

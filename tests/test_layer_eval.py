"""Pre-registered evaluation math and release-gate contracts."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _layer_eval as le  # noqa: E402


class RetrievalMetricTest(unittest.TestCase):
    def test_rank_metrics_include_not_found_precision(self):
        cases = [
            {"expected": "a", "hits": ["a", "b"]},
            {"expected": "b", "hits": ["a", "b"]},
            {"expected": None, "hits": []},
            {"expected": None, "hits": ["noise"]},
        ]
        metrics = le.retrieval_metrics(cases, cutoffs=(1, 3))
        self.assertEqual(metrics["positive_n"], 2)
        self.assertEqual(metrics["negative_n"], 2)
        self.assertEqual(metrics["hit@1"], 0.5)
        self.assertEqual(metrics["hit@3"], 1.0)
        self.assertEqual(metrics["no_hit_precision"], 0.5)

    def test_source_gate_rejects_small_or_provenance_imperfect_samples(self):
        good = le.source_gate_input_template()
        good.update({"positive_n": 30, "negative_n": 5, "hit@5": 0.8,
                     "lexical_hit@5": 0.6, "provenance_precision": 1.0,
                     "no_hit_precision": 0.8, "normal_p50_delta_ms": 0.0,
                     "normal_p95_delta_ms": 0.0, "source_p95_ms": 500.0,
                     "rebuild_preserved": True})
        self.assertTrue(le.source_gate(good)["passed"])
        for field, value in (("positive_n", 29), ("provenance_precision", 0.99),
                             ("normal_p95_delta_ms", 5.1), ("rebuild_preserved", False)):
            bad = dict(good)
            bad[field] = value
            self.assertFalse(le.source_gate(bad)["passed"], field)

    def test_experience_gate_rejects_candidate_leakage_and_false_warnings(self):
        good = le.experience_gate_input_template()
        good.update({"labelled_n": 20, "validated_hit@3": 0.8,
                     "lexical_hit@3": 0.6, "failure_hit@3": 0.8,
                     "evidence_precision": 1.0, "candidate_leakage": 0,
                     "false_warning_rate": 0.1, "normal_p50_delta_ms": 0.0,
                     "normal_p95_delta_ms": 0.0})
        self.assertTrue(le.experience_gate(good)["passed"])
        for field, value in (("candidate_leakage", 1), ("false_warning_rate", 0.11),
                             ("evidence_precision", 0.99), ("labelled_n", 19)):
            bad = dict(good)
            bad[field] = value
            self.assertFalse(le.experience_gate(bad)["passed"], field)

    def test_eval_environment_disables_usage_telemetry(self):
        saved = os.environ.pop("KB_USAGE_DISABLE", None)
        try:
            with le.evaluation_environment():
                self.assertEqual(os.environ.get("KB_USAGE_DISABLE"), "1")
            self.assertNotIn("KB_USAGE_DISABLE", os.environ)
        finally:
            if saved is not None:
                os.environ["KB_USAGE_DISABLE"] = saved


if __name__ == "__main__":
    unittest.main()


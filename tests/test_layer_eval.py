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
        good.update({"positive_n": 50, "negative_n": 10, "hit@5": 0.8,
                     "lexical_hit@5": 0.6, "provenance_precision": 1.0,
                     "no_hit_specificity": 0.95, "normal_p50_delta_ms": 0.0,
                     "normal_p95_delta_ms": 0.0, "source_p95_ms": 500.0,
                     "rebuild_preserved": True, "answer_pairs_n": 50,
                     "answer_correctness_delta": 0.10})
        self.assertTrue(le.source_gate(good)["passed"])
        for field, value in (("positive_n", 49), ("provenance_precision", 0.99),
                             ("normal_p95_delta_ms", 5.1), ("rebuild_preserved", False)):
            bad = dict(good)
            bad[field] = value
            self.assertFalse(le.source_gate(bad)["passed"], field)

    def test_experience_gate_rejects_candidate_leakage_and_false_warnings(self):
        good = le.experience_gate_input_template()
        good.update({"labelled_n": 60, "validated_hit@3": 0.8,
                     "lexical_hit@3": 0.6, "failure_hit@3": 0.8,
                     "evidence_precision": 1.0, "candidate_leakage": 0,
                     "false_warning_rate": 0.1, "advisory_precision": 0.9,
                     "normal_p50_delta_ms": 0.0,
                     "normal_p95_delta_ms": 0.0, "action_pairs_n": 60,
                     "action_correctness_delta": 0.10})
        self.assertTrue(le.experience_gate(good)["passed"])
        for field, value in (("candidate_leakage", 1), ("false_warning_rate", 0.11),
                             ("evidence_precision", 0.99), ("labelled_n", 59)):
            bad = dict(good)
            bad[field] = value
            self.assertFalse(le.experience_gate(bad)["passed"], field)

    def test_exact_ten_point_hybrid_delta_is_not_lost_to_float_rounding(self):
        good = le.experience_gate_input_template()
        good.update({"labelled_n": 60, "validated_hit@3": 0.9,
                     "lexical_hit@3": 0.8, "failure_hit@3": 0.8,
                     "evidence_precision": 1.0, "candidate_leakage": 0,
                     "false_warning_rate": 0.1, "advisory_precision": 0.9,
                     "normal_p50_delta_ms": 0.0, "normal_p95_delta_ms": 0.0,
                     "action_pairs_n": 60, "action_correctness_delta": 0.10})
        self.assertTrue(le.experience_gate(good)["passed"])

    def test_eval_environment_disables_usage_telemetry(self):
        saved = os.environ.pop("KB_USAGE_DISABLE", None)
        try:
            with le.evaluation_environment():
                self.assertEqual(os.environ.get("KB_USAGE_DISABLE"), "1")
            self.assertNotIn("KB_USAGE_DISABLE", os.environ)
        finally:
            if saved is not None:
                os.environ["KB_USAGE_DISABLE"] = saved

    def test_paired_delta_reports_direction_and_interval(self):
        result = le.paired_binary_delta(
            [False, True, False, True], [True, True, True, True], bootstrap=200)
        self.assertEqual(result["n"], 4)
        self.assertEqual(result["delta"], 0.5)
        self.assertEqual(result["baseline_correct"], 2)
        self.assertEqual(result["experiment_correct"], 4)
        self.assertLessEqual(result["ci_low"], result["delta"])
        self.assertGreaterEqual(result["ci_high"], result["delta"])

    def test_paired_delta_rejects_unpaired_inputs(self):
        with self.assertRaises(ValueError):
            le.paired_binary_delta([True], [True, False])

    def test_arm_coverage_requires_all_six_or_explicit_omissions(self):
        with self.assertRaisesRegex(ValueError, "missing arms"):
            le.validate_arm_coverage({"A": {}, "B": {}})
        covered = le.validate_arm_coverage(
            {"A": {}, "B": {}, "C": {}, "D": {}, "E": {},
             "F": {}, "omissions": {}}
        )
        self.assertEqual(covered["missing"], [])
        omitted = le.validate_arm_coverage(
            {"A": {}, "B": {}, "C": {}, "D": {}, "omissions": {
                "E": "experience holdout unavailable", "F": "research-only not run"}}
        )
        self.assertEqual(omitted["missing"], ["E", "F"])

    def test_latency_summary_is_deterministic_and_separate_from_route_metrics(self):
        result = le.latency_summary([3, 7, 9, 10, 100])
        self.assertEqual(result, {"n": 5, "p50_ms": 9.0, "p95_ms": 100.0})

    def test_decision_table_distinguishes_go_hold_and_reject(self):
        source = le.source_gate_input_template()
        source.update({"positive_n": 50, "negative_n": 10, "hit@5": 0.8,
                       "lexical_hit@5": 0.6, "provenance_precision": 1.0,
                       "no_hit_specificity": 0.95, "normal_p50_delta_ms": 0.0,
                       "normal_p95_delta_ms": 0.0, "source_p95_ms": 500.0,
                       "rebuild_preserved": True, "answer_pairs_n": 50,
                       "answer_correctness_delta": 0.10})
        experience = le.experience_gate_input_template()
        experience.update({"labelled_n": 60, "validated_hit@3": 0.8,
                            "lexical_hit@3": 0.6, "failure_hit@3": 0.8,
                            "evidence_precision": 1.0, "candidate_leakage": 0,
                            "false_warning_rate": 0.1, "advisory_precision": 0.9,
                            "normal_p50_delta_ms": 0.0, "normal_p95_delta_ms": 0.0,
                            "action_pairs_n": 60, "action_correctness_delta": 0.10})
        self.assertEqual(le.decision_table(source, experience)["source"], "go")
        hold = dict(source)
        hold["positive_n"] = 49
        self.assertEqual(le.decision_table(hold, experience)["source"], "hold")
        missing_pairs = dict(source)
        missing_pairs["answer_pairs_n"] = 0
        self.assertEqual(le.decision_table(missing_pairs, experience)["source"], "hold")
        missing_actions = dict(experience)
        missing_actions["action_pairs_n"] = 0
        self.assertEqual(le.decision_table(source, missing_actions)["experience"], "hold")
        unsafe_incomplete = dict(missing_actions)
        unsafe_incomplete["false_warning_rate"] = 0.2
        self.assertEqual(le.decision_table(source, unsafe_incomplete)["experience"],
                         "reject")
        reject = dict(source)
        reject["provenance_precision"] = 0.99
        self.assertEqual(le.decision_table(reject, experience)["source"], "reject")


if __name__ == "__main__":
    unittest.main()

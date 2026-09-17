"""Contracts for the private advisory-development calibration runner."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "calibrate-experience-advisory.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("advisory_calibration_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def positive_case():
    return {
        "case_id": "D-001",
        "query": "A private positive query",
        "expected_advisory": True,
        "expected_experience": {
            "outcome": "the fix worked",
            "failed_approach": "reuse the stale cache key",
            "recommended_action": "key the cache on its real input",
            "scope": "derived caches",
            "tradeoff": "one migration",
        },
        "expected_state": "success",
        "expected_attempt_state": "failure",
        "expected_resolution_state": "fix_validated",
        "evidence_sources": [{
            "path": "01-raw/a.md", "hash": "sha256:abc",
            "windows": [{"start": 10, "end": 20}],
        }],
        "review_status": "reviewed", "review_decision": "keep",
    }


def negative_case():
    return {
        "case_id": "D-002",
        "query": "A private factual query",
        "expected_advisory": False,
        "expected_experience": None,
        "expected_state": "unknown",
        "expected_attempt_state": "unknown",
        "expected_resolution_state": "not_applicable",
        "evidence_sources": [{
            "path": "01-raw/b.md", "hash": "sha256:def",
            "windows": [{"start": 30, "end": 40}],
        }],
        "review_status": "reviewed", "review_decision": "keep",
    }


class AdvisoryCalibrationCliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner()

    def test_reviewed_set_requires_kept_positive_and_negative_cases(self):
        cases = self.runner.validate_cases([positive_case(), negative_case()])
        self.assertEqual(len(cases), 2)

        pending = positive_case()
        pending["review_status"] = "proposed"
        with self.assertRaisesRegex(ValueError, "reviewed and kept"):
            self.runner.validate_cases([pending, negative_case()])
        with self.assertRaisesRegex(ValueError, "positive and negative"):
            self.runner.validate_cases([positive_case()])

    def test_positive_record_preserves_axes_and_exact_source_windows(self):
        record = self.runner.record_for(positive_case())

        self.assertEqual(record["experience_id"], "D-001")
        self.assertEqual(record["attempt_state"], "failure")
        self.assertEqual(record["resolution_state"], "fix_validated")
        self.assertEqual(record["outcome_state"], "success")
        self.assertEqual(
            record["source_refs"], ["01-raw/a.md#10:20@sha256:abc"])
        self.assertIn("key the cache", record["lesson"])
        self.assertIsNone(self.runner.record_for(negative_case()))

    def test_report_is_aggregate_and_requires_hybrid_gain(self):
        cases = [positive_case(), negative_case()]
        hybrid = [
            {"id": "D-001", "candidate_experience": "D-001", "score": 0.85},
            {"id": "D-002", "candidate_experience": "D-001", "score": 0.65},
        ]
        lexical = [
            {"id": "D-001", "candidate_experience": None},
            {"id": "D-002", "candidate_experience": "D-001"},
        ]

        report = self.runner.calibration_report(
            cases, hybrid, lexical, thresholds=[0.5, 0.7, 0.8],
            embedding_id="fake:4")

        self.assertEqual(report["selected_threshold"], 0.8)
        self.assertEqual(report["selected"]["positive_recall"], 1.0)
        self.assertEqual(report["selected"]["false_warning_rate"], 0.0)
        self.assertEqual(report["lexical"]["positive_recall"], 0.0)
        self.assertTrue(report["hybrid_vs_lexical"]["passes"])
        serialized = json.dumps(report)
        self.assertNotIn("private positive query", serialized.lower())
        self.assertNotIn("stale cache key", serialized.lower())


if __name__ == "__main__":
    unittest.main()

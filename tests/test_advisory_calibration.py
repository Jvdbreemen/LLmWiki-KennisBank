"""Independent development-set and advisory calibration contracts."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "dev"))

import _advisory_calibration as calibration  # noqa: E402


class AdvisoryDevelopmentSetTest(unittest.TestCase):
    def test_dev_queries_and_source_sessions_must_not_overlap_frozen_holdout(self):
        frozen = [{
            "id": "E-001", "query": "Why did the cache fail?",
            "records": [{"source_refs": ["01-raw/transcripts/frozen.jsonl#10:20@sha256:a"]}],
        }]
        clean = [{
            "id": "D-001", "query": "Why did the installer rollback fail?",
            "records": [{"source_refs": ["01-raw/transcripts/dev.jsonl#1:9@sha256:b"]}],
        }]
        calibration.assert_independent(clean, frozen)

        with self.assertRaisesRegex(ValueError, "query overlap"):
            calibration.assert_independent(
                [{"id": "D-002", "query": " WHY  did the cache fail? ", "records": []}],
                frozen)
        with self.assertRaisesRegex(ValueError, "source overlap"):
            calibration.assert_independent(
                [{"id": "D-003", "query": "different",
                  "records": [{"source_refs": [
                      "01-raw/transcripts/frozen.jsonl#30:40@sha256:a"]}]}],
                frozen)

    def test_threshold_maximizes_recall_subject_to_safety_constraints(self):
        observations = [
            {"id": "P-1", "expected_experience": "x1",
             "candidate_experience": "x1", "score": 0.90},
            {"id": "P-2", "expected_experience": "x2",
             "candidate_experience": "x2", "score": 0.75},
            {"id": "N-1", "expected_experience": None,
             "candidate_experience": "x3", "score": 0.65},
        ]

        result = calibration.calibrate_threshold(
            observations, thresholds=[0.5, 0.7, 0.8],
            min_precision=0.9, max_false_warning_rate=0.1)

        self.assertEqual(result["selected_threshold"], 0.7)
        self.assertEqual(result["selected"]["positive_recall"], 1.0)
        self.assertEqual(result["selected"]["precision"], 1.0)
        self.assertEqual(result["selected"]["false_warning_rate"], 0.0)
        self.assertEqual(result["selection_source"], "development_only")

    def test_no_unsafe_threshold_is_silently_selected(self):
        observations = [
            {"id": "P-1", "expected_experience": "x1",
             "candidate_experience": "wrong", "score": 0.9},
            {"id": "N-1", "expected_experience": None,
             "candidate_experience": "wrong", "score": 0.9},
        ]

        result = calibration.calibrate_threshold(
            observations, thresholds=[0.5, 0.8],
            min_precision=0.9, max_false_warning_rate=0.1)

        self.assertIsNone(result["selected_threshold"])
        self.assertEqual(result["reason"], "no_threshold_meets_safety_constraints")

    def test_hybrid_candidate_needs_gain_over_lexical_arm(self):
        accepted = calibration.compare_to_lexical(
            {"positive_recall": 0.8}, {"positive_recall": 0.6})
        rejected = calibration.compare_to_lexical(
            {"positive_recall": 0.8}, {"positive_recall": 0.8})

        self.assertTrue(accepted["passes"])
        self.assertAlmostEqual(accepted["delta"], 0.2)
        self.assertFalse(rejected["passes"])
        self.assertEqual(rejected["reason"], "no_hybrid_recall_gain")


if __name__ == "__main__":
    unittest.main()

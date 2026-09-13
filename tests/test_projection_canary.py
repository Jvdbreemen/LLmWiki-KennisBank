"""Owner-vault canary contracts for the deeper recall projections."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _projection_canary as canary  # noqa: E402


def _source(index: int) -> dict:
    return {
        "schema_version": 1,
        "canary_id": f"source-{index:02d}",
        "layer": "source",
        "route": "exact_ref",
        "observed_at": f"2026-09-07T09:{index:02d}:00Z",
        "result_status": "ok",
        "shown_count": 1,
        "latency_ms": 8.0 + index,
        "owner_reviewed": True,
        "reconstruction_correct": True,
        "provenance_correct": True,
        "candidate_leakage": 0,
        "idempotency_key": f"source-{index:02d}",
    }


def _experience(index: int, *, useful: bool = True,
                harmful: bool = False) -> dict:
    return {
        "schema_version": 1,
        "canary_id": f"experience-{index:02d}",
        "layer": "experience",
        "route": "lexical_fallback",
        "observed_at": f"2026-09-07T10:{index:02d}:00Z",
        "result_status": "ok",
        "shown_count": 2,
        "latency_ms": 12.0 + index,
        "owner_reviewed": True,
        "natural_explicit_use": True,
        "useful": useful,
        "harmful": harmful,
        "evidence_correct": True,
        "candidate_leakage": 0,
        "idempotency_key": f"experience-{index:02d}",
    }


class ProjectionCanaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "private-canary.jsonl"

    def test_append_is_idempotent_and_refuses_changed_reuse(self):
        row = _source(1)
        self.assertTrue(canary.append_record(self.log, row))
        self.assertFalse(canary.append_record(self.log, row))
        changed = dict(row, latency_ms=999.0)
        with self.assertRaisesRegex(ValueError, "idempotency"):
            canary.append_record(self.log, changed)
        self.assertEqual(len(self.log.read_text(encoding="utf-8").splitlines()), 1)

    def test_record_schema_refuses_raw_private_content(self):
        for field in ("prompt", "query", "passage", "lesson", "source_path",
                      "source_ref", "embedding"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "content field"):
                    canary.validate_record(dict(_source(1), **{field: "secret"}))

    def test_passing_canary_requires_ten_source_then_twenty_natural_experience(self):
        rows = [_source(i) for i in range(10)]
        rows.extend(_experience(i) for i in range(20))
        report = canary.aggregate(rows)
        self.assertTrue(report["source"]["passed"])
        self.assertTrue(report["experience"]["passed"])
        self.assertTrue(report["sequence"]["source_before_experience"])
        self.assertEqual(report["source"]["provenance_precision"], 1.0)
        self.assertEqual(report["experience"]["useful_rate"], 1.0)
        self.assertEqual(report["experience"]["evidence_precision"], 1.0)
        def keys(value):
            if isinstance(value, dict):
                return set(value).union(*(keys(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(item) for item in value))
            return set()
        for private in ("canary_id", "prompt", "passage", "source_path",
                        "idempotency_key"):
            self.assertNotIn(private, keys(report))

    def test_gate_does_not_average_safety_failures_away(self):
        rows = [_source(i) for i in range(10)]
        experiences = [_experience(i) for i in range(20)]
        experiences[0]["harmful"] = True
        experiences[1]["evidence_correct"] = False
        experiences[2]["candidate_leakage"] = 1
        report = canary.aggregate(rows + experiences)
        self.assertFalse(report["experience"]["passed"])
        self.assertEqual(report["experience"]["harmful_rate"], 0.05)
        self.assertIn("evidence_precision", report["experience"]["failed"])
        self.assertIn("candidate_leakage", report["experience"]["failed"])

    def test_experience_before_source_gate_is_a_hard_sequence_failure(self):
        early = _experience(0)
        early["observed_at"] = "2026-09-07T08:00:00Z"
        rows = [early] + [_source(i) for i in range(10)]
        rows.extend(_experience(i) for i in range(1, 20))
        report = canary.aggregate(rows)
        self.assertFalse(report["sequence"]["source_before_experience"])
        self.assertFalse(report["experience"]["passed"])
        self.assertIn("source_before_experience", report["experience"]["failed"])

    def test_non_natural_or_non_owner_reviewed_rows_do_not_satisfy_sample_gate(self):
        rows = [_source(i) for i in range(10)]
        experiences = [_experience(i) for i in range(20)]
        experiences[0]["natural_explicit_use"] = False
        experiences[1]["owner_reviewed"] = False
        report = canary.aggregate(rows + experiences)
        self.assertEqual(report["experience"]["eligible_n"], 18)
        self.assertFalse(report["experience"]["passed"])
        self.assertIn("minimum_natural_explicit_reviews", report["experience"]["failed"])

    def test_empty_report_does_not_claim_an_unmeasured_safety_rate_passes(self):
        report = canary.aggregate([])
        self.assertFalse(report["experience"]["checks"]["harmful_rate"])
        self.assertIn("harmful_rate", report["experience"]["failed"])


if __name__ == "__main__":
    unittest.main()

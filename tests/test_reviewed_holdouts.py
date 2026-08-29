"""Contracts for promoting interactive reviews into private eval holdouts."""
from __future__ import annotations

import sys
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _reviewed_holdouts as reviewed  # noqa: E402


def _kept(**overrides):
    case = {
        "case_id": "S-001",
        "layer": "source_recall",
        "query": "Which source proves the claim?",
        "gold_verdict": "found",
        "expected_source": "01-raw/transcripts/session.jsonl",
        "expected_source_hash": "sha256:" + "a" * 64,
        "expected_windows": [{"start": 10, "end": 20}],
        "category": "provenance",
        "language": "nl",
        "sensitive": False,
        "review_status": "reviewed",
        "review_decision": "keep",
        "gold_answer": "private answer",
        "required_answer_points": ["private point"],
    }
    case.update(overrides)
    return case


class ReviewedHoldoutsTest(unittest.TestCase):
    def test_source_promotion_maps_review_schema_and_drops_answer_payload(self):
        result = reviewed.prepare_source_cases([_kept()])
        self.assertEqual(result, [{
            "id": "S-001",
            "query": "Which source proves the claim?",
            "expected_source": "01-raw/transcripts/session.jsonl",
            "expected_verdict": "source",
            "expected_hash": "sha256:" + "a" * 64,
            "expected_windows": [{"start": 10, "end": 20}],
            "category": "provenance",
            "language": "nl",
            "sensitive": False,
        }])
        self.assertNotIn("private answer", repr(result))
        self.assertNotIn("private point", repr(result))

    def test_source_negative_verdicts_have_no_source_coordinates(self):
        cases = reviewed.prepare_source_cases([
            _kept(case_id="S-002", gold_verdict="unknown",
                  expected_source=None, expected_source_hash=None,
                  expected_windows=[]),
            _kept(case_id="S-003", gold_verdict="not_found",
                  expected_source=None, expected_source_hash=None,
                  expected_windows=[]),
        ])
        self.assertEqual([case["expected_verdict"] for case in cases],
                         ["unknown", "not_found"])
        self.assertTrue(all(case["expected_source"] is None for case in cases))

    def test_unreviewed_or_rejected_rows_are_refused_not_silently_skipped(self):
        for row in (
            _kept(review_status="draft"),
            _kept(review_decision="reject"),
        ):
            with self.subTest(row=row):
                with self.assertRaisesRegex(ValueError, "reviewed and kept"):
                    reviewed.prepare_source_cases([row])

    def test_experience_promotion_requires_explicit_normalized_state(self):
        row = _kept(
            case_id="E-001", layer="experience_recall",
            gold_verdict="validated_experience",
            expected_source=None, expected_source_hash=None, expected_windows=None,
            expected_experience={
                "outcome": "bounded fix worked",
                "recommended_action": "keep the timeout",
                "scope": "shutdown helpers",
                "tradeoff": "slower failure path",
            },
            evidence_sources=[{
                "path": "01-raw/transcripts/session.jsonl",
                "hash": "sha256:" + "b" * 64,
                "windows": [{"start": 30, "end": 50}],
            }],
        )
        with self.assertRaisesRegex(ValueError, "normalized experience state"):
            reviewed.prepare_experience_cases([row], states={})

    def test_experience_promotion_builds_stable_evidence_bound_record(self):
        row = _kept(
            case_id="E-001", layer="experience_recall",
            gold_verdict="validated_experience",
            expected_source=None, expected_source_hash=None, expected_windows=None,
            expected_experience={
                "outcome": "bounded fix worked",
                "recommended_action": "keep the timeout",
                "scope": "shutdown helpers",
                "tradeoff": "slower failure path",
            },
            evidence_sources=[{
                "path": "01-raw/transcripts/session.jsonl",
                "hash": "sha256:" + "b" * 64,
                "windows": [{"start": 30, "end": 50}],
            }],
        )
        result = reviewed.prepare_experience_cases(
            [row], states={"E-001": "success"})
        case = result[0]
        self.assertEqual(case["id"], "E-001")
        self.assertEqual(case["expected_state"], "success")
        self.assertEqual(case["expected_experience"],
                         "reviewed-experience-e-001")
        record = case["records"][0]
        self.assertEqual(record["experience_id"], case["expected_experience"])
        self.assertEqual(record["status"], "validated")
        self.assertEqual(record["outcome_state"], "success")
        self.assertTrue(record["source_refs"])
        self.assertTrue(record["outcome_refs"])
        self.assertNotIn("private answer", repr(result))
        self.assertNotIn("private point", repr(result))

    def test_experience_promotion_accepts_diagnostic_and_procedure_shapes(self):
        diagnostic = _kept(
            case_id="E-002", layer="experience_recall",
            gold_verdict="validated_experience",
            expected_source=None, expected_source_hash=None, expected_windows=None,
            expected_experience={
                "outcome": "failed_approach_with_fix",
                "failed_approach": "wait for one process",
                "fix": "terminate the complete process tree",
                "lesson": "bind the budget to the complete tree",
                "scope": "Windows process supervision",
            },
            evidence_sources=[{
                "path": "01-raw/transcripts/session.jsonl",
                "hash": "sha256:" + "c" * 64,
                "windows": [{"start": 1, "end": 4}],
            }],
        )
        procedure = _kept(
            case_id="E-003", layer="experience_recall",
            gold_verdict="validated_experience",
            expected_source=None, expected_source_hash=None, expected_windows=None,
            expected_experience={
                "outcome": "reproducible_evaluation_practice",
                "recommended_procedure": ["isolate corpus", "measure p95"],
                "scope": "embedding evaluation",
            },
            evidence_sources=[{
                "path": "02-wiki/evaluation.md",
                "hash": "sha256:" + "d" * 64,
                "windows": [{"start": 2, "end": 8}],
            }],
        )
        cases = reviewed.prepare_experience_cases(
            [diagnostic, procedure],
            states={"E-002": "mixed", "E-003": "success"})
        self.assertEqual(cases[0]["records"][0]["action"],
                         "terminate the complete process tree")
        self.assertIn("isolate corpus", cases[1]["records"][0]["action"])

    def test_experience_without_action_field_keeps_complete_reviewed_proposition(self):
        transfer = _kept(
            case_id="E-015", layer="experience_recall",
            gold_verdict="validated_experience",
            expected_source=None, expected_source_hash=None, expected_windows=None,
            expected_experience={
                "outcome": "retraction_propagates_through_derived_layers",
                "invalidation_targets": ["chunks", "embeddings", "citations"],
                "verification": "retrieval must not return retracted content",
            },
            evidence_sources=[{
                "path": "02-wiki/retraction.md",
                "hash": "sha256:" + "e" * 64,
                "windows": [{"start": 2, "end": 8}],
            }],
        )
        record = reviewed.prepare_experience_cases(
            [transfer], states={"E-015": "success"})[0]["records"][0]
        self.assertIn("chunks", record["action"])
        self.assertIn("retracted content", record["action"])

    def test_duplicate_case_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            reviewed.prepare_source_cases([_kept(), _kept()])

    def test_reviewed_source_negatives_become_explicit_cross_layer_probes(self):
        source_cases = reviewed.prepare_source_cases([
            _kept(case_id="S-009", gold_verdict="unknown",
                  expected_source=None, expected_source_hash=None,
                  expected_windows=[]),
            _kept(case_id="S-010", gold_verdict="not_found",
                  expected_source=None, expected_source_hash=None,
                  expected_windows=[]),
            _kept(case_id="S-011"),
        ])
        probes = reviewed.prepare_experience_negative_probes(source_cases)
        self.assertEqual([case["id"] for case in probes],
                         ["XP-S-009", "XP-S-010"])
        self.assertTrue(all(case["expected_experience"] is None for case in probes))
        self.assertTrue(all(case["expected_state"] == "unknown" for case in probes))
        self.assertTrue(all(case["records"] == [] for case in probes))

    def test_cli_writes_private_inputs_and_prints_aggregate_counts_only(self):
        experience = _kept(
            case_id="E-001", layer="experience_recall",
            gold_verdict="validated_experience",
            expected_source=None, expected_source_hash=None, expected_windows=None,
            expected_experience={
                "outcome": "bounded fix worked",
                "recommended_action": "keep the timeout",
                "scope": "shutdown helpers",
                "tradeoff": "slower failure path",
            },
            evidence_sources=[{
                "path": "01-raw/transcripts/session.jsonl",
                "hash": "sha256:" + "b" * 64,
                "windows": [{"start": 30, "end": 50}],
            }],
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviews = root / "reviews.jsonl"
            reviews.write_text(
                "\n".join(json.dumps(row) for row in (_kept(), experience)) + "\n",
                encoding="utf-8")
            states = root / "states.json"
            states.write_text(json.dumps({"E-001": "success"}), encoding="utf-8")
            output = root / "private-holdouts"
            result = subprocess.run(
                [sys.executable, "scripts/prepare-reviewed-holdouts.py",
                 "--reviews", str(reviews), "--experience-states", str(states),
                 "--output-dir", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["counts"], {"experience": 1, "source": 1})
            self.assertNotIn("private answer", result.stdout)
            self.assertNotIn("Which source", result.stdout)
            self.assertEqual(len((output / "source-cases.jsonl").read_text(
                encoding="utf-8").splitlines()), 1)
            self.assertEqual(len((output / "experience-cases.jsonl").read_text(
                encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()

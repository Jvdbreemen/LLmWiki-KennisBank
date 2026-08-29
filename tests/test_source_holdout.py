"""Privacy-safe, provenance-aware source holdout contracts.

The holdout manifest is an evaluation oracle, not a second raw-source store.
It may keep a query and source coordinates, but must never persist passages,
answers, or arbitrary raw fixture payloads.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _source_holdout as holdout  # noqa: E402


class SourceHoldoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        source = self.vault / "01-raw" / "transcripts" / "session-a.md"
        source.parent.mkdir(parents=True)
        source.write_text("prefix historical fact and outcome suffix", encoding="utf-8")

    def test_positive_case_is_frozen_with_hash_and_valid_window(self):
        case = {
            "id": "src-001",
            "query": "What was the historical outcome?",
            "expected_source": "01-raw/transcripts/session-a.md",
            "expected_windows": [{"start": 7, "end": 29}],
        }
        frozen = holdout.validate_case(case, self.vault)
        self.assertEqual(frozen["expected_verdict"], "source")
        self.assertTrue(frozen["expected_hash"].startswith("sha256:"))
        self.assertEqual(frozen["expected_windows"], [{"start": 7, "end": 29}])

    def test_negative_case_requires_not_found_or_unknown_verdict(self):
        with self.assertRaisesRegex(ValueError, "expected_verdict"):
            holdout.validate_case(
                {"id": "src-002", "query": "missing", "expected_source": None},
                self.vault,
            )
        for verdict in ("not_found", "unknown"):
            frozen = holdout.validate_case(
                {"id": verdict, "query": "missing", "expected_source": None,
                 "expected_verdict": verdict},
                self.vault,
            )
            self.assertIsNone(frozen["expected_source"])

    def test_invalid_source_and_window_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "approved"):
            holdout.validate_case(
                {"id": "src-003", "query": "x", "expected_source": "outside.md",
                 "expected_windows": [{"start": 0, "end": 1}]},
                self.vault,
            )
        with self.assertRaisesRegex(ValueError, "window"):
            holdout.validate_case(
                {"id": "src-004", "query": "x",
                 "expected_source": "01-raw/transcripts/session-a.md",
                 "expected_windows": [{"start": 0, "end": 999}]},
                self.vault,
            )

    def test_redacted_source_cannot_become_a_positive_fixture(self):
        redacted = self.vault / "01-raw" / "transcripts" / "private.redacted.md"
        redacted.write_text("sensitive local content", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "redacted"):
            holdout.validate_case(
                {"id": "src-005", "query": "x", "expected_source": redacted.relative_to(self.vault).as_posix(),
                 "expected_windows": [{"start": 0, "end": 1}]},
                self.vault,
            )

    def test_sensitive_positive_fixture_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "sensitive"):
            holdout.validate_case(
                {"id": "src-005b", "query": "x", "sensitive": True,
                 "expected_source": "01-raw/transcripts/session-a.md",
                 "expected_windows": [{"start": 0, "end": 1}]},
                self.vault,
            )

    def test_freeze_manifest_strips_raw_payloads_and_is_versioned(self):
        output = self.vault / "holdout.json"
        cases = [{
            "id": "src-006",
            "query": "What was the fact?",
            "expected_source": "01-raw/transcripts/session-a.md",
            "expected_windows": [{"start": 7, "end": 29}],
            "answer": "must not be persisted",
            "documents": [{"path": "x", "text": "must not be persisted"}],
        }]
        result = holdout.freeze_manifest(cases, self.vault, output)
        self.assertEqual(result["schema_version"], 1)
        written = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(written["cases"][0]["id"], "src-006")
        serialized = output.read_text(encoding="utf-8")
        self.assertNotIn("must not be persisted", serialized)
        self.assertNotIn("documents", written["cases"][0])
        self.assertNotIn("answer", written["cases"][0])

    def test_duplicate_ids_are_rejected_before_write(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            holdout.freeze_manifest([
                {"id": "same", "query": "a", "expected_source": None,
                 "expected_verdict": "unknown"},
                {"id": "same", "query": "b", "expected_source": None,
                 "expected_verdict": "not_found"},
            ], self.vault, Path(self.tmp.name) / "duplicate.json")

    def test_oracle_report_distinguishes_answerable_and_intentionally_unknown(self):
        manifest = self.vault / "holdout.json"
        holdout.freeze_manifest([
            {"id": "source", "query": "fact", "expected_source": "01-raw/transcripts/session-a.md",
             "expected_windows": [{"start": 7, "end": 29}]},
            {"id": "missing", "query": "missing", "expected_source": None,
             "expected_verdict": "not_found"},
            {"id": "uncertain", "query": "uncertain", "expected_source": None,
             "expected_verdict": "unknown"},
        ], self.vault, manifest)
        report = holdout.oracle_report(holdout.load_manifest(manifest), self.vault)
        self.assertEqual(report["oracle"]["positive_cases"], 1)
        self.assertEqual(report["oracle"]["answerable_positive"], 1)
        self.assertEqual(report["oracle"]["unrecoverable_positive"], 0)
        self.assertEqual(report["oracle"]["ceiling"], 1.0)
        self.assertEqual(report["verdicts"], {"source": 1, "not_found": 1, "unknown": 1})
        self.assertNotIn("fact", json.dumps(report))

    def test_oracle_report_marks_changed_source_as_unrecoverable(self):
        manifest = self.vault / "holdout.json"
        holdout.freeze_manifest([{
            "id": "stale", "query": "fact",
            "expected_source": "01-raw/transcripts/session-a.md",
            "expected_windows": [{"start": 7, "end": 29}],
        }], self.vault, manifest)
        source = self.vault / "01-raw" / "transcripts" / "session-a.md"
        source.write_text("changed local source", encoding="utf-8")
        report = holdout.oracle_report(holdout.load_manifest(manifest), self.vault)
        self.assertEqual(report["oracle"]["answerable_positive"], 0)
        self.assertEqual(report["oracle"]["unrecoverable_positive"], 1)
        self.assertEqual(report["oracle"]["ceiling"], 0.0)
        self.assertEqual(report["oracle"]["reasons"], {"hash_mismatch": 1})


if __name__ == "__main__":
    unittest.main()

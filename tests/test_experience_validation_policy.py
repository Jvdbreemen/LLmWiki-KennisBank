"""Production experience validation is evidence- and human-gated."""
from __future__ import annotations

import importlib
import sqlite3
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


class ExperienceValidationPolicyContractTest(unittest.TestCase):
    def setUp(self):
        self.experience = importlib.import_module("_experience")
        self.extract = importlib.import_module("_experience_extract")
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.experience.ensure_schema(self.conn)

    def _record_outcome(self):
        self.experience.record_outcome(
            self.conn, outcome_id="out-1", session_id="s1", task_id="t1",
            state="success", evidence=["tests passed"],
            attribution_strength="correlated")

    def test_schema_separates_evidence_review_and_lifecycle_state(self):
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(experiences)")}
        tables = {row[0] for row in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"evidence_state", "review_state", "content_hash"} <= columns)
        self.assertIn("experience_reviews", tables)

    def test_validated_write_without_verified_evidence_and_review_is_rejected(self):
        self._record_outcome()
        with self.assertRaises(ValueError):
            self.experience.save_experience(
                self.conn, experience_id="exp-1", session_id="s1", task_id="t1",
                status="validated", situation="s", approach="a",
                observed_result="r", lesson="l", applicability="scope",
                outcome_state="success", confidence=0.9,
                source_refs=["01-raw/transcripts/one.md"], outcome_refs=["out-1"])

    def test_extractor_can_only_create_an_unreviewed_candidate(self):
        self.experience.append_event(
            self.conn, event_id="evt-1", session_id="s1", task_id="t1",
            event_type="attempt", observed_at="2026-09-04T00:00:00Z",
            payload={"situation": "s", "approach": "a", "lesson": "l"},
            source_refs=["01-raw/transcripts/one.md"])
        self._record_outcome()
        record = self.extract.derive_experience(self.conn, "s1", "t1", "exp-1")
        self.assertEqual(record["status"], "candidate")
        self.assertEqual(record["evidence_state"], "unverified")
        self.assertEqual(record["review_state"], "unreviewed")


if __name__ == "__main__":
    unittest.main()

"""Production experience validation is evidence- and human-gated."""
from __future__ import annotations

import importlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


class ExperienceValidationPolicyContractTest(unittest.TestCase):
    def setUp(self):
        self.experience = importlib.import_module("_experience")
        self.extract = importlib.import_module("_experience_extract")
        self.source_ref = importlib.import_module("_source_ref")
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.experience.ensure_schema(self.conn)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        self.source = self.vault / "01-raw" / "transcripts" / "one.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("bounded retry passed", encoding="utf-8")

    def _source(self):
        return self.source_ref.make_source_ref(
            self.vault, "01-raw/transcripts/one.md", start=0,
            end=len("bounded retry passed"), chunk_id="chunk-0",
            captured_at="2026-09-04T00:00:00Z")

    def _candidate(self, *, source_ref=None):
        self.experience.append_event(
            self.conn, event_id="evt-1", session_id="s1", task_id="t1",
            event_type="attempt", observed_at="2026-09-04T00:00:00Z",
            payload={"situation": "s", "approach": "a", "lesson": "l"},
            source_refs=[source_ref or self._source()])
        self._record_outcome()
        return self.extract.derive_experience_values(
            self.conn, "s1", "t1", "exp-1")

    def _review(self, candidate, *, decision="accepted", review_id="review-1"):
        return self.experience.record_review(
            self.conn, review_id=review_id, experience_id="exp-1",
            decision=decision, actor="owner",
            reviewed_at="2026-09-04T00:01:00Z",
            reason="owner checked exact source and outcome",
            content_hash=self.experience.experience_content_hash(candidate),
            schema_version="1", idempotency_key=review_id)

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

    def test_exact_evidence_and_matching_accepted_review_validate_projection(self):
        candidate = self._candidate()
        self._review(candidate)

        record = self.experience.validate_projection_record(
            self.conn, candidate, vault=self.vault)

        self.assertEqual(record["status"], "validated")
        self.assertEqual(record["evidence_state"], "verified")
        self.assertEqual(record["review_state"], "accepted")

    def test_stale_source_and_rejected_review_cannot_enter_projection(self):
        candidate = self._candidate()
        self._review(candidate, decision="rejected")
        self.source.write_text("source changed after review", encoding="utf-8")

        record = self.experience.validate_projection_record(
            self.conn, candidate, vault=self.vault)

        self.assertEqual(record["status"], "candidate")
        self.assertEqual(record["evidence_state"], "stale")
        self.assertEqual(record["review_state"], "rejected")

    def test_later_rejection_revokes_an_accepted_review_for_same_content(self):
        candidate = self._candidate()
        self._review(candidate)
        self.experience.record_review(
            self.conn, review_id="review-2", experience_id="exp-1",
            decision="rejected", actor="owner",
            reviewed_at="2026-09-03T00:00:00Z",
            reason="second inspection found an unsupported causal claim",
            content_hash=self.experience.experience_content_hash(candidate))

        record = self.experience.validate_projection_record(
            self.conn, candidate, vault=self.vault)

        self.assertEqual(record["status"], "candidate")
        self.assertEqual(record["review_state"], "rejected")

    def test_incomplete_review_row_fails_closed(self):
        candidate = self._candidate()
        self.conn.execute(
            "INSERT INTO experience_reviews(review_id, experience_id, decision, actor, "
            "reviewed_at, reason, content_hash, schema_version, idempotency_key) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("legacy-review", "exp-1", "accepted", "owner",
             "2026-09-04T00:01:00Z", "",
             self.experience.experience_content_hash(candidate), "1", "legacy-review"))
        self.conn.commit()

        record = self.experience.validate_projection_record(
            self.conn, candidate, vault=self.vault)

        self.assertEqual(record["status"], "candidate")
        self.assertEqual(record["review_state"], "unreviewed")

    def test_missing_version_stamp_is_not_verified(self):
        candidate = self._candidate()
        candidate["extractor_version"] = ""
        candidate["content_hash"] = self.experience.experience_content_hash(candidate)
        self._review(candidate)

        record = self.experience.validate_projection_record(
            self.conn, candidate, vault=self.vault)

        self.assertEqual(record["status"], "candidate")
        self.assertEqual(record["evidence_state"], "unverified")

    def test_material_reextraction_invalidates_old_review(self):
        original = self._candidate()
        self._review(original)
        self.experience.append_event(
            self.conn, event_id="evt-2", session_id="s1", task_id="t1",
            event_type="decision", observed_at="2026-09-04T00:02:00Z",
            payload={"lesson": "changed lesson"}, source_refs=[self._source()])

        changed = self.extract.derive_experience_values(
            self.conn, "s1", "t1", "exp-1")
        record = self.experience.validate_projection_record(
            self.conn, changed, vault=self.vault)

        self.assertNotEqual(original["content_hash"], changed["content_hash"])
        self.assertEqual(record["status"], "candidate")
        self.assertEqual(record["evidence_state"], "verified")
        self.assertEqual(record["review_state"], "unreviewed")

    def test_cross_task_outcome_and_forbidden_lifecycle_are_not_validated(self):
        candidate = self._candidate()
        self.experience.record_outcome(
            self.conn, outcome_id="out-other", session_id="other", task_id="other",
            state="success", evidence=["pass"], attribution_strength="direct")
        candidate["outcome_refs"] = ["out-other"]
        candidate["content_hash"] = self.experience.experience_content_hash(candidate)
        self._review(candidate)

        mismatched = self.experience.validate_projection_record(
            self.conn, candidate, vault=self.vault)
        retracted = self.experience.validate_projection_record(
            self.conn, {**candidate, "status": "retracted"}, vault=self.vault)

        self.assertEqual(mismatched["evidence_state"], "contradictory")
        self.assertEqual(mismatched["status"], "candidate")
        self.assertEqual(retracted["status"], "retracted")

    def test_review_metadata_and_idempotency_are_enforced(self):
        candidate = self._candidate()
        content_hash = self.experience.experience_content_hash(candidate)
        for field in ("actor", "reviewed_at", "reason", "schema_version"):
            kwargs = {
                "review_id": f"bad-{field}", "experience_id": "exp-1",
                "decision": "accepted", "actor": "owner",
                "reviewed_at": "2026-09-04T00:01:00Z", "reason": "checked",
                "content_hash": content_hash, "schema_version": "1",
            }
            kwargs[field] = ""
            with self.assertRaises(ValueError, msg=field):
                self.experience.record_review(self.conn, **kwargs)
        self.assertTrue(self._review(candidate))
        self.assertFalse(self._review(candidate))
        with self.assertRaises(ValueError):
            self.experience.record_review(
                self.conn, review_id="review-2", experience_id="exp-1",
                decision="rejected", actor="owner",
                reviewed_at="2026-09-04T00:03:00Z", reason="changed decision",
                content_hash=content_hash, schema_version="1",
                idempotency_key="review-1")

    def test_transition_revalidates_exact_evidence_instead_of_trusting_cached_state(self):
        candidate = self._candidate()
        self.experience.save_experience(self.conn, **candidate)
        self._review(candidate)
        self.conn.execute(
            "UPDATE experiences SET evidence_state='verified' WHERE experience_id='exp-1'")
        self.conn.commit()
        self.source.write_text("stale now", encoding="utf-8")

        with self.assertRaises(ValueError):
            self.experience.transition(
                self.conn, "exp-1", "validated", vault=self.vault)


if __name__ == "__main__":
    unittest.main()

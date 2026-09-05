"""Focused contracts for the production experience human-review CLI."""
from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tests._loader import load_script  # noqa: E402
import _experience  # noqa: E402


class ExperienceReviewCliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name) / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self.ledger = _experience.ledger_path(self.vault)
        conn = _experience.connect(self.ledger)
        _experience.ensure_ledger_schema(conn)
        _experience.append_event(
            conn, event_id="event-1", session_id="session-1", task_id="task-1",
            event_type="observation", observed_at="2026-09-05T10:00:00Z",
            payload={
                "situation": "The deploy failed after a stale cache read.",
                "goal": "Restore the deploy.",
                "approach": "Invalidate the cache before retrying.",
                "action": "Removed only the stale cache entry.",
                "observed_result": "The retry passed.",
                "lesson": "Check cache freshness before retrying a deploy.",
                "applicability": "Deploy failures after cache changes.",
            },
            source_refs=[{"source_ref_id": "source-ref-1"}],
            schema_version="1")
        _experience.record_outcome(
            conn, outcome_id="outcome-1", session_id="session-1",
            task_id="task-1", state="success",
            evidence=[{"source_ref_id": "source-ref-1"}],
            attribution_strength="strong",
            observed_at="2026-09-05T10:01:00Z")
        conn.close()
        self.cli = load_script("kb-experience-review.py")
        self.experience_id = self.cli.experience_id_for("session-1", "task-1")
        self.env = patch.dict(os.environ, {"KENNISBANK_VAULT": str(self.vault)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = self.cli.main(argv)
        output = stdout.getvalue() if result == 0 else stderr.getvalue()
        return result, json.loads(output)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _content_hash(self) -> str:
        result, payload = self._run(["inspect", self.experience_id])
        self.assertEqual(result, 0)
        return payload["candidate"]["content_hash"]

    def test_list_and_inspect_are_read_only_and_show_candidate_hash(self):
        before = self._sha256(self.ledger)

        list_result, listing = self._run(["list", "--limit", "10"])
        inspect_result, inspected = self._run(["inspect", self.experience_id])

        self.assertEqual((list_result, inspect_result), (0, 0))
        self.assertFalse(listing["mutated"])
        self.assertFalse(inspected["mutated"])
        self.assertEqual(listing["ledger_path"], str(self.ledger))
        self.assertEqual(listing["candidates"][0]["status"], "candidate")
        self.assertEqual(listing["candidates"][0]["review_state"], "unreviewed")
        self.assertRegex(inspected["candidate"]["content_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(self._sha256(self.ledger), before)

    def test_review_appends_complete_audit_row_without_touching_projection(self):
        content_hash = self._content_hash()
        projection = _experience.projection_path(self.vault)
        projection.write_bytes(b"projection sentinel")

        result, payload = self._run([
            "review", self.experience_id, "--decision", "accepted",
            "--actor", "owner@example.test", "--reason", "Evidence checked.",
            "--content-hash", content_hash, "--idempotency-key", "review-command-1",
        ])

        self.assertEqual(result, 0)
        self.assertTrue(payload["created"])
        self.assertFalse(payload["projection_written"])
        review = payload["review"]
        self.assertEqual(review["decision"], "accepted")
        self.assertEqual(review["schema_version"], "1")
        self.assertEqual(review["content_hash"], content_hash)
        self.assertTrue(review["actor"] and review["reason"] and review["reviewed_at"])
        self.assertIsNotNone(datetime.fromisoformat(review["reviewed_at"]))
        self.assertEqual(projection.read_bytes(), b"projection sentinel")
        conn = sqlite3.connect(self.ledger)
        try:
            stored = conn.execute(
                "SELECT decision, actor, reviewed_at, reason, content_hash, "
                "schema_version, idempotency_key FROM experience_reviews").fetchone()
        finally:
            conn.close()
        self.assertEqual(stored, (
            "accepted", "owner@example.test", review["reviewed_at"],
            "Evidence checked.", content_hash, "1", "review-command-1"))

    def test_same_idempotency_key_is_a_noop_with_original_timestamp(self):
        content_hash = self._content_hash()
        kwargs = dict(
            experience_id=self.experience_id, decision="rejected", actor="owner",
            reason="The claimed lesson is too broad.", content_hash=content_hash,
            idempotency_key="stable-rejection")

        first = self.cli.append_review(
            self.ledger, **kwargs, now_fn=lambda: "2026-09-05T12:00:00+00:00")
        second = self.cli.append_review(
            self.ledger, **kwargs, now_fn=lambda: "2026-09-05T13:00:00+00:00")

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(second["review"]["reviewed_at"],
                         "2026-09-05T12:00:00+00:00")
        conn = sqlite3.connect(self.ledger)
        try:
            count = conn.execute("SELECT count(*) FROM experience_reviews").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 1)

    def test_idempotency_key_cannot_be_reused_for_another_decision(self):
        content_hash = self._content_hash()
        common = dict(
            experience_id=self.experience_id, actor="owner", reason="Reviewed.",
            content_hash=content_hash, idempotency_key="one-command")
        self.cli.append_review(self.ledger, decision="accepted", **common)

        with self.assertRaisesRegex(ValueError, "different review"):
            self.cli.append_review(self.ledger, decision="rejected", **common)

        conn = sqlite3.connect(self.ledger)
        try:
            rows = conn.execute(
                "SELECT decision FROM experience_reviews").fetchall()
        finally:
            conn.close()
        self.assertEqual(rows, [("accepted",)])

    def test_review_rejects_blank_audit_fields_without_writing(self):
        content_hash = self._content_hash()
        for field in ("actor", "reason", "idempotency_key"):
            values = {
                "experience_id": self.experience_id, "decision": "accepted",
                "actor": "owner", "reason": "Reviewed.",
                "content_hash": content_hash, "idempotency_key": "key",
            }
            values[field] = "  "
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "must be non-empty"):
                self.cli.append_review(self.ledger, **values)
        conn = sqlite3.connect(self.ledger)
        try:
            count = conn.execute("SELECT count(*) FROM experience_reviews").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)

    def test_review_rejects_stale_content_hash(self):
        stale_hash = "sha256:" + ("0" * 64)

        result, payload = self._run([
            "review", self.experience_id, "--decision", "accepted",
            "--actor", "owner", "--reason", "Reviewed.",
            "--content-hash", stale_hash, "--idempotency-key", "stale-review",
        ])

        self.assertEqual(result, 2)
        self.assertIn("content hash mismatch", payload["reason"])
        conn = sqlite3.connect(self.ledger)
        try:
            count = conn.execute("SELECT count(*) FROM experience_reviews").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()

"""Contracts for production, source-grounded experience event capture."""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT = SCRIPTS / "kb-experience-capture.py"


def load_script():
    spec = importlib.util.spec_from_file_location("kb_experience_capture", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_named(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExperienceCaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        self.source = self.vault / "01-raw" / "transcripts" / "session.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("first attempt failed; bounded retry passed", encoding="utf-8")
        (self.vault / "kennisbank-settings.json").write_text(
            json.dumps({"experience_capture": True}) + "\n", encoding="utf-8")
        self.mod = load_script()

    def event(self, **changes):
        payload = {
            "idempotency_key": "natural-case-1",
            "session_id": "session-1",
            "task_id": "task-1",
            "event_type": "fix",
            "observed_at": "2026-09-07T12:00:00+00:00",
            "payload": {
                "situation": "an unbounded retry hung",
                "goal": "finish without a stuck child",
                "approach": "bound the retry",
                "action": "added a timeout",
                "observed_result": "the bounded retry passed",
                "lesson": "bound retries at process boundaries",
                "applicability": "subprocess recovery",
                "attempt_state": "failure",
                "resolution_state": "fix_validated",
                "attribution_limits": "one observed task; no universal causality",
            },
            "source_ranges": [{
                "source_path": "01-raw/transcripts/session.md",
                "start": 0,
                "end": len("first attempt failed; bounded retry passed"),
                "chunk_id": "session-1",
            }],
        }
        payload.update(changes)
        return payload

    def test_capture_creates_only_an_idempotent_grounded_ledger_event(self):
        first = self.mod.capture_event(self.event(), vault=self.vault)
        second = self.mod.capture_event(self.event(), vault=self.vault)
        self.assertEqual(first["status"], "ok")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertRegex(first["event_id"], r"^experience-event-[0-9a-f]{24}$")
        self.assertRegex(first["experience_id"], r"^experience-[0-9a-f]{20}$")
        self.assertEqual(first["source_ref_count"], 1)
        self.assertNotIn("payload", first)
        self.assertNotIn("source_ranges", first)

        ledger = self.vault / ".claude" / "kb-experience-ledger.db"
        projection = self.vault / ".claude" / "kb-experience-index.db"
        self.assertTrue(ledger.is_file())
        self.assertFalse(projection.exists())
        conn = sqlite3.connect(ledger)
        try:
            row = conn.execute(
                "SELECT payload_json, source_refs_json FROM experience_events"
            ).fetchone()
            stored_payload = json.loads(row[0])
            source_refs = json.loads(row[1])
            self.assertEqual(stored_payload["lesson"],
                             "bound retries at process boundaries")
            self.assertEqual(stored_payload["attempt_state"], "failure")
            self.assertEqual(stored_payload["resolution_state"], "fix_validated")
            self.assertEqual(source_refs[0]["source_path"],
                             "01-raw/transcripts/session.md")
            self.assertRegex(source_refs[0]["source_ref_id"], r"^sr_[0-9a-f]{64}$")
        finally:
            conn.close()

    def test_disabled_capture_does_not_create_a_store(self):
        (self.vault / "kennisbank-settings.json").unlink()
        result = self.mod.capture_event(self.event(), vault=self.vault)
        self.assertEqual(result, {"status": "disabled", "created": False})
        self.assertFalse((self.vault / ".claude" / "kb-experience-ledger.db").exists())

    def test_changed_reuse_of_an_idempotency_key_is_rejected(self):
        self.mod.capture_event(self.event(), vault=self.vault)
        changed = self.event()
        changed["payload"] = {**changed["payload"], "lesson": "a different lesson"}
        with self.assertRaisesRegex(ValueError, "different payload"):
            self.mod.capture_event(changed, vault=self.vault)

    def test_capture_rejects_ungrounded_or_content_leaking_shapes_before_write(self):
        cases = []
        no_sources = self.event(source_ranges=[])
        cases.append(no_sources)
        raw_prompt = self.event()
        raw_prompt["payload"] = {**raw_prompt["payload"], "raw_prompt": "private"}
        cases.append(raw_prompt)
        outside = self.event(source_ranges=[{
            "source_path": "../outside.md", "start": 0, "end": 1,
        }])
        cases.append(outside)
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    self.mod.capture_event(case, vault=self.vault)
        self.assertFalse((self.vault / ".claude" / "kb-experience-ledger.db").exists())

    def test_cli_reads_private_content_from_stdin_and_emits_aggregate_json(self):
        env = dict(os.environ)
        env["KENNISBANK_VAULT"] = str(self.vault)
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], input=json.dumps(self.event()),
            text=True, capture_output=True, env=env, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["status"], "ok")
        self.assertEqual(output["source_ref_count"], 1)
        self.assertNotIn("bounded retry", result.stdout)
        self.assertNotIn(str(self.vault), result.stdout)

    def test_capture_outcome_review_and_rebuild_form_one_closed_gate(self):
        captured = self.mod.capture_event(self.event(), vault=self.vault)
        outcome = load_named("capture_outcome", "kb-outcome.py")
        outcome_transcript = self.vault / "outcome.jsonl"
        outcome_transcript.write_text('{"text":"pytest: 3 passed"}\n',
                                      encoding="utf-8")
        result = outcome.record_session_outcome({
            "session_id": "session-1", "task_id": "task-1",
            "transcript_path": str(outcome_transcript),
            "timestamp": "2026-09-07T12:01:00+00:00",
        }, vault=self.vault)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["state"], "success")

        ledger = self.vault / ".claude" / "kb-experience-ledger.db"
        review = load_named("capture_review", "kb-experience-review.py")
        inspected = review.inspect_candidate(ledger, captured["experience_id"])
        candidate = inspected["candidate"]
        self.assertEqual(candidate["attempt_state"], "failure")
        self.assertEqual(candidate["resolution_state"], "fix_validated")
        self.assertEqual(candidate["outcome_state"], "success")
        review.append_review(
            ledger, experience_id=captured["experience_id"],
            decision="accepted", actor="test-owner",
            reason="exact source and observed outcome checked",
            content_hash=candidate["content_hash"],
            idempotency_key="natural-case-1-review",
            now_fn=lambda: "2026-09-07T12:02:00+00:00")

        builder = load_named("capture_builder", "build-experience-index.py")
        projection = self.vault / ".claude" / "kb-experience-index.db"
        report = builder.rebuild_experience_projection(ledger, projection)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["experiences"], 1)
        self.assertEqual(report["skipped_candidates"], [])
        conn = sqlite3.connect(projection)
        try:
            row = conn.execute(
                "SELECT status, evidence_state, review_state, attempt_state, "
                "resolution_state, outcome_state FROM experiences"
            ).fetchone()
            self.assertEqual(row, (
                "validated", "verified", "accepted", "failure",
                "fix_validated", "success"))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()

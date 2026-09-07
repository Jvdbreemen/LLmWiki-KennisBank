"""Session-end outcome recorder contracts."""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load():
    spec = importlib.util.spec_from_file_location("kb_outcome", SCRIPTS / "kb-outcome.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OutcomeRecorderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self.transcript = self.vault / "transcript.jsonl"
        self.transcript.write_text(
            json.dumps({"text": "pytest: 3 passed; commit abc1234"}) + "\n",
            encoding="utf-8")
        (self.vault / "kennisbank-settings.json").write_text(
            json.dumps({"experience_capture": True}) + "\n", encoding="utf-8")
        self.saved_vault = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.addCleanup(self._restore_vault)
        self.mod = load()

    def _restore_vault(self):
        if self.saved_vault is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self.saved_vault

    def test_local_signals_record_success_and_are_idempotent(self):
        result = self.mod.record_session_outcome(
            {"session_id": "s1", "task_id": "t1", "transcript_path": str(self.transcript)},
            vault=self.vault)
        self.assertEqual(result["state"], "success")
        again = self.mod.record_session_outcome(
            {"session_id": "s1", "task_id": "t1", "transcript_path": str(self.transcript)},
            vault=self.vault)
        self.assertFalse(again["created"])
        ledger = self.vault / ".claude" / "kb-experience-ledger.db"
        self.assertTrue(ledger.is_file())
        self.assertFalse((self.vault / ".claude" / "kb-experience.db").exists())
        conn = sqlite3.connect(ledger)
        try:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM experience_events").fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM experience_outcomes").fetchone()[0], 1)
        finally:
            conn.close()

    def test_capture_default_off_does_not_create_any_experience_store(self):
        (self.vault / "kennisbank-settings.json").unlink()
        result = self.mod.record_session_outcome(
            {"session_id": "off", "task_id": "t", "transcript_path": str(self.transcript)},
            vault=self.vault)
        self.assertEqual(result["status"], "disabled")
        self.assertFalse(result["created"])
        self.assertFalse((self.vault / ".claude" / "kb-experience-ledger.db").exists())
        self.assertFalse((self.vault / ".claude" / "kb-experience.db").exists())

    def test_explicit_vault_uses_its_own_capture_flag(self):
        other = Path(self.tmp.name) / "other-vault"
        other.mkdir()
        os.environ["KENNISBANK_VAULT"] = str(other)
        result = self.mod.record_session_outcome(
            {"session_id": "explicit", "task_id": "t",
             "transcript_path": str(self.transcript)}, vault=self.vault)
        self.assertEqual(result["status"], "ok")
        self.assertTrue((self.vault / ".claude" / "kb-experience-ledger.db").is_file())
        self.assertFalse((other / ".claude" / "kb-experience-ledger.db").exists())

    def test_missing_transcript_is_unknown_and_fail_open(self):
        result = self.mod.record_session_outcome(
            {"session_id": "s2", "task_id": "t2", "transcript_path": "missing.jsonl"},
            vault=self.vault)
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["evidence"], [])


if __name__ == "__main__":
    unittest.main()

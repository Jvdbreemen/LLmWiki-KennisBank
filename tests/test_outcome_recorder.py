"""Session-end outcome recorder contracts."""
from __future__ import annotations

import importlib.util
import json
import os
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
        self.mod = load()

    def test_local_signals_record_success_and_are_idempotent(self):
        result = self.mod.record_session_outcome(
            {"session_id": "s1", "task_id": "t1", "transcript_path": str(self.transcript)},
            vault=self.vault)
        self.assertEqual(result["state"], "success")
        again = self.mod.record_session_outcome(
            {"session_id": "s1", "task_id": "t1", "transcript_path": str(self.transcript)},
            vault=self.vault)
        self.assertFalse(again["created"])

    def test_missing_transcript_is_unknown_and_fail_open(self):
        result = self.mod.record_session_outcome(
            {"session_id": "s2", "task_id": "t2", "transcript_path": "missing.jsonl"},
            vault=self.vault)
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["evidence"], [])


if __name__ == "__main__":
    unittest.main()

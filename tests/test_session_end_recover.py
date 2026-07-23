import importlib.util
import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location(
        "kb_session_end_recover", SCRIPTS / "kb-session-end-recover.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecoverTest(unittest.TestCase):
    def setUp(self):
        self.mod = _load()

    def _vault(self, tmp):
        claude = Path(tmp) / ".claude"
        (claude / "scripts").mkdir(parents=True)
        return Path(tmp)

    def _state(self, vault):
        p = vault / ".claude" / self.mod.STATE_NAME
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}

    def test_no_state_is_noop(self):
        with TemporaryDirectory() as tmp:
            vault = self._vault(tmp)
            self.assertIsNone(self.mod.recover(vault))

    def test_completed_state_is_noop(self):
        with TemporaryDirectory() as tmp:
            vault = self._vault(tmp)
            (vault / ".claude" / self.mod.STATE_NAME).write_text(
                json.dumps({"status": "completed", "started_at": 0}), encoding="utf-8"
            )
            self.assertIsNone(self.mod.recover(vault))

    def test_fresh_running_state_is_left_alone(self):
        # Younger than MIN_AGE_SECONDS: may still be in flight, do not race it.
        with TemporaryDirectory() as tmp:
            vault = self._vault(tmp)
            (vault / ".claude" / self.mod.STATE_NAME).write_text(
                json.dumps({"status": "running", "started_at": time.time()}),
                encoding="utf-8",
            )
            self.assertIsNone(self.mod.recover(vault))
            self.assertEqual(self._state(vault)["status"], "running")

    def test_stale_running_state_triggers_capture_and_closes(self):
        with TemporaryDirectory() as tmp:
            vault = self._vault(tmp)
            # A capture stub that just succeeds; recover invokes it via subprocess.
            (vault / ".claude" / "scripts" / "archive-transcript.py").write_text(
                "import sys; sys.exit(0)\n", encoding="utf-8"
            )
            (vault / ".claude" / self.mod.STATE_NAME).write_text(
                json.dumps(
                    {
                        "status": "running",
                        "started_at": time.time() - self.mod.MIN_AGE_SECONDS - 60,
                        "client": "claude",
                        "transcript_path": "/tmp/whatever.jsonl",
                    }
                ),
                encoding="utf-8",
            )
            note = self.mod.recover(vault)
            self.assertIsNotNone(note)
            # State is closed so it is recovered at most once.
            self.assertEqual(self._state(vault)["status"], "recovered")
            self.assertIsNone(self.mod.recover(vault))


if __name__ == "__main__":
    unittest.main()

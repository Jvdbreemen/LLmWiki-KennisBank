"""Checkpoint-primitief (TASK-79): stub bij PreCompact, melding vóór de gate.

De drie manieren waarop dit stil kon breken:
1. De PreCompact-stub schrijft terwijl de toggle uit staat (opt-in geschonden),
   of schrijft niet terwijl hij aan staat.
2. De melding hangt achter de 300s-freshness-gate en valt precies bij
   source=compact weg.
3. --register accepteert een pad buiten 01-raw/checkpoints/.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tests._loader import load_script  # noqa: E402


class CheckpointBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        (self.vault / ".claude").mkdir()
        (self.vault / "01-raw" / "checkpoints").mkdir(parents=True)
        self._saved_env = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.mod = load_script("kb-checkpoint.py")

    def tearDown(self):
        if self._saved_env is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved_env
        self._tmp.cleanup()

    def _set_toggle(self, value: bool) -> None:
        (self.vault / "kennisbank-settings.json").write_text(
            json.dumps({"checkpoints": value}), encoding="utf-8")


class PreCompactStubTest(CheckpointBase):
    PAYLOAD = {"trigger": "auto", "session_id": "s1",
               "transcript_path": "/tmp/t.jsonl", "cwd": "/repo"}

    def test_toggle_off_writes_nothing(self):
        self._set_toggle(False)
        self.assertFalse(self.mod.record_precompact(self.vault, self.PAYLOAD))
        self.assertEqual(self.mod.pending(self.vault), [])

    def test_toggle_missing_defaults_to_off(self):
        self.assertFalse(self.mod.record_precompact(self.vault, self.PAYLOAD))
        self.assertEqual(self.mod.pending(self.vault), [])

    def test_toggle_on_writes_stub(self):
        self._set_toggle(True)
        self.assertTrue(self.mod.record_precompact(self.vault, self.PAYLOAD))
        items = self.mod.pending(self.vault)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["type"], "auto")
        self.assertEqual(items[0]["transcript_path"], "/tmp/t.jsonl")

    def test_pending_is_bounded(self):
        self._set_toggle(True)
        for _ in range(self.mod.MAX_PENDING + 5):
            self.mod.record_precompact(self.vault, self.PAYLOAD)
        self.assertEqual(len(self.mod.pending(self.vault)), self.mod.MAX_PENDING)


class RegisterAndDoneTest(CheckpointBase):
    def test_register_inside_checkpoint_dir(self):
        md = self.vault / "01-raw" / "checkpoints" / "checkpoint-x.md"
        md.write_text("## Actieve taak\n", encoding="utf-8")
        self.assertIsNone(self.mod.register_manual(self.vault, str(md)))
        items = self.mod.pending(self.vault)
        self.assertEqual(items[0]["type"], "manual")

    def test_register_outside_checkpoint_dir_refused(self):
        md = self.vault / "elders.md"
        md.write_text("x", encoding="utf-8")
        err = self.mod.register_manual(self.vault, str(md))
        self.assertIsNotNone(err)
        self.assertEqual(self.mod.pending(self.vault), [])

    def test_register_works_regardless_of_toggle(self):
        # Handmatig registreren mag NIET achter de toggle zitten.
        self._set_toggle(False)
        md = self.vault / "01-raw" / "checkpoints" / "c.md"
        md.write_text("x", encoding="utf-8")
        self.assertIsNone(self.mod.register_manual(self.vault, str(md)))
        self.assertEqual(len(self.mod.pending(self.vault)), 1)

    def test_done_clears_pending_idempotent(self):
        md = self.vault / "01-raw" / "checkpoints" / "c.md"
        md.write_text("x", encoding="utf-8")
        self.mod.register_manual(self.vault, str(md))
        self.assertEqual(self.mod.mark_done(self.vault), 1)
        self.assertEqual(self.mod.mark_done(self.vault), 0)
        self.assertEqual(self.mod.pending(self.vault), [])


class NotifyTest(CheckpointBase):
    def test_silent_when_nothing_pending(self):
        self.assertEqual(self.mod.notify_text(self.vault, "startup"), "")

    def test_compact_source_gets_urgent_lead(self):
        md = self.vault / "01-raw" / "checkpoints" / "c.md"
        md.write_text("x", encoding="utf-8")
        self.mod.register_manual(self.vault, str(md))
        text = self.mod.notify_text(self.vault, "compact")
        self.assertIn("compaction", text.lower())
        self.assertIn("/checkpoint load", text)

    def test_startup_source_reports_count(self):
        md = self.vault / "01-raw" / "checkpoints" / "c.md"
        md.write_text("x", encoding="utf-8")
        self.mod.register_manual(self.vault, str(md))
        text = self.mod.notify_text(self.vault, "startup")
        self.assertIn("1 open checkpoint", text)


class CoordinatorWiringTest(unittest.TestCase):
    """De melding moet vóór de freshness-gate zitten en source moet geparsed worden."""

    def test_notify_runs_even_when_state_is_fresh(self):
        m = load_script("kb-session-start.py")
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            runtime = vault / ".claude"
            (runtime / "scripts").mkdir(parents=True)
            (runtime / m.STATE_NAME).write_text(
                json.dumps({"completed_at": 10_000.0,
                            "clients": {"claude": 10_000.0}}), encoding="utf-8")

            seen = []

            def runner(job, scripts, payload):
                seen.append((job.script, job.args))
                return m.Result(script=job.script)

            payload = json.dumps({"source": "compact"}).encode()
            m.coordinate("claude", vault, payload, runner=runner, now=10_060.0)
            self.assertEqual(
                seen, [("kb-checkpoint.py", ("--notify", "--source", "compact"))],
                "verse state mag alles overslaan BEHALVE de checkpoint-melding")

    def test_manifest_has_precompact_hook_with_timeout(self):
        import _hooks_manifest as man
        events = {(e, s) for e, s, _ in man.hooks()}
        self.assertIn(("PreCompact", "kb-checkpoint.py"), events)
        self.assertEqual(man.timeout("kb-checkpoint.py"), 15)


if __name__ == "__main__":
    unittest.main()

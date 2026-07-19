"""Tests voor scripts/memory-notify.py - SessionStart-health-surface."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("memory_notify", str(SCRIPTS_DIR / "memory-notify.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class MemoryNotifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-notify-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = _load()

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _hb(self, obj):
        (self.vault / ".claude" / "memory-sweep-status.json").write_text(
            json.dumps(obj), encoding="utf-8")

    def test_clean_no_notice(self):
        self._hb({"last_run": "2026-06-27T10:00:00+00:00", "errors": 0,
                  "model_unreachable": False})
        self.assertEqual(self.m.notice(), "")

    def test_model_unreachable_notice(self):
        self._hb({"model_unreachable": True, "errors": 0})
        self.assertIn("onbereikbaar", self.m.notice().lower())

    def test_errors_notice(self):
        self._hb({"errors": 3, "model_unreachable": False})
        self.assertIn("3", self.m.notice())

    def test_rot_notice(self):
        from datetime import date, timedelta
        old = (date.today() - timedelta(days=3)).isoformat()
        (self.vault / "09-memory" / "a.md").write_text(
            f"---\ntype: memory\nstatus: unverified\ncreated: {old}\n---\n\nx", encoding="utf-8")
        self._hb({"errors": 0, "model_unreachable": False})
        self.assertIn("unverified", self.m.notice().lower())

    def _pending_transcript(self, name="t1.jsonl"):
        """Create a pending transcript file in the vault."""
        tdir = self.vault / "01-raw" / "transcripts"
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / name).write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "test"}}),
            encoding="utf-8")

    def test_stale_absent_heartbeat_with_pending(self):
        """Absent heartbeat + pending transcript → stale notice emitted."""
        self._pending_transcript()
        # No heartbeat file (hb_path does not exist)
        n = self.m.notice()
        self.assertIn("gestald", n,
                      f"Expected stale notice when no heartbeat + pending, got: {n!r}")

    def test_stale_old_last_run_with_pending(self):
        """Heartbeat with last_run > 26 hours ago + pending → stale notice."""
        self._pending_transcript()
        old_dt = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat()
        self._hb({"last_run": old_dt, "errors": 0, "model_unreachable": False})
        n = self.m.notice()
        self.assertIn("gestald", n,
                      f"Expected stale notice for very old last_run, got: {n!r}")

    def test_fresh_heartbeat_with_pending_no_stale_notice(self):
        """Fresh last_run (just now) + pending → NO stale notice."""
        self._pending_transcript()
        now = datetime.now(timezone.utc).isoformat()
        self._hb({"last_run": now, "errors": 0, "model_unreachable": False})
        n = self.m.notice()
        self.assertNotIn("gestald", n,
                         f"Expected no stale notice for fresh heartbeat, got: {n!r}")

    def test_main_failing_heartbeat_json_output(self):
        """main() with absent heartbeat + pending → stdout JSON with correct hook structure."""
        self._pending_transcript()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.m.main()
        out = buf.getvalue()
        self.assertTrue(out, "main() should produce JSON output for stale/failing state")
        data = json.loads(out)
        self.assertTrue(data["suppressOutput"])
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("gestald", data["hookSpecificOutput"]["additionalContext"])

    def test_main_clean_no_output(self):
        """main() with clean state (fresh heartbeat, no pending) → no stdout."""
        self._hb({"last_run": datetime.now(timezone.utc).isoformat(),
                  "errors": 0, "model_unreachable": False})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.m.main()
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()

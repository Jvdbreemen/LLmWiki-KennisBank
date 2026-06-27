"""Tests voor scripts/memory-notify.py - SessionStart-health-surface."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()

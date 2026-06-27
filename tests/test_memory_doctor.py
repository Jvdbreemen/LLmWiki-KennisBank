"""Tests voor scripts/memory-doctor.py - no-cloud + quarantaine-rot checks."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import importlib.util


def _load():
    spec = importlib.util.spec_from_file_location("memory_doctor", str(SCRIPTS_DIR / "memory-doctor.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class MemoryDoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-doc-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = {k: os.environ.get(k) for k in
                       ("KENNISBANK_VAULT", "KB_LLM_PROVIDERS", "KB_LLM_ENDPOINT")}
        for k in ("KB_LLM_PROVIDERS", "KB_LLM_ENDPOINT"):
            os.environ.pop(k, None)
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = _load()

    def tearDown(self):
        import shutil
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, name, status, created):
        (self.vault / "09-memory" / name).write_text(
            f"---\ntitle: T\ntype: memory\nstatus: {status}\ncreated: {created}\n---\n\nbody",
            encoding="utf-8")

    def test_nocloud_clean_default(self):
        self.assertEqual(self.m.cloud_warnings(), [])  # default ollama localhost

    def test_nocloud_flags_cloud_provider(self):
        os.environ["KB_LLM_PROVIDERS"] = "ollama, openrouter"
        w = self.m.cloud_warnings()
        self.assertTrue(any("openrouter" in x for x in w))

    def test_nocloud_flags_remote_ollama(self):
        os.environ["KB_LLM_ENDPOINT"] = "http://192.168.1.50:11434"
        w = self.m.cloud_warnings()
        self.assertTrue(any("endpoint" in x.lower() for x in w))

    def test_rot_counts_old_unverified(self):
        old = (date.today() - timedelta(days=3)).isoformat()
        new = date.today().isoformat()
        self._mem("a.md", "unverified", old)   # rot
        self._mem("b.md", "unverified", new)   # vers, geen rot
        self._mem("c.md", "current", old)      # current, geen rot
        self.assertEqual(self.m.rot_count(hours=48), 1)


if __name__ == "__main__":
    unittest.main()

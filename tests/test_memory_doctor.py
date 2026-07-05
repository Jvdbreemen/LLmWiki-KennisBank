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

    def _status(self, name):
        import re
        txt = (self.vault / "09-memory" / name).read_text(encoding="utf-8")
        mm = re.search(r"^status:\s*(\w+)", txt, re.MULTILINE)
        return mm.group(1) if mm else None

    def test_rejudge_promotes_on_current_verdict(self):
        d = date.today().isoformat()
        self._mem("a.md", "unverified", d)
        self._mem("b.md", "unverified", d)
        r = self.m.rejudge_pass(judge_fn=lambda body: {"verdict": "current"})
        self.assertEqual(r["promoted"], 2)
        self.assertEqual(self._status("a.md"), "current")

    def test_rejudge_keeps_on_unverified_verdict(self):
        d = date.today().isoformat()
        self._mem("a.md", "unverified", d)
        r = self.m.rejudge_pass(judge_fn=lambda body: {"verdict": "unverified"})
        self.assertEqual(r, {"promoted": 0, "kept": 1, "failed": 0})
        self.assertEqual(self._status("a.md"), "unverified")

    def test_rejudge_dry_run_writes_nothing(self):
        d = date.today().isoformat()
        self._mem("a.md", "unverified", d)
        r = self.m.rejudge_pass(judge_fn=lambda body: {"verdict": "current"}, dry_run=True)
        self.assertEqual(r["promoted"], 1)
        self.assertEqual(self._status("a.md"), "unverified")  # niet geschreven

    def test_rejudge_hours_filter_only_old(self):
        old = (date.today() - timedelta(days=3)).isoformat()
        new = date.today().isoformat()
        self._mem("old.md", "unverified", old)
        self._mem("new.md", "unverified", new)
        r = self.m.rejudge_pass(judge_fn=lambda body: {"verdict": "current"}, hours=48)
        self.assertEqual(r["promoted"], 1)          # alleen de oude
        self.assertEqual(self._status("new.md"), "unverified")

    def test_rejudge_failsafe_on_judge_exception(self):
        d = date.today().isoformat()
        self._mem("a.md", "unverified", d)
        def boom(body):
            raise RuntimeError("model down")
        r = self.m.rejudge_pass(judge_fn=boom)
        self.assertEqual(r, {"promoted": 0, "kept": 0, "failed": 1})
        self.assertEqual(self._status("a.md"), "unverified")

    def test_nocloud_localhost_evil_com_is_flagged(self):
        """Bypass via http://localhost.evil.com — naive substring match misses this; parse-based must catch it."""
        os.environ["KB_LLM_ENDPOINT"] = "http://localhost.evil.com:11434"
        w = self.m.cloud_warnings()
        self.assertTrue(any("endpoint" in x.lower() for x in w),
                        f"Expected endpoint warning for localhost.evil.com, got: {w}")

    def test_nocloud_ollama_not_first_in_chain_still_checked(self):
        """KB_LLM_PROVIDERS='foo, ollama' + remote endpoint must still warn (ollama not at chain[0])."""
        os.environ["KB_LLM_PROVIDERS"] = "foo, ollama"
        os.environ["KB_LLM_ENDPOINT"] = "http://192.168.1.50:11434"
        w = self.m.cloud_warnings()
        self.assertTrue(any("endpoint" in x.lower() for x in w),
                        f"Expected endpoint warning for ollama-not-first, got: {w}")


if __name__ == "__main__":
    unittest.main()

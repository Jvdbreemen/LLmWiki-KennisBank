from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _maintenance as mnt  # noqa: E402
import _memory  # noqa: E402
import _judge  # noqa: E402


class RecheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-rc-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = _memory.write("Ruis", "iets nietszeggends", status="current", created="2026-06-01")
        self._orig = _judge.judge

    def tearDown(self):
        import shutil
        _judge.judge = self._orig
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recheck_retracts_non_current(self):
        _judge.judge = lambda cand, context="": {"verdict": "unverified", "reason": "ruis"}
        n = mnt.recheck_pass()
        self.assertEqual(n, 1)
        self.assertEqual(_memory.read_status(self.m), "retracted")

    def test_recheck_keeps_current(self):
        _judge.judge = lambda cand, context="": {"verdict": "current", "reason": "ok"}
        self.assertEqual(mnt.recheck_pass(), 0)
        self.assertEqual(_memory.read_status(self.m), "current")

    def test_cluster_marks_neighbors(self):
        _memory.write("A", "onderwerp x een", status="current", created="2026-06-01")
        _memory.write("B", "onderwerp x twee", status="current", created="2026-06-02")
        _memory.write("C", "onderwerp x drie", status="current", created="2026-06-03")
        gc = lambda p, cache, recompute=True: [1.0, 0.0, 0.0]  # alles identiek -> buren
        n = mnt.cluster_promote_pass(threshold=0.5, min_neighbors=2, get_cached_fn=gc)
        self.assertGreaterEqual(n, 1)


if __name__ == "__main__":
    unittest.main()

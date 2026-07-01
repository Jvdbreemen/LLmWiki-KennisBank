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
import _llm  # noqa: E402


class SupersedeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-sup-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.old = _memory.write("Jim zoekt baan", "Jim is op zoek naar een nieuwe baan.",
                                 status="current", created="2026-01-01")
        self.new = _memory.write("Jim heeft baan", "Jim heeft de nieuwe baan gekregen.",
                                 status="current", created="2026-06-01")
        # injecteer vectoren: oud en nieuw liggen dicht bij elkaar (zelfde onderwerp)
        self._gc = lambda p, cache, recompute=True: [1.0, 0.0] if True else None
        self._orig_gen = _llm.generate

    def tearDown(self):
        import shutil
        _llm.generate = self._orig_gen
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_supersede_marks_older(self):
        _llm.generate = lambda *a, **k: '{"supersede": true, "reason": "Jim heeft nu de baan"}'
        n = mnt.supersede_pass(threshold=0.5, get_cached_fn=self._gc)
        self.assertEqual(n, 1)
        self.assertEqual(_memory.read_status(self.old), "superseded")
        self.assertEqual(_memory.read_status(self.new), "current")
        self.assertIn("superseded_by", self.old.read_text(encoding="utf-8"))

    def test_no_supersede_when_judge_false(self):
        _llm.generate = lambda *a, **k: '{"supersede": false}'
        n = mnt.supersede_pass(threshold=0.5, get_cached_fn=self._gc)
        self.assertEqual(n, 0)
        self.assertEqual(_memory.read_status(self.old), "current")

    def test_failsafe_on_model_none(self):
        _llm.generate = lambda *a, **k: None
        self.assertEqual(mnt.supersede_pass(threshold=0.5, get_cached_fn=self._gc), 0)
        self.assertEqual(_memory.read_status(self.old), "current")

    def test_supersede_stamps_valid_until(self):
        _llm.generate = lambda *a, **k: '{"supersede": true, "reason": "vervangen"}'
        mnt.supersede_pass(threshold=0.5, get_cached_fn=self._gc)
        old_txt = self.old.read_text(encoding="utf-8")
        # oud feit gold tot het nieuwe inging (valid_from nieuw = created 2026-06-01)
        self.assertIn("valid_until: 2026-06-01", old_txt)

    def test_orders_on_event_time_not_capture_time(self):
        # Laat gecaptured OUD feit (created later, valid_from 2025) mag het
        # event-nieuwere feit (2026) NIET sluiten; ordening op valid_from.
        for f in (self.vault / "09-memory").glob("*.md"):
            f.unlink()
        newer_fact = _memory.write("Jim heeft baan", "Jim heeft een baan.",
                                   status="current", created="2026-01-01",
                                   valid_from="2026-01-01")
        stale_capture = _memory.write("Jim zoekt baan", "Jim zoekt een baan.",
                                      status="current", created="2026-07-01",
                                      valid_from="2025-01-01")
        _llm.generate = lambda *a, **k: '{"supersede": true, "reason": "x"}'
        n = mnt.supersede_pass(threshold=0.5, get_cached_fn=self._gc)
        self.assertEqual(n, 1)
        # het event-OUDERE feit wordt gesloten, niet het nieuwere
        self.assertEqual(_memory.read_status(stale_capture), "superseded")
        self.assertEqual(_memory.read_status(newer_fact), "current")
        # en het interval is coherent: valid_until (2026-01-01) >= valid_from (2025-01-01)
        self.assertIn("valid_until: 2026-01-01",
                      stale_capture.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

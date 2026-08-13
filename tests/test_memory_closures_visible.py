"""A closed memory has to surface somewhere, or "reversible" is a fiction.

The design leans on superseding being safe because nothing is deleted: the file
stays, with `superseded_by` and `valid_until`. True on disk, false in practice —
recall filters on `current`, and `/kennisbank:review` walks the `unverified`
queue only. A wrongly closed memory therefore appeared in no path a human uses,
which is functionally the same as deletion (TASK-150).

These tests hold the claim to its word: every closure is recorded with what
replaced it and why, and reopening restores the memory to the recall set.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _memory  # noqa: E402


class ClosureLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-closed-"))
        (self.tmp / "09-memory").mkdir(parents=True)
        (self.tmp / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, title="Oud feit", status="current"):
        return _memory.write(title, "de oude tekst", status=status, created="2026-01-01")

    def test_a_supersession_is_recorded_with_its_successor_and_reason(self):
        p = self._write()
        self.assertTrue(_memory.set_status(p, "superseded",
                                           superseded_by=["2026-08-13-nieuw-feit"],
                                           valid_until="2026-08-13",
                                           reason="nieuw model gepind"))
        rows = _memory.recent_closures()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["stem"], p.stem)
        self.assertEqual(rows[0]["status"], "superseded")
        self.assertEqual(rows[0]["superseded_by"], ["2026-08-13-nieuw-feit"])
        self.assertIn("nieuw model", rows[0]["reason"])

    def test_promoting_to_current_is_not_a_closure(self):
        """Only statuses that remove a memory from recall belong in this log."""
        p = self._write(status="unverified")
        _memory.set_status(p, "current")
        self.assertEqual(_memory.recent_closures(), [])

    def test_retracted_and_expired_count_as_closures(self):
        for i, status in enumerate(("retracted", "expired")):
            p = self._write(title=f"Feit {i}")
            _memory.set_status(p, status)
        self.assertEqual({r["status"] for r in _memory.recent_closures()},
                         {"retracted", "expired"})

    def test_newest_first(self):
        for i in range(3):
            _memory.set_status(self._write(title=f"Feit {i}"), "superseded")
        rows = _memory.recent_closures()
        self.assertEqual([r["stem"].split("-")[-1] for r in rows], ["2", "1", "0"])

    def test_reopen_restores_the_memory_to_the_recall_set(self):
        p = self._write()
        _memory.set_status(p, "superseded", superseded_by=["opvolger"],
                           valid_until="2026-08-13")
        self.assertEqual(_memory.read_status(p), "superseded")

        self.assertTrue(_memory.reopen(p))
        self.assertEqual(_memory.read_status(p), "current",
                         "recall filtert op current, dus dit is de hele terugweg")
        text = p.read_text(encoding="utf-8")
        self.assertNotIn("superseded_by:", text)
        self.assertNotIn("valid_until:", text)

    def test_reopening_is_itself_recorded(self):
        p = self._write()
        _memory.set_status(p, "superseded", superseded_by=["opvolger"])
        _memory.reopen(p)
        self.assertIn("reopened", _memory.recent_closures()[0]["status"])

    def test_reopen_leaves_the_body_untouched(self):
        """Reopen mutates frontmatter only; the knowledge itself is not rewritten.

        Measured against the state AFTER set_status, not after render: set_status
        already normalises the blank line between the closing fence and the body,
        and has done so since long before this change. Asserting round-trip
        identity with the rendered file would pin someone else's behaviour to
        this test and fail for a reason that has nothing to do with reopening.
        """
        p = self._write()
        _memory.set_status(p, "superseded", superseded_by=["opvolger"])
        before = p.read_text(encoding="utf-8").split("---", 2)[2]
        _memory.reopen(p)
        self.assertEqual(p.read_text(encoding="utf-8").split("---", 2)[2], before)

    def test_a_broken_log_never_blocks_the_closure(self):
        """The log is a record, not a gate: capture must not depend on it."""
        p = self._write()
        (self.tmp / ".claude" / _memory.CLOSED_LOG).mkdir()  # directory op de logpad
        self.assertTrue(_memory.set_status(p, "superseded", superseded_by=["x"]))
        self.assertEqual(_memory.read_status(p), "superseded")


if __name__ == "__main__":
    unittest.main()

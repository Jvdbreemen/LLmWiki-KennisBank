"""The audit view's undo edge: demote reverses a promotion, nothing else.

TASK-195 removed the human from the decision loop; /kennisbank:review became
an after-the-fact audit view. Its undo for promotions is demote(): exactly
one legal edge (current -> unverified), mirroring promote()'s single edge in
the other direction. A demote that could touch closed statuses would reopen
closures made for cause — that refusal is the safety property under test.

Imports happen inside setUp, after the env points at a temp vault: module-
level imports would freeze _embeddings.CACHE_FILE onto the real vault during
collection and tax every later test (TASK-196).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_doctor():
    spec = importlib.util.spec_from_file_location(
        "memory_doctor", str(SCRIPTS / "memory-doctor.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class DemoteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-audit-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        import _memory
        self.mem = _memory

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, stem, status):
        p = self.vault / "09-memory" / f"{stem}.md"
        p.write_text(f"---\ntitle: {stem}\ntype: memory\nstatus: {status}\n"
                     f"created: 2026-08-01\n---\n\nBody of {stem}.\n",
                     encoding="utf-8")
        return p

    def _status(self, p):
        import re
        m = re.search(r"^status:\s*(\w+)", p.read_text(encoding="utf-8"),
                      re.MULTILINE)
        return m.group(1) if m else None

    def test_demote_reverses_a_promotion_with_an_audit_line(self):
        p = self._mem("m", "current")
        self.assertTrue(self.mem.demote(p, reason="promotie was voorbarig"))
        self.assertEqual(self._status(p), "unverified")
        row = self.mem.recent_promotions()[0]
        self.assertEqual(row["action"], "demote")
        self.assertEqual(row["route"], "undo")
        self.assertIn("voorbarig", row["reason"])

    def test_demote_refuses_every_status_but_current(self):
        """The single-edge rule: a demote pass may never reopen closures."""
        for status in ("unverified", "retracted", "superseded", "expired"):
            p = self._mem(f"m-{status}", status)
            self.assertFalse(self.mem.demote(p), status)
            self.assertEqual(self._status(p), status)

    def test_promote_then_demote_is_one_story_in_one_log(self):
        p = self._mem("m", "unverified")
        self.assertTrue(self.mem.promote(p, reason="bewijs", route="client",
                                         prompt_version="autoreview-1"))
        self.assertTrue(self.mem.demote(p))
        rows = self.mem.recent_promotions(limit=2)
        self.assertEqual([r.get("action") for r in rows], ["demote", None])
        self.assertEqual({r["stem"] for r in rows}, {"m"})
        # and the memory is eligible for the next cycle again
        self.assertEqual(self._status(p), "unverified")

    def test_body_survives_a_demote(self):
        # Compare stripped: promote/demote normalise the blank line after the
        # frontmatter fence; the CONTENT must be untouched.
        p = self._mem("m", "current")
        before = p.read_text(encoding="utf-8").split("---")[-1].strip()
        self.mem.demote(p)
        self.assertEqual(
            p.read_text(encoding="utf-8").split("---")[-1].strip(), before)


class AuditCliTest(DemoteTest):
    """The CLI wrappers the /kennisbank:review command drives."""

    def setUp(self):
        super().setUp()
        self.doc = _load_doctor()

    def test_demote_subcommand_flips_and_reports(self):
        p = self._mem("m", "current")
        self.assertEqual(self.doc.main(["demote", "m"]), 0)
        self.assertEqual(self._status(p), "unverified")

    def test_demote_subcommand_fails_loudly_on_missing_or_wrong_status(self):
        self.assertEqual(self.doc.main(["demote", "nope"]), 1)
        self._mem("q", "retracted")
        self.assertEqual(self.doc.main(["demote", "q"]), 1)

    def test_promotions_subcommand_renders_both_directions(self):
        p = self._mem("m", "unverified")
        self.mem.promote(p, reason="citaat", route="client",
                         prompt_version="autoreview-1")
        self.mem.demote(p)
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(self.doc.main(["promotions", "--json"]), 0)
        rows = json.loads(buf.getvalue())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["action"], "demote")
        self.assertEqual(rows[1]["route"], "client")


if __name__ == "__main__":
    unittest.main()

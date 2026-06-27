"""Tests voor scripts/_sweepstate.py - watermark + transcript-reader."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _sweepstate as ss  # noqa: E402


class SweepStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-sweep-"))
        self.vault = self.tmp / "vault"
        self.tdir = self.vault / "01-raw" / "transcripts"
        self.tdir.mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _t(self, name, records):
        p = self.tdir / name
        p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        return p

    def test_pending_excludes_marked(self):
        self._t("a.jsonl", [{"type": "user", "message": {"role": "user", "content": "hoi"}}])
        self._t("b.jsonl", [{"type": "user", "message": {"role": "user", "content": "hoi"}}])
        self.assertEqual({p.stem for p in ss.pending()}, {"a", "b"})
        ss.mark(["a"])
        self.assertEqual({p.stem for p in ss.pending()}, {"b"})

    def test_mark_is_idempotent(self):
        self._t("a.jsonl", [{"type": "user", "message": {"role": "user", "content": "x"}}])
        ss.mark(["a"])
        ss.mark(["a"])
        self.assertEqual(ss.pending(), [])

    def test_transcript_text_reduces_messages(self):
        p = self._t("c.jsonl", [
            {"type": "user", "message": {"role": "user", "content": "Repareer de bug"}},
            {"type": "assistant", "message": {"role": "assistant",
                "content": [{"type": "text", "text": "Token-expiry fix"}]}},
        ])
        txt = ss.transcript_text(p)
        self.assertIn("Repareer de bug", txt)
        self.assertIn("Token-expiry fix", txt)

    def test_transcript_text_failsoft(self):
        bad = self.tdir / "bad.jsonl"
        bad.write_text("{ kapot json", encoding="utf-8")
        self.assertEqual(ss.transcript_text(bad), "")


if __name__ == "__main__":
    unittest.main()

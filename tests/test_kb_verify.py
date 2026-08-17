"""Tests for scripts/kb-verify.py - the deliberate drain of the unverified backlog.

The CLI and the sweep MUST use the same candidate selection. Until TASK-198 it
lived as a copied block in both, and two copies of a selection rule are one
edit away from a CLI and a sweep judging different sets. These tests pin the
shared behaviour plus the two things the CLI may do differently: run dry
without bookkeeping, and ignore the cooldown because a person asked for it.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load():
    spec = importlib.util.spec_from_file_location("kb_verify", str(SCRIPTS / "kb-verify.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class KbVerifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-verify-"))
        self.vault = self.tmp / "vault"
        (self.vault / "01-raw" / "transcripts").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

        (self.vault / "01-raw" / "transcripts" / "s1.jsonl").write_text(
            json.dumps({"type": "user", "message": {
                "role": "user", "content": "De drempel is 0.75 geworden."}}),
            encoding="utf-8")

        import _llm
        import _embeddings
        import _groundcheck
        self._llm, self._emb, self._gc = _llm, _embeddings, _groundcheck
        self._orig = (_llm.generate, _embeddings.embed)
        _embeddings.embed = lambda *a, **k: [0.1, 0.2]
        self.m = _load()

    def tearDown(self):
        self._llm.generate, self._emb.embed = self._orig
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, stem, created="2026-07-01"):
        p = self.vault / "09-memory" / f"{stem}.md"
        p.write_text("\n".join([
            "---", f"title: {stem}", "type: memory", "status: unverified",
            'source_session: "s1.jsonl"', f"created: {created}",
            'source_chunk: "1/1"', "---", "", f"Claim uit {stem}.", ""]),
            encoding="utf-8")
        return p

    def _key(self, stem):
        return self._gc.attempt_key(self.vault / "09-memory" / f"{stem}.md")

    def _says(self, verdict):
        self._llm.generate = lambda *a, **k: json.dumps(
            {"verdict": verdict, "reason": "citaat"})

    def test_a_dry_run_records_no_attempt(self):
        """A dry run writes nothing -- not even a cooldown.

        A --dry-run that kept books would rob the real run after it of its own
        candidates for as long as the window lasts.
        """
        self._mem("m")
        self._says("partial")
        self.assertEqual(self.m.main(["--dry-run"]), 0)
        self.assertEqual(self._gc.load_attempts(), {})

    def test_a_real_run_records_the_verdict(self):
        self._mem("m")
        self._says("partial")
        self.assertEqual(self.m.main([]), 0)
        self.assertEqual(
            self._gc.load_attempts()[self._key("m")]["verdict"], "partial")

    def test_a_settled_memory_is_skipped_by_default(self):
        self._mem("m")
        self._gc.record_attempt(self._key("m"), "partial")
        self._says("supported")
        self.assertEqual(self.m.main([]), 0)
        from _frontmatter import parse_frontmatter
        fm, _ = parse_frontmatter(
            (self.vault / "09-memory" / "m.md").read_text(encoding="utf-8"))
        self.assertEqual(fm["status"], "unverified")

    def test_retry_settled_drains_it_anyway(self):
        """The CLI is the deliberate drain: ask for it and you get the backlog."""
        self._mem("m")
        self._gc.record_attempt(self._key("m"), "partial")
        self._says("supported")
        self.assertEqual(self.m.main(["--retry-settled"]), 0)
        from _frontmatter import parse_frontmatter
        fm, _ = parse_frontmatter(
            (self.vault / "09-memory" / "m.md").read_text(encoding="utf-8"))
        self.assertEqual(fm["status"], "current")

    def test_an_unreachable_model_exits_one(self):
        """TASK-148: 'nothing to do' and 'could not run' are not the same thing."""
        self._mem("m")
        self._llm.generate = lambda *a, **k: ""
        self.assertEqual(self.m.main([]), 1)


if __name__ == "__main__":
    unittest.main()

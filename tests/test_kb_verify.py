"""Tests voor scripts/kb-verify.py - de bewuste drain van de unverified backlog.

De CLI en de sweep MOETEN dezelfde kandidaatselectie gebruiken. Tot TASK-198
stond die als gekopieerd blok in allebei; twee kopieën van een selectieregel
zijn één wijziging verwijderd van een CLI en een sweep die verschillende
verzamelingen beoordelen. De tests hier pinnen het gedeelde gedrag plus de twee
dingen die de CLI wél apart mag: droogdraaien zonder boekhouding, en de
cooldown negeren omdat de mens er expliciet om vroeg.
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

    def _says(self, verdict):
        self._llm.generate = lambda *a, **k: json.dumps(
            {"verdict": verdict, "reason": "citaat"})

    def test_a_dry_run_records_no_attempt(self):
        """Droogdraaien schrijft niets -- ook geen cooldown.

        Een --dry-run die wel boekhoudt zou de echte run die erop volgt een
        week lang van zijn eigen kandidaten beroven.
        """
        self._mem("m")
        self._says("partial")
        self.assertEqual(self.m.main(["--dry-run"]), 0)
        self.assertEqual(self._gc.load_attempts(), {})

    def test_a_real_run_records_the_verdict(self):
        self._mem("m")
        self._says("partial")
        self.assertEqual(self.m.main([]), 0)
        self.assertEqual(self._gc.load_attempts()["m"]["verdict"], "partial")

    def test_a_settled_memory_is_skipped_by_default(self):
        self._mem("m")
        self._gc.record_attempt("m", "partial")
        self._says("supported")
        self.assertEqual(self.m.main([]), 0)
        from _frontmatter import parse_frontmatter
        fm, _ = parse_frontmatter(
            (self.vault / "09-memory" / "m.md").read_text(encoding="utf-8"))
        self.assertEqual(fm["status"], "unverified")

    def test_retry_settled_drains_it_anyway(self):
        """De CLI is de bewuste drain; wie erom vraagt krijgt de hele backlog."""
        self._mem("m")
        self._gc.record_attempt("m", "partial")
        self._says("supported")
        self.assertEqual(self.m.main(["--retry-settled"]), 0)
        from _frontmatter import parse_frontmatter
        fm, _ = parse_frontmatter(
            (self.vault / "09-memory" / "m.md").read_text(encoding="utf-8"))
        self.assertEqual(fm["status"], "current")

    def test_an_unreachable_model_exits_one(self):
        """TASK-148: 'niets te doen' en 'kon niet draaien' zijn niet hetzelfde."""
        self._mem("m")
        self._llm.generate = lambda *a, **k: ""
        self.assertEqual(self.m.main([]), 1)


if __name__ == "__main__":
    unittest.main()

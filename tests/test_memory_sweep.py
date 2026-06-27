"""Tests voor scripts/memory-sweep.py - de orkestrator. Alle LLM/embed-seams
gemockt; geen echt model. Vault naar temp."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load():
    spec = importlib.util.spec_from_file_location("memory_sweep", str(SCRIPTS_DIR / "memory-sweep.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class MemorySweepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-msweep-"))
        self.vault = self.tmp / "vault"
        (self.vault / "01-raw" / "transcripts").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        # een pending transcript
        (self.vault / "01-raw" / "transcripts" / "s1.jsonl").write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "Bug X opgelost"}}),
            encoding="utf-8")
        self.m = _load()
        import _extract, _judge
        import _embeddings as emb
        # Save originals (4: extract, judge, embed, get_cached)
        self._orig = (_extract.extract_candidates, _judge.judge, emb.embed, emb.get_cached)
        _extract.extract_candidates = lambda text, max_n=8: [{"title": "Bug X", "body": "opgelost via Y"}]
        _judge.judge = lambda cand, context="": {"verdict": "current", "reason": "duidelijk"}
        emb.embed = lambda text, timeout=30.0: [0.1, 0.2, 0.3]
        # Also mock get_cached so the dedup pool uses the same fixed vector
        # for existing 09-memory files — ensures dedup test exercises the path.
        emb.get_cached = lambda f, cache, recompute=True: [0.1, 0.2, 0.3]
        self.emb, self._extract, self._judge = emb, _extract, _judge

    def tearDown(self):
        import shutil
        (self._extract.extract_candidates,
         self._judge.judge,
         self.emb.embed,
         self.emb.get_cached) = self._orig
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sweep_writes_current_memory_and_marks(self):
        summary = self.m.run_sweep()
        mems = list((self.vault / "09-memory").glob("*.md"))
        self.assertEqual(len(mems), 1)
        self.assertIn("status: current", mems[0].read_text(encoding="utf-8"))
        self.assertIn("evidence_basis: agent", mems[0].read_text(encoding="utf-8"))
        # tweede run verwerkt niets nieuws (watermark)
        self.assertEqual(self.m.run_sweep()["processed"], 0)

    def test_doubt_writes_unverified(self):
        self._judge.judge = lambda cand, context="": {"verdict": "unverified", "reason": "vaag"}
        self.m.run_sweep()
        mem = list((self.vault / "09-memory").glob("*.md"))[0]
        self.assertIn("status: unverified", mem.read_text(encoding="utf-8"))

    def test_dedup_skips_near_duplicate(self):
        # bestaande memory met dezelfde embedding -> kandidaat is duplicaat
        import _memory
        _memory.write("Bestaand", "iets", created="2026-06-27")
        # emb.embed EN emb.get_cached geven dezelfde vaste vector terug ->
        # kandidaat cosine 1.0 > 0.92 -> duplicaat -> overgeslagen
        summary = self.m.run_sweep()
        self.assertEqual(summary.get("written", 0), 0)
        self.assertGreaterEqual(summary.get("duplicates", 0), 1)

    def test_gated_off_does_nothing(self):
        (self.vault / "kennisbank-settings.json").write_text(
            json.dumps({"memory_capture": False}), encoding="utf-8")
        summary = self.m.run_sweep()
        self.assertEqual(list((self.vault / "09-memory").glob("*.md")), [])
        self.assertFalse(summary.get("enabled", True))

    def test_heartbeat_written(self):
        self.m.run_sweep()
        hb = self.vault / ".claude" / "memory-sweep-status.json"
        self.assertTrue(hb.exists())
        data = json.loads(hb.read_text(encoding="utf-8"))
        self.assertIn("last_run", data)

    def test_expire_pass_flips_past_expires(self):
        import _memory
        old = _memory.write("Vluchtig", "iets", status="current",
                            expires="2000-01-01", created="2026-06-27")
        self.m.run_sweep()
        self.assertIn("status: expired", old.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

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
        import _extract, _judge, _llm
        import _embeddings as emb
        import _sweepstate as _ss
        # Save originals (4: extract, judge, embed, get_cached + llm.generate + transcript_text)
        self._orig = (_extract.extract_candidates, _judge.judge, emb.embed, emb.get_cached)
        self._orig_generate = _llm.generate
        self._orig_transcript_text = _ss.transcript_text
        self._llm = _llm
        self._ss = _ss
        # Mock _llm.generate so the model-probe in run_sweep succeeds without Ollama.
        _llm.generate = lambda *a, **k: "ok"
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
        self._llm.generate = self._orig_generate
        self._ss.transcript_text = self._orig_transcript_text
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


    def test_per_transcript_error_increments_errors(self):
        """COVERAGE: per-transcript exception → errors telt mee, transcript blijft pending."""
        import _sweepstate as _ss

        def _raise(_p):
            raise RuntimeError("forced transcript error")

        _ss.transcript_text = _raise
        try:
            summary = self.m.run_sweep()
            self.assertGreaterEqual(summary.get("errors", 0), 1,
                                    "errors should be at least 1")
            # Transcript is NOT marked (exception prevented ss.mark)
            self.assertGreater(len(_ss.pending()), 0,
                               "transcript should still be pending after error")
        finally:
            _ss.transcript_text = self._orig_transcript_text

    def test_source_session_in_memory_frontmatter(self):
        """COVERAGE: source_session in frontmatter komt overeen met de transcriptnaam."""
        self.m.run_sweep()
        mems = list((self.vault / "09-memory").glob("*.md"))
        self.assertEqual(len(mems), 1)
        txt = mems[0].read_text(encoding="utf-8")
        self.assertIn("s1.jsonl", txt, "source_session must reference the transcript filename")

    def test_expire_quoted_status_flips_correctly(self):
        """BUG 3: status: \"current\" (quoted in file) moet naar expired flippen."""
        import _memory
        old_path = _memory.write("Vluchtig", "iets", status="current",
                                 expires="2000-01-01", created="2026-06-27")
        # Overschrijf status-regel met quoted variant (de bug-trigger)
        content = old_path.read_text(encoding="utf-8")
        quoted = content.replace("status: current", 'status: "current"', 1)
        old_path.write_text(quoted, encoding="utf-8")
        self.assertIn('status: "current"', old_path.read_text(encoding="utf-8"))
        self.m.run_sweep()
        result = old_path.read_text(encoding="utf-8")
        self.assertIn("status: expired", result,
                      "quoted status: current should be flipped to expired")
        self.assertNotIn("status: current", result)

    def test_model_down_marks_nothing(self):
        """IMPORTANT 1: chat-model onbereikbaar → transcript mag NIET gemarkeerd worden."""
        import _sweepstate as _ss
        self._llm.generate = lambda *a, **k: None  # chat down (embed blijft truthy)
        try:
            summary = self.m.run_sweep()
            # (a) transcript still pending
            self.assertGreater(len(_ss.pending()), 0,
                               "transcript should still be pending when model is down")
            # (b) no memory written
            mems = list((self.vault / "09-memory").glob("*.md"))
            self.assertEqual(len(mems), 0,
                             "no memory may be written when model is down")
            # (c) heartbeat has model_unreachable truthy
            hb = self.vault / ".claude" / "memory-sweep-status.json"
            self.assertTrue(hb.exists(), "heartbeat should be written")
            data = json.loads(hb.read_text(encoding="utf-8"))
            self.assertTrue(data.get("model_unreachable"),
                            "heartbeat must flag model_unreachable")
        finally:
            self._llm.generate = self._orig_generate

    def test_embed_down_marks_nothing(self):
        """Embed-follow-up: embed-backend down (chat up) → transcript NIET gemarkeerd.

        Spiegel van test_model_down_marks_nothing: een embed-only-outage moet
        symmetrisch upfront opgevangen worden, anders watermark-burn."""
        import _sweepstate as _ss
        self.emb.embed = lambda *a, **k: None  # embed down (chat blijft "ok")
        try:
            summary = self.m.run_sweep()
            # (a) transcript still pending
            self.assertGreater(len(_ss.pending()), 0,
                               "transcript should still be pending when embed is down")
            # (b) no memory written
            mems = list((self.vault / "09-memory").glob("*.md"))
            self.assertEqual(len(mems), 0,
                             "no memory may be written when embed is down")
            # (c) heartbeat has model_unreachable truthy
            hb = self.vault / ".claude" / "memory-sweep-status.json"
            self.assertTrue(hb.exists(), "heartbeat should be written")
            data = json.loads(hb.read_text(encoding="utf-8"))
            self.assertTrue(data.get("model_unreachable"),
                            "heartbeat must flag model_unreachable on embed outage")
        finally:
            self.emb.embed = self._orig[2]


if __name__ == "__main__":
    unittest.main()

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

    def test_expire_pass_stamps_valid_until(self):
        import _memory
        old = _memory.write("Vluchtig", "iets", status="current",
                            expires="2000-01-01", created="1999-06-27")
        self.m.run_sweep()
        self.assertIn("valid_until: 2000-01-01", old.read_text(encoding="utf-8"))

    def test_new_memory_gets_valid_from(self):
        # s1.jsonl heeft geen datum-prefix -> valid_from valt terug op created.
        self.m.run_sweep()
        mem = list((self.vault / "09-memory").glob("*.md"))[0]
        txt = mem.read_text(encoding="utf-8")
        self.assertIn("valid_from: ", txt)

    def _dated_transcript_in_reconcile_band(self):
        """Vervang s1.jsonl door een gedateerd transcript en zet de embeddings
        zo dat de kandidaat in de reconcile-band valt (cosine 0.9 met bestaand:
        boven RECONCILE_THRESHOLD 0.75, onder dup-drempel 0.92)."""
        tdir = self.vault / "01-raw" / "transcripts"
        (tdir / "s1.jsonl").unlink()
        (tdir / "2026-06-25-jim.jsonl").write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "Jim update"}}),
            encoding="utf-8")
        self.emb.embed = lambda text, timeout=30.0: [0.9, 0.4358899, 0.0]
        self.emb.get_cached = lambda f, cache, recompute=True: [1.0, 0.0, 0.0]

    def test_reconcile_supersedes_existing_at_write(self):
        import _memory
        import _reconcile
        old = _memory.write("Jim zoekt baan", "Jim zoekt een baan",
                            status="current", created="2026-01-01")
        self._dated_transcript_in_reconcile_band()
        orig = _reconcile.judge_reconcile
        _reconcile.judge_reconcile = lambda new, o: "SUPERSEDE"
        self.addCleanup(lambda: setattr(_reconcile, "judge_reconcile", orig))
        summary = self.m.run_sweep()
        self.assertEqual(summary.get("reconciled_superseded", 0), 1)
        old_txt = old.read_text(encoding="utf-8")
        self.assertIn("status: superseded", old_txt)
        self.assertIn("valid_until: 2026-06-25", old_txt)
        new_files = [f for f in (self.vault / "09-memory").glob("*.md") if f != old]
        self.assertEqual(len(new_files), 1)
        new_txt = new_files[0].read_text(encoding="utf-8")
        self.assertIn("valid_from: 2026-06-25", new_txt)
        self.assertIn(new_files[0].stem, old_txt)  # superseded_by-link

    def test_reconcile_noop_skips_writing(self):
        import _memory
        import _reconcile
        _memory.write("Jim zoekt baan", "Jim zoekt een baan",
                      status="current", created="2026-01-01")
        self._dated_transcript_in_reconcile_band()
        orig = _reconcile.judge_reconcile
        _reconcile.judge_reconcile = lambda new, o: "NOOP"
        self.addCleanup(lambda: setattr(_reconcile, "judge_reconcile", orig))
        summary = self.m.run_sweep()
        self.assertEqual(summary.get("written", 0), 0)
        self.assertGreaterEqual(summary.get("reconcile_noop", 0), 1)
        self.assertEqual(len(list((self.vault / "09-memory").glob("*.md"))), 1)

    def test_unverified_candidate_does_not_supersede_current(self):
        # Quarantaine-kennis mag geen geverifieerd feit sluiten: judge zegt
        # unverified -> supersedes worden NIET toegepast.
        import _memory
        import _reconcile
        old = _memory.write("Jim zoekt baan", "Jim zoekt een baan",
                            status="current", created="2026-01-01")
        self._dated_transcript_in_reconcile_band()
        self._judge.judge = lambda cand, context="": {"verdict": "unverified", "reason": "vaag"}
        orig = _reconcile.judge_reconcile
        _reconcile.judge_reconcile = lambda new, o: "SUPERSEDE"
        self.addCleanup(lambda: setattr(_reconcile, "judge_reconcile", orig))
        summary = self.m.run_sweep()
        self.assertEqual(summary.get("reconciled_superseded", 0), 0)
        self.assertIn("status: current", old.read_text(encoding="utf-8"))
        self.assertEqual(summary.get("unverified", 0), 1)  # kandidaat wel geschreven

    def test_flipback_against_closed_memory_reaches_reconcile(self):
        # Her-assertie van een eerder GESLOTEN feit met latere valid_from is
        # geen duplicaat: de kandidaat moet de reconcile-laag bereiken.
        import _memory
        closed = _memory.write("Jim zoekt baan", "Jim zoekt een baan",
                               status="superseded", created="2026-01-01",
                               valid_from="2026-01-01", valid_until="2026-02-01")
        self._dated_transcript_in_reconcile_band()
        # kandidaat embedt IDENTIEK aan het gesloten memory (cosine 1.0)
        self.emb.embed = lambda text, timeout=30.0: [1.0, 0.0, 0.0]
        summary = self.m.run_sweep()
        self.assertEqual(summary.get("duplicates", 0), 0)
        self.assertEqual(summary.get("written", 0), 1)
        self.assertIn("status: superseded", closed.read_text(encoding="utf-8"))

    def test_same_era_recapture_of_closed_memory_still_dedups(self):
        # Her-capture uit hetzelfde tijdperk (valid_from <= valid_until van het
        # gesloten memory) blijft een duplicaat: --all-rebuild idempotentie.
        import _memory
        _memory.write("Jim zoekt baan", "Jim zoekt een baan",
                      status="superseded", created="2026-01-01",
                      valid_from="2026-01-01", valid_until="2026-02-01")
        tdir = self.vault / "01-raw" / "transcripts"
        (tdir / "s1.jsonl").unlink()
        (tdir / "2026-01-15-jim.jsonl").write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "Jim"}}),
            encoding="utf-8")
        self.emb.embed = lambda text, timeout=30.0: [1.0, 0.0, 0.0]
        self.emb.get_cached = lambda f, cache, recompute=True: [1.0, 0.0, 0.0]
        summary = self.m.run_sweep()
        self.assertEqual(summary.get("written", 0), 0)
        self.assertGreaterEqual(summary.get("duplicates", 0), 1)

    def test_expire_pass_failure_does_not_break_sweep(self):
        # Een exception in de expire-pass mag de sweep-afronding (heartbeat)
        # niet blokkeren: errors telt op, run_sweep keert normaal terug.
        def _boom():
            raise RuntimeError("malformed memory-file")
        self.m._expire_pass = _boom
        summary = self.m.run_sweep()
        self.assertGreaterEqual(summary.get("errors", 0), 1)
        self.assertTrue((self.vault / ".claude" / "memory-sweep-status.json").exists())

    def test_reconcile_temporal_guard_blocks_old_transcript(self):
        # Kandidaat uit een OUDER transcript (2025) mag een nieuwer feit
        # (valid_from 2026-01-01) niet sluiten -> gewoon ADD, geen supersede.
        import _memory
        import _reconcile
        old = _memory.write("Jim heeft baan", "Jim heeft een baan",
                            status="current", created="2026-01-01")
        tdir = self.vault / "01-raw" / "transcripts"
        (tdir / "s1.jsonl").unlink()
        (tdir / "2025-01-01-jim.jsonl").write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "Jim oud"}}),
            encoding="utf-8")
        self.emb.embed = lambda text, timeout=30.0: [0.9, 0.4358899, 0.0]
        self.emb.get_cached = lambda f, cache, recompute=True: [1.0, 0.0, 0.0]
        orig = _reconcile.judge_reconcile
        _reconcile.judge_reconcile = lambda new, o: "SUPERSEDE"
        self.addCleanup(lambda: setattr(_reconcile, "judge_reconcile", orig))
        summary = self.m.run_sweep()
        self.assertEqual(summary.get("reconciled_superseded", 0), 0)
        self.assertIn("status: current", old.read_text(encoding="utf-8"))
        self.assertEqual(summary.get("written", 0), 1)


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

    def test_rebuild_all_reprocesses_marked(self):
        # eerste sweep markeert s1 als swept
        self.m.run_sweep()
        # normale 2e sweep doet niets
        self.assertEqual(self.m.run_sweep()["processed"], 0)
        # --all negeert de watermark en verwerkt s1 opnieuw...
        s = self.m.run_sweep(ignore_watermark=True)
        self.assertEqual(s["processed"], 1)
        # ...maar dedup voorkomt een tweede memory-file (idempotent)
        mems = list((self.vault / "09-memory").glob("*.md"))
        self.assertEqual(len(mems), 1)

    def test_rebuild_all_processes_more_than_max_transcripts(self):
        """IMPORTANT 3: ignore_watermark=True moet ALLE transcripts verwerken, ook > max_transcripts."""
        tdir = self.vault / "01-raw" / "transcripts"
        # Maak 11 extra transcripts (s1 bestaat al in setUp → totaal 12).
        for i in range(2, 13):
            (tdir / f"s{i}.jsonl").write_text(
                json.dumps({"type": "user",
                            "message": {"role": "user", "content": f"feit {i}"}}),
                encoding="utf-8")
        # Sanity: normale sweep stopt bij max_transcripts=10 (default).
        s_normal = self.m.run_sweep(max_transcripts=10)
        self.assertEqual(s_normal["processed"], 10)

        # Reset watermark: verwijder .swept zodat alle 12 opnieuw pending zijn.
        swept = tdir / ".swept"
        if swept.exists():
            swept.unlink()

        # --all: ALLE 12 moeten verwerkt worden, ongeacht max_transcripts.
        s_all = self.m.run_sweep(max_transcripts=10, ignore_watermark=True)
        self.assertEqual(s_all["processed"], 12,
                         f"ignore_watermark=True moet alle 12 verwerken, got {s_all['processed']}")

    def test_sweep_runs_maintenance(self):
        # na een normale sweep moet de summary de onderhouds-tellers bevatten
        s = self.m.run_sweep()
        for key in ("superseded", "rechecked_retracted", "promote_marked"):
            self.assertIn(key, s)

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

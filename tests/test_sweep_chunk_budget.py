"""How much of a session survives capture, and what bounds one sweep run.

The old caps (6 chunks, 20 memories per transcript) were set when a chunk cost
30-56 s, because the judge model thought before it answered (TASK-143). Measured
after that fix, over four long transcripts and 120 real extractor calls:

    unique from chunk 1-6 : 101 candidates
    unique from chunk 7+  : 361 candidates  = 78% of all unique knowledge
    duplicates            : 4 of 466 = 0.9%

So the premise behind the cap -- later chunks repeat what the early ones said --
is false. What the sweep discarded was knowledge, not repetition.

Two guards live here. The caps must stay well above the old six, and a run must
stay bounded in total work: the sweep is detached but shares one GPU with the
embedding model that serves the retrieval hot path, so an unbounded run would
starve recall for as long as it lasts.
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

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "memory-sweep.py"
sys.path.insert(0, str(REPO / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("memory_sweep_budget", str(SCRIPT))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class ChunkBudgetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-budget-"))
        self.vault = self.tmp / "vault"
        (self.vault / "01-raw" / "transcripts").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = _load()
        # `self.m` is een VERSE kopie van memory-sweep, maar `self.m._extract`
        # is de GEDEELDE module uit sys.modules. De tests hieronder hangen daar
        # een stub in die altijd [] teruggeeft, en zonder deze restore erft de
        # rest van de suite een extractor die niets meer vindt -- wat er precies
        # uitziet als een lege extract in plaats van als een lekkende test.
        self._orig_extract = self.m._extract.extract_candidates
        self.addCleanup(lambda: setattr(self.m._extract, "extract_candidates",
                                        self._orig_extract))

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _transcript(self, name: str, chunks: int):
        """A transcript long enough to need more than one chunk."""
        block = "x" * 5800
        lines = [json.dumps({"message": {"role": "user",
                                         "content": [{"type": "text", "text": block}]}})
                 for _ in range(chunks)]
        p = self.vault / "01-raw" / "transcripts" / name
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    def test_the_caps_are_no_longer_set_for_a_model_that_thought_first(self):
        """6 and 20 were a cost decision, and that cost fell by a factor of ten."""
        self.assertGreaterEqual(self.m.MAX_CHUNKS, 30)
        self.assertGreaterEqual(self.m.MAX_MEMORIES_PER_TRANSCRIPT, 40)

    def test_a_run_is_bounded_in_total_chunks(self):
        """Without a ceiling, ten long transcripts is 40 minutes of GPU."""
        self.assertGreater(self.m.CHUNK_BUDGET, self.m.MAX_CHUNKS)
        self.assertLessEqual(self.m.CHUNK_BUDGET, 400)

    def test_the_budget_stops_between_transcripts_not_inside_one(self):
        """A half-read transcript would be marked swept and lose the rest.

        The watermark is append-only, so a transcript that is cut short is gone
        for good. The budget therefore only ever decides whether to START one.
        """
        for i in range(4):
            self._transcript(f"2026-08-12-t{i}.jsonl", 6)
        seen = []
        self.m._extract.extract_candidates = lambda text, max_n=8: seen.append(text) or []
        self.m._model_reachable = lambda: True
        s = self.m.run_sweep(max_chunks=6, chunk_budget=12)

        self.assertTrue(s["budget_reached"], "budget had moeten afkappen")
        self.assertEqual(s["chunks_read"] % 6, 0,
                         "afgekapt midden in een transcript in plaats van ertussen")
        self.assertEqual(s["processed"], 2)
        import _sweepstate as ss
        self.assertEqual(len(ss.pending()), 2, "de rest moet pending blijven")

    def test_all_ignores_both_the_cap_and_the_budget(self):
        """--all promises the whole archive; a silent cap would break that."""
        self._transcript("2026-08-12-long.jsonl", 9)
        seen = []
        self.m._extract.extract_candidates = lambda text, max_n=8: seen.append(text) or []
        self.m._model_reachable = lambda: True
        s = self.m.run_sweep(max_chunks=2, chunk_budget=1, ignore_watermark=True)
        self.assertFalse(s["budget_reached"])
        self.assertGreaterEqual(len(seen), 9)

    def test_skipped_chunks_are_reported(self):
        """"5 memories written" must not hide "and 300 chunks ignored"."""
        self._transcript("2026-08-12-long.jsonl", 10)
        self.m._extract.extract_candidates = lambda text, max_n=8: []
        self.m._model_reachable = lambda: True
        s = self.m.run_sweep(max_chunks=3)
        self.assertEqual(s["chunks_read"], 3)
        self.assertEqual(s["chunks_skipped"], 7)


if __name__ == "__main__":
    unittest.main()


class SweepCliTest(unittest.TestCase):
    """The CLI is how the sweep actually starts: sweep-launch.py spawns it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-cli-"))
        (self.tmp / "01-raw" / "transcripts").mkdir(parents=True)
        (self.tmp / "09-memory").mkdir(parents=True)
        (self.tmp / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        self.m = _load()

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_help_does_not_start_a_sweep(self):
        """argv is hand-parsed, so --help fell through and swept the vault.

        Asking a script what it does must never be a write operation.
        """
        called = []
        self.m.run_sweep = lambda *a, **k: called.append(k) or {"enabled": True}
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.m.main(["--help"])
        self.assertEqual(rc, 0)
        self.assertEqual(called, [], "--help mag geen sweep starten")
        self.assertIn("Usage:", buf.getvalue())

    def test_the_cli_passes_the_measured_memory_cap(self):
        """main() hardcoded 20 and so silently overrode the module default.

        The constant was raised to 60 on measured evidence; a CLI that keeps
        passing 20 means the change never reaches production, because
        sweep-launch.py starts the sweep through exactly this path.
        """
        # De echte samenvatting draagt alle tellers; de stub ook, anders
        # meet de test de printregel in plaats van de argumenten.
        summary = {"enabled": True, "processed": 0, "written": 0, "current": 0,
                   "unverified": 0, "duplicates": 0, "reconcile_noop": 0,
                   "reconciled_superseded": 0, "expired": 0, "errors": 0}
        seen = {}
        self.m.run_sweep = lambda *a, **k: seen.update(k) or summary
        self.m.main([])
        self.assertEqual(seen["max_memories_per_transcript"],
                         self.m.MAX_MEMORIES_PER_TRANSCRIPT)

    def test_an_explicit_flag_still_wins(self):
        # De echte samenvatting draagt alle tellers; de stub ook, anders
        # meet de test de printregel in plaats van de argumenten.
        summary = {"enabled": True, "processed": 0, "written": 0, "current": 0,
                   "unverified": 0, "duplicates": 0, "reconcile_noop": 0,
                   "reconciled_superseded": 0, "expired": 0, "errors": 0}
        seen = {}
        self.m.run_sweep = lambda *a, **k: seen.update(k) or summary
        self.m.main(["--max-per-transcript", "5"])
        self.assertEqual(seen["max_memories_per_transcript"], 5)

"""A NOOP throws a memory away and used to leave no trace of what it was.

Of the three reconcile actions, NOOP is the only one where the candidate is
never written. The heartbeat counts how OFTEN; nothing said WHAT. That is the
same shape as TASK-150 one step earlier in the pipeline, except worse: there
the memory existed on disk and could be reopened, here it never reaches disk at
all.

It matters because NOOP is exactly the action models get wrong. Measured on 20
unrelated pairs, the old prompt answered NOOP 25% of the time with reasons that
amounted to "these are unrelated" -- the definition of ADD. The prompt fix took
that to 0%, but the mechanism that made the loss invisible was untouched, so a
future prompt or model can bring it back silently (TASK-155).
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
import _reconcile  # noqa: E402


class DiscardLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-noop-"))
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

    def test_a_discard_records_what_was_thrown_away(self):
        _memory.log_discard("Judge model", "The judge runs on qwen3.5:4b.",
                            covered_by="2026-01-01-judge", reason="already covered",
                            prompt_version=2)
        rows = _memory.recent_discards()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Judge model")
        self.assertIn("qwen3.5:4b", rows[0]["body"])
        self.assertEqual(rows[0]["covered_by"], "2026-01-01-judge")
        self.assertEqual(rows[0]["prompt_version"], 2)

    def test_newest_first(self):
        for i in range(3):
            _memory.log_discard(f"K{i}", "body")
        self.assertEqual([r["title"] for r in _memory.recent_discards()],
                         ["K2", "K1", "K0"])

    def test_an_empty_covering_path_is_recorded_as_empty(self):
        """Raised in review as `Path("").stem` yielding ".". Measured: it does not.

        `Path("").stem` and `Path(".").stem` are both `""`, so the empty case
        already lands correctly. Pinning it here rather than adding a guard,
        because the concern was reasonable even though the premise was wrong,
        and "correct by accident" is one refactor away from "wrong".
        """
        self.assertEqual(Path("").stem, "")
        self.assertEqual(Path(".").stem, "")
        _memory.log_discard("K", "body", covered_by=Path("").stem)
        self.assertEqual(_memory.recent_discards()[0]["covered_by"], "")

    def test_a_broken_log_never_blocks_the_sweep(self):
        """A record, never a gate: capture must not depend on bookkeeping."""
        (self.tmp / ".claude" / _memory.DISCARD_LOG).mkdir()
        _memory.log_discard("K", "body")  # must not raise
        self.assertEqual(_memory.recent_discards(), [])

    def test_the_log_is_bounded(self):
        """An --all rebuild over hundreds of transcripts must not fill a disk.

        The closure log has no such problem, because closures are rare. NOOPs
        are not: every re-capture of covered knowledge is one.
        """
        _memory.DISCARD_LOG_MAX_LINES = 50
        try:
            for i in range(200):
                _memory.log_discard(f"K{i}", "body")
            log = self.tmp / ".claude" / _memory.DISCARD_LOG
            lines = log.read_text(encoding="utf-8").strip().splitlines()
            self.assertLessEqual(len(lines), 63,  # 50 * 1.25, the trim slack
                                 "the log kept growing without bound")
            # The NEWEST entries are the ones that survive.
            self.assertIn("K199", lines[-1])
        finally:
            _memory.DISCARD_LOG_MAX_LINES = 2000

    def test_a_trimmed_log_is_still_valid_json_lines(self):
        _memory.DISCARD_LOG_MAX_LINES = 10
        try:
            for i in range(60):
                _memory.log_discard(f"K{i}", "body")
            for row in _memory.recent_discards(limit=100):
                self.assertIn("title", row)
        finally:
            _memory.DISCARD_LOG_MAX_LINES = 2000


class ReconcileReportsTheCoveringMemoryTest(unittest.TestCase):
    """Without knowing WHICH memory covered it, the record cannot be judged."""

    def _item(self, path, status="current"):
        return {"path": path, "body": "existing", "vec": [1.0],
                "status": status, "valid_from": "2026-01-01",
                "volatility": "state"}

    def test_noop_names_the_covering_memory(self):
        r = _reconcile.reconcile("new", "2026-08-13", [1.0],
                                 [self._item("/vault/09-memory/a.md")],
                                 judge_fn=lambda n, o: "NOOP",
                                 new_volatility="state")
        self.assertEqual(r["action"], "NOOP")
        self.assertEqual(r["covered_by"], "/vault/09-memory/a.md")

    def test_an_add_carries_the_field_too_so_callers_need_no_special_case(self):
        r = _reconcile.reconcile("new", "2026-08-13", [1.0], [],
                                 judge_fn=lambda n, o: "ADD",
                                 new_volatility="state")
        self.assertEqual(r["covered_by"], "")

    def test_an_event_candidate_also_carries_it(self):
        r = _reconcile.reconcile("new", "2026-08-13", [1.0],
                                 [self._item("/vault/09-memory/a.md")],
                                 judge_fn=lambda n, o: "NOOP",
                                 new_volatility="event")
        self.assertEqual(r["action"], "ADD")
        self.assertEqual(r["covered_by"], "")


class SweepWritesTheDiscardTest(unittest.TestCase):
    """End to end: the sweep is where a NOOP actually discards something."""

    def setUp(self):
        import importlib.util
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-noopsweep-"))
        self.vault = self.tmp / "vault"
        (self.vault / "01-raw" / "transcripts").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        (self.vault / "01-raw" / "transcripts" / "2026-06-25-s.jsonl").write_text(
            json.dumps({"type": "user",
                        "message": {"role": "user", "content": "iets"}}),
            encoding="utf-8")
        spec = importlib.util.spec_from_file_location(
            "memory_sweep_noop", str(SCRIPTS / "memory-sweep.py"))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

        import _embeddings as emb
        import _extract
        import _judge
        import _llm
        self._restore = [
            (_extract, "extract_candidates", _extract.extract_candidates),
            (_judge, "judge", _judge.judge),
            (emb, "embed", emb.embed),
            (emb, "get_cached", emb.get_cached),
            (_llm, "generate", _llm.generate),
            (_reconcile, "judge_reconcile", _reconcile.judge_reconcile),
        ]
        for mod, naam, orig in self._restore:
            self.addCleanup(lambda m=mod, n=naam, o=orig: setattr(m, n, o))
        _llm.generate = lambda *a, **k: "ok"
        _extract.extract_candidates = lambda text, max_n=8: [
            {"title": "Weggegooid", "body": "de judge draait op qwen3.5:4b",
             "volatility": "state"}]
        _judge.judge = lambda cand, context="": {"verdict": "current", "reason": "ok"}
        emb.embed = lambda text, timeout=30.0: [0.9, 0.4358899, 0.0]
        emb.get_cached = lambda f, cache, recompute=True: [1.0, 0.0, 0.0]
        _reconcile.judge_reconcile = lambda new, old: "NOOP"

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_sweep_records_the_candidate_it_did_not_write(self):
        existing = _memory.write("Bestaand", "iets bestaands", status="current",
                                 created="2026-01-01", volatility="state")
        summary = self.m.run_sweep()
        self.assertGreaterEqual(summary.get("reconcile_noop", 0), 1)
        self.assertEqual(summary.get("written", 0), 0)

        rows = _memory.recent_discards()
        self.assertEqual(len(rows), 1, "de weggegooide kandidaat is niet vastgelegd")
        self.assertEqual(rows[0]["title"], "Weggegooid")
        self.assertIn("qwen3.5:4b", rows[0]["body"])
        self.assertEqual(rows[0]["covered_by"], existing.stem)
        self.assertIsNotNone(rows[0]["prompt_version"])


if __name__ == "__main__":
    unittest.main()

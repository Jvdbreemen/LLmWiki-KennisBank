"""Tests voor scripts/_usage.py en kb-usage-scan.py - de retrieval-feedbackloop.

Sqlite naar temp-vault; geen model, geen hooks.
"""
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

from tests._loader import load_script


class UsageCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = self.tmp.name
        self.addCleanup(self._restore)
        import _usage
        self.u = _usage

    def _restore(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved


class TestUsageStore(UsageCase):
    def test_log_injected_and_pending(self):
        n = self.u.log_injected(["artikel-a", "artikel-b"], session_id="s1",
                                today="2026-07-01")
        self.assertEqual(n, 2)
        self.assertEqual(sorted(self.u.pending_for("s1")), ["artikel-a", "artikel-b"])

    def test_mark_used_sets_last_used(self):
        self.u.mark_used(["artikel-a"], today="2026-07-01")
        self.assertEqual(self.u.last_used_of("artikel-a"), "2026-07-01")
        self.assertEqual(self.u.last_used_of("onbekend"), "")

    def test_counters_accumulate(self):
        self.u.log_injected(["a"], today="2026-07-01")
        self.u.log_injected(["a"], today="2026-07-02")
        self.u.mark_used(["a"], today="2026-07-02")
        import sqlite3
        from contextlib import closing
        # closing() expliciet: op Windows houdt een niet-gesloten connectie
        # het db-bestand op slot en faalt de tempdir-cleanup.
        with closing(sqlite3.connect(str(self.u.db_path()))) as conn:
            row = conn.execute(
                "SELECT injected, used, last_injected FROM usage WHERE stem='a'").fetchone()
        self.assertEqual(row, (2, 1, "2026-07-02"))

    def test_clear_pending(self):
        self.u.log_injected(["a"], session_id="s1")
        self.u.clear_pending("s1")
        self.assertEqual(self.u.pending_for("s1"), [])

    def test_all_last_used(self):
        self.u.mark_used(["a"], today="2026-07-01")
        self.u.log_injected(["b"], today="2026-07-01")  # wel geinjecteerd, nooit gebruikt
        lu = self.u.all_last_used()
        self.assertEqual(lu.get("a"), "2026-07-01")
        self.assertNotIn("b", lu)

    def test_toggle_off_disables(self):
        (Path(self.tmp.name) / "kennisbank-settings.json").write_text(
            json.dumps({"usage_telemetry": False}), encoding="utf-8")
        self.assertEqual(self.u.log_injected(["a"], session_id="s1"), 0)
        self.assertEqual(self.u.pending_for("s1"), [])


class TestUsageScan(UsageCase):
    def setUp(self):
        super().setUp()
        self.scan_mod = load_script("kb-usage-scan.py")

    def _transcript(self, lines) -> Path:
        p = Path(self.tmp.name) / "t.jsonl"
        p.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
        return p

    def test_used_stem_in_tool_use_input_marked(self):
        self.u.log_injected(["artikel-a", "artikel-b"], session_id="s1")
        t = self._transcript([
            {"type": "user", "message": {"content": "vraag over artikel-b (injectie zelf)"}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "input": {"file_path": "02-wiki/artikel-a.md"}}]}},
        ])
        n = self.scan_mod.scan("s1", t)
        self.assertEqual(n, 1)
        self.assertTrue(self.u.last_used_of("artikel-a"))
        # artikel-b stond alleen in het user-bericht (de injectie) -> niet gebruikt
        self.assertEqual(self.u.last_used_of("artikel-b"), "")

    def test_prose_only_mention_does_not_count_as_use(self):
        self.u.log_injected(["artikel-a"], session_id="s1")
        t = self._transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Ik noem artikel-a maar raadpleeg het niet."}]}},
        ])
        n = self.scan_mod.scan("s1", t)
        self.assertEqual(n, 0)
        self.assertEqual(self.u.last_used_of("artikel-a"), "")

    def test_tool_use_input_counts(self):
        self.u.log_injected(["artikel-a"], session_id="s1")
        t = self._transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "input": {"file_path": "02-wiki/artikel-a.md"}}]}},
        ])
        self.assertEqual(self.scan_mod.scan("s1", t), 1)

    def test_pending_cleared_after_scan(self):
        self.u.log_injected(["artikel-a"], session_id="s1")
        t = self._transcript([{"type": "assistant", "message": {"content": []}}])
        self.scan_mod.scan("s1", t)
        self.assertEqual(self.u.pending_for("s1"), [])

    def test_missing_transcript_failsoft(self):
        self.u.log_injected(["artikel-a"], session_id="s1")
        n = self.scan_mod.scan("s1", Path(self.tmp.name) / "bestaat-niet.jsonl")
        self.assertEqual(n, 0)

    def test_no_pending_is_noop(self):
        t = self._transcript([{"type": "assistant", "message": {"content": []}}])
        self.assertEqual(self.scan_mod.scan("s-leeg", t), 0)


class TestFrozenGuard(UsageCase):
    """KB_USAGE_DISABLE (kb-eval --frozen): een eval-run mag nooit als
    gebruik meetellen, anders vervuilt de meting het signaal dat ze meet."""

    def setUp(self):
        super().setUp()
        self._saved_disable = os.environ.pop("KB_USAGE_DISABLE", None)
        self.addCleanup(self._restore_disable)

    def _restore_disable(self):
        if self._saved_disable is None:
            os.environ.pop("KB_USAGE_DISABLE", None)
        else:
            os.environ["KB_USAGE_DISABLE"] = self._saved_disable

    def test_env_var_disables_all_writers(self):
        os.environ["KB_USAGE_DISABLE"] = "1"
        self.assertFalse(self.u.enabled())
        self.assertEqual(self.u.log_injected(["a"], session_id="s1"), 0)
        self.assertEqual(self.u.mark_used(["a"]), 0)
        self.assertEqual(self.u.mark_noise(["a"]), 0)
        self.assertEqual(self.u.pending_for("s1"), [])

    def test_unset_env_var_keeps_default_on(self):
        self.assertTrue(self.u.enabled())

    def _run_eval_main(self, eval_mod):
        # --set naar een niet-bestaand pad: main() faalt netjes (exit 1) nadat
        # de guard gezet is, zonder model of index nodig te hebben.
        argv_saved = sys.argv
        sys.argv = ["kb-eval.py",
                    "--set", str(Path(self.tmp.name) / "geen-set.json")]
        try:
            return eval_mod.main()
        finally:
            sys.argv = argv_saved

    def test_kb_eval_freezes_during_run_and_restores_after(self):
        # Geen vlag: een eval mag NOOIT als gebruik meetellen, dus de guard is
        # onvoorwaardelijk actief TIJDENS de run — en na afloop hersteld, zodat
        # ook een in-process aanroep het normale leergedrag teruggeeft.
        eval_mod = load_script("kb-eval.py")
        captured = {}
        orig = eval_mod._run_jobs

        def spy(args):
            captured["during"] = os.environ.get("KB_USAGE_DISABLE")
            return orig(args)

        eval_mod._run_jobs = spy
        try:
            self._run_eval_main(eval_mod)
        finally:
            eval_mod._run_jobs = orig
        self.assertEqual(captured.get("during"), "1")
        self.assertNotIn("KB_USAGE_DISABLE", os.environ)
        self.assertTrue(self.u.enabled())

    def test_kb_eval_preserves_preexisting_disable(self):
        # Stond de var al (bewust) in de omgeving, dan laat de eval hem staan:
        # herstellen betekent "vorige staat terug", niet "altijd aan".
        eval_mod = load_script("kb-eval.py")
        os.environ["KB_USAGE_DISABLE"] = "handmatig"
        self._run_eval_main(eval_mod)
        self.assertEqual(os.environ.get("KB_USAGE_DISABLE"), "handmatig")


if __name__ == "__main__":
    unittest.main()

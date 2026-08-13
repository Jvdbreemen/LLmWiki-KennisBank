"""A zero must mean "nothing to do", never "this crashed".

Every maintenance pass ran inside `try: ... except Exception: 0`. A timeout, an
ImportError and an idle run all wrote the same line in the heartbeat, so the
sweep reported `superseded: 0, rechecked_retracted: 0, promote_marked: 0,
exact_duplicates_closed: 0` while nothing had run at all — and that looked
exactly like a quiet vault.

It is the same failure shape as TASK-143 one level up: there the seam swallowed a
model that never answered, here the orchestrator swallowed a pass that never ran.
It was only found because `--help` accidentally started a sweep that spent ten
minutes without writing anything.

The counters stay integers, because readers depend on that. The reason is
recorded beside them and counted into `errors`, which memory-notify already
surfaces at the next session start.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "memory_sweep_passes", str(REPO / "scripts" / "memory-sweep.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class PassFailureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-passes-"))
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

    def test_an_idle_pass_leaves_no_trace(self):
        s = {"errors": 0}
        self.m._run_pass(s, "superseded", lambda: 0)
        self.assertEqual(s["superseded"], 0)
        self.assertEqual(s.get("pass_errors", {}), {})
        self.assertEqual(s["errors"], 0, "niets te doen is geen fout")

    def test_a_crashed_pass_says_so(self):
        s = {"errors": 0}
        self.m._run_pass(s, "superseded", lambda: 1 / 0)
        self.assertEqual(s["superseded"], 0, "de teller blijft een int voor lezers")
        self.assertIn("superseded", s["pass_errors"])
        self.assertIn("ZeroDivisionError", s["pass_errors"]["superseded"])

    def test_a_crash_counts_as_an_error_so_the_user_hears_about_it(self):
        """memory-notify reports `errors > 0` at session start already."""
        s = {"errors": 0}
        self.m._run_pass(s, "promote_marked", lambda: (_ for _ in ()).throw(TimeoutError("op")))
        self.assertEqual(s["errors"], 1)

    def test_a_working_pass_reports_its_count(self):
        """The inverse: where work exists, the counter is not zero."""
        s = {"errors": 0}
        self.m._run_pass(s, "superseded", lambda: 7)
        self.assertEqual(s["superseded"], 7)
        self.assertEqual(s.get("pass_errors", {}), {})

    def test_one_failing_pass_does_not_stop_the_others(self):
        s = {"errors": 0}
        self.m._run_pass(s, "exact_duplicates_closed", lambda: 2)
        self.m._run_pass(s, "superseded", lambda: 1 / 0)
        self.m._run_pass(s, "rechecked_retracted", lambda: 3)
        self.assertEqual(s["exact_duplicates_closed"], 2)
        self.assertEqual(s["rechecked_retracted"], 3)
        self.assertEqual(list(s["pass_errors"]), ["superseded"])

    def test_the_summary_always_carries_the_field(self):
        """An absent key would make "no failures" and "old format" the same.

        `_settings` is a module shared through sys.modules, so patching `.get`
        on it reaches every other test in the run. Restore it, or the next
        suite sees memory_capture=True when it asked for False -- which is how
        a neighbouring test started writing memories it had switched off.
        """
        self.m._model_reachable = lambda: True
        saved = self.m._settings.get
        self.addCleanup(lambda: setattr(self.m._settings, "get", saved))
        self.m._settings.get = lambda key, default=None: True
        s = self.m.run_sweep()
        self.assertIn("pass_errors", s)


if __name__ == "__main__":
    unittest.main()

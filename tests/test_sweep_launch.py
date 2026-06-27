"""Tests voor scripts/sweep-launch.py - lockfile + gating (geen echte spawn)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("sweep_launch", str(SCRIPTS_DIR / "sweep-launch.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class SweepLaunchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-launch-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = _load()

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_acquire_then_second_fails(self):
        self.assertTrue(self.m.acquire_lock())
        self.assertFalse(self.m.acquire_lock())  # single-flight
        self.m.release_lock()
        self.assertTrue(self.m.acquire_lock())

    def test_gated_off_skips_spawn(self):
        (self.vault / "kennisbank-settings.json").write_text(
            json.dumps({"memory_capture": False}), encoding="utf-8")
        spawned = []
        self.m._spawn_detached = lambda script, *a: spawned.append(script)
        self.m.main()
        self.assertEqual(spawned, [])  # niets gespawnd als gated off

    def test_main_spawns_when_enabled(self):
        spawned = []
        self.m._spawn_detached = lambda script, *a: spawned.append(Path(script).name)
        self.m.main()
        # sweep eerst, dan index
        self.assertIn("memory-sweep.py", spawned)
        self.assertIn("build-kb-index.py", spawned)
        self.assertLess(spawned.index("memory-sweep.py"), spawned.index("build-kb-index.py"))


if __name__ == "__main__":
    unittest.main()

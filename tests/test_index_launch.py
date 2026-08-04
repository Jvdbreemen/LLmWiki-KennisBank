"""Tests voor scripts/index-launch.py — het gedetachte indexonderhoud (TASK-63)."""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from tests._loader import load_script


class IndexLaunchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-idxlaunch-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = load_script("index-launch.py")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- single flight ---

    def test_second_launch_does_not_spawn_a_second_worker(self):
        spawned = []
        self.m.spawn_worker = lambda token: spawned.append(token)
        self.assertEqual(self.m.main([]), 0)
        self.assertEqual(self.m.main([]), 0)
        self.assertEqual(len(spawned), 1,
                         "tweede sessie startte een tweede worker; twee processen "
                         "zouden dezelfde index schrijven")

    def test_lock_is_released_when_spawning_fails(self):
        def boom(_token):
            raise OSError("geen proces")
        self.m.spawn_worker = boom
        self.m.main([])
        self.assertFalse(self.m._lock_path().exists(),
                         "lock bleef staan terwijl er niets draait")

    # --- staleness ---

    def test_stale_lock_is_reclaimed(self):
        self.assertTrue(self.m.acquire_lock())
        lock = self.m._lock_path()
        old = time.time() - self.m.STALE_SEC - 10
        os.utime(lock, (old, old))
        self.assertTrue(self.m.is_stale(lock))
        self.assertTrue(self.m.acquire_lock(), "verweesde lock niet heroverd")

    def test_future_mtime_counts_as_stale(self):
        """Klokverzetting mag het onderhoud niet permanent stilzetten."""
        self.assertTrue(self.m.acquire_lock())
        lock = self.m._lock_path()
        future = time.time() + 10_000
        os.utime(lock, (future, future))
        self.assertTrue(self.m.is_stale(lock))

    def test_recent_lock_with_dead_pid_counts_as_stale(self):
        """Een gecrashte worker mag geen uur lang onderhoud blokkeren."""
        lock = self.m._lock_path()
        lock.write_text("2147483647\nlegacy-token\n", encoding="ascii")
        self.assertTrue(self.m.is_stale(lock))

    def test_stale_window_exceeds_the_worst_case_run(self):
        """Anders kan een tweede sessie een NOG DRAAIENDE worker verweesd noemen.

        Niet geparametriseerd op de constante zelf: dan zou de test bij elke
        waarde slagen en niets toetsen.
        """
        worst_case = self.m.PER_JOB_TIMEOUT * len(self.m.JOBS)
        self.assertGreater(self.m.STALE_SEC, worst_case)

    # --- volgorde en gating ---

    def test_jobs_run_sequentially_with_the_sweep_first(self):
        order = []

        def runner(path, timeout):
            order.append(Path(path).name)
            return 0

        self.m.run_jobs(runner=runner)
        self.assertEqual(order[0], "memory-sweep.py",
                         "de sweep flipt statussen en moet vóór de index draaien")
        self.assertEqual(order, [s for s, _ in self.m.JOBS])

    def test_a_failing_job_does_not_stop_the_rest(self):
        seen = []

        def runner(path, timeout):
            seen.append(Path(path).name)
            if Path(path).name == "memory-sweep.py":
                raise RuntimeError("sweep stuk")
            return 0

        results = self.m.run_jobs(runner=runner)
        self.assertEqual(len(seen), len(self.m.JOBS))
        self.assertIn(("memory-sweep.py", None), results)

    def test_worker_mode_releases_the_lock(self):
        self.assertTrue(self.m.acquire_lock())
        token = self.m._lock_token(self.m._lock_path())
        self.assertIsNotNone(token)
        self.m.run_jobs = lambda runner=None: []
        self.m.main(["--worker", "--lock-token", token])
        self.assertFalse(self.m._lock_path().exists())

    def test_spawn_worker_hides_windows_console(self):
        calls = []
        original_popen = self.m.subprocess.Popen
        self.m.subprocess.Popen = lambda command, **kwargs: calls.append((command, kwargs))
        try:
            self.m.spawn_worker("test-token")
        finally:
            self.m.subprocess.Popen = original_popen

        self.assertEqual(len(calls), 1)
        command, kwargs = calls[0]
        self.assertEqual(command[-3:], ["--worker", "--lock-token", "test-token"])
        self.assertIs(kwargs["stdout"], self.m.subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], self.m.subprocess.DEVNULL)
        if os.name == "nt":
            self.assertEqual(kwargs["creationflags"], 0x00000008 | 0x08000000)
        else:
            self.assertTrue(kwargs["start_new_session"])


if __name__ == "__main__":
    unittest.main()

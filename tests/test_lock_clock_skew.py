"""A lock is not stale because the clock is coarser than the filesystem.

On Windows ``time.time()`` reads GetSystemTimeAsFileTime, resolution 15.625 ms,
while the filesystem stamps ``st_mtime`` from a finer clock. A file created
microseconds ago therefore measures as slightly IN THE FUTURE: 586 of 5000
samples on the target machine, up to +0.016 s. Every lock here used to read that
as clock skew and reclaim the lock, so single-flight held only ~88% of the time
and a run of the suite failed roughly one time in eight (TASK-140).

The tests stamp the skew explicitly instead of racing the clock: a real run
reproduces it about one call in eight, which is no regression guard at all.
Far-future stamps must still expire -- otherwise a genuine clock change parks
maintenance forever -- and those cases stay covered in test_sweep_launch.py and
test_index_launch.py.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script  # noqa: E402

#: Smaller than one tick of the Windows system clock, i.e. exactly the noise the
#: old check mistook for a clock change.
SKEW = 0.01


def _stamp_future(path: Path, delta: float = SKEW) -> None:
    t = time.time() + delta
    os.utime(str(path), (t, t))


class _VaultCase(unittest.TestCase):
    prefix = "kb-skew-"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix=self.prefix))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)


class SweepLaunchSkewTest(_VaultCase):
    def setUp(self):
        super().setUp()
        self.m = load_script("sweep-launch.py")

    def test_barely_future_lock_is_held_not_reclaimed(self):
        self.assertTrue(self.m.acquire_lock())
        _stamp_future(self.m._lock_path())
        self.assertFalse(self.m.is_stale(self.m._lock_path()))
        self.assertFalse(self.m.acquire_lock(), "single-flight gave the lock away")


class IndexLaunchSkewTest(_VaultCase):
    def setUp(self):
        super().setUp()
        self.m = load_script("index-launch.py")

    def test_barely_future_lock_is_held_not_reclaimed(self):
        self.assertTrue(self.m.acquire_lock())
        lock = self.m._lock_path()
        _stamp_future(lock)
        self.assertFalse(self.m.is_stale(lock))
        self.assertFalse(self.m.acquire_lock(), "two index builders could run at once")


class SessionStartSkewTest(_VaultCase):
    def setUp(self):
        super().setUp()
        self.m = load_script("kb-session-start.py")

    def test_barely_future_lock_is_held_not_reclaimed(self):
        lock = self.vault / ".claude" / ".kb-session-start.lock"
        self.assertTrue(self.m.acquire_lock(lock))
        _stamp_future(lock)
        self.assertFalse(self.m.acquire_lock(lock), "coordinator lock reclaimed itself")

    def test_far_future_lock_still_expires(self):
        """A real clock change must not park SessionStart maintenance forever."""
        lock = self.vault / ".claude" / ".kb-session-start.lock"
        self.assertTrue(self.m.acquire_lock(lock))
        _stamp_future(lock, self.m.LOCK_STALE_SECONDS + 60)
        self.assertTrue(self.m.acquire_lock(lock))


class WarmMarkerSkewTest(_VaultCase):
    prefix = "kb-skew-warm-"

    def test_marker_written_just_now_counts_as_running(self):
        """The marker path is patched rather than the module reloaded.

        _embeddings binds its cache path at import time, so pointing it at this
        vault would mean re-importing it -- and a re-imported module left in
        sys.modules outlives the test and its temp directory. That is the leak
        conftest.py exists to prevent, so patch the one function instead.
        """
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import _embeddings as emb

        marker = self.vault / ".claude" / ".embed-warm.marker"
        marker.write_text('{"pid": %d, "started_at": 0}\n' % os.getpid(), encoding="utf-8")
        _stamp_future(marker)
        saved = emb._warm_marker
        emb._warm_marker = lambda: marker
        try:
            self.assertTrue(emb.warm_in_progress(), "a live warm child read as finished")
        finally:
            emb._warm_marker = saved


if __name__ == "__main__":
    unittest.main()

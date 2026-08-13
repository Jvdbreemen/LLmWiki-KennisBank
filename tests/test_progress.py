"""A long job that says nothing cannot be told apart from a hung one.

`memory-sweep.py` once ran ten minutes without writing a byte, and a read-only
measurement over the corpus produced no output at all for longer than that —
both looked exactly like a crash from the outside. This helper exists so the
answer to "is it still doing something?" is visible while it happens, together
with an estimate extrapolated from the run so far (TASK-153).

Two properties matter more than the cosmetics: the helper must never break the
work it reports on, and it must stay silent where silence is the contract
(hooks, heartbeats, KB_NO_PROGRESS).
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _progress import Progress, format_duration  # noqa: E402


class _FakeTTY(io.StringIO):
    def isatty(self):
        return True


class DurationTest(unittest.TestCase):
    def test_reads_as_time_not_as_a_float(self):
        self.assertEqual(format_duration(45), "45s")
        self.assertEqual(format_duration(134), "2m14s")
        self.assertEqual(format_duration(3780), "1h03m")

    def test_nonsense_never_raises(self):
        self.assertEqual(format_duration("nope"), "?")


class RenderTest(unittest.TestCase):
    def test_the_line_carries_percent_bar_counts_and_elapsed(self):
        p = Progress(200, "documents", stream=io.StringIO())
        p.done = 50
        line = p.render_line()
        self.assertIn("documents", line)
        self.assertIn(" 25%", line)
        self.assertIn("50/200", line)
        self.assertIn("[#####", line)

    def test_an_estimate_appears_once_throughput_is_measurable(self):
        """The start time is moved back rather than waited out.

        `time.monotonic()` ticks every 15.6 ms on Windows, so a loop with no
        real work in it yields elapsed == 0.0, from which no throughput can be
        measured. That is exactly when an estimate is worthless too, so the
        silence is behaviour and not a bug -- but a test that relies on a
        running clock measures the clock instead of the estimate.
        """
        p = Progress(100, "x", stream=io.StringIO(), min_items_for_eta=3)
        p.started -= 10.0  # as if the run has been going for ten seconds
        p.done = 1
        self.assertNotIn("left", p.render_line(),
                         "an estimate from a single item is a guess, not an estimate")
        p.done = 50
        line = p.render_line()
        self.assertIn("left", line)
        # 50 items in 10s -> the remaining 50 take ~10s as well.
        self.assertIn("~10s left", line)

    def test_no_estimate_while_the_clock_has_not_moved(self):
        """With no time elapsed there is no throughput, so no estimate either."""
        p = Progress(100, "x", stream=io.StringIO(), min_items_for_eta=1)
        p.done = 50
        p.started = __import__("time").monotonic() + 1  # 'not started yet'
        self.assertNotIn("left", p.render_line())

    def test_an_unknown_total_counts_instead_of_inventing_a_percentage(self):
        p = Progress(None, "unknown", stream=io.StringIO())
        p.done = 7
        line = p.render_line()
        self.assertIn("7 done", line)
        self.assertNotIn("%", line)
        self.assertNotIn("left", line)


class OutputShapeTest(unittest.TestCase):
    def test_a_terminal_gets_one_rewritten_line(self):
        out = _FakeTTY()
        p = Progress(10, "t", stream=out)
        for _ in range(10):
            p._last_render = 0.0  # force a render; the interval would throttle it
            p.step()
        self.assertIn("\r", out.getvalue())

    def test_a_pipe_gets_whole_lines_and_far_fewer_of_them(self):
        """A log file made of thousands of carriage returns is not a log file."""
        out = io.StringIO()
        p = Progress(1000, "p", stream=out)
        for _ in range(1000):
            p.step()
        value = out.getvalue()
        self.assertNotIn("\r", value)
        # 5% steps: at most ~20 lines, not 1000.
        self.assertLessEqual(len(value.strip().splitlines()), 25)
        self.assertGreaterEqual(len(value.strip().splitlines()), 5)

    def test_close_reports_what_was_done_and_how_long_it_took(self):
        out = io.StringIO()
        with Progress(3, "reading memories", stream=out) as p:
            for _ in range(3):
                p.step()
        self.assertIn("reading memories: 3/3 in ", out.getvalue())


class SilenceTest(unittest.TestCase):
    def test_quiet_writes_nothing_at_all(self):
        out = io.StringIO()
        with Progress(5, "quiet", stream=out, quiet=True) as p:
            for _ in range(5):
                p.step()
        self.assertEqual(out.getvalue(), "")

    def test_the_environment_can_demand_silence(self):
        """Hooks and the heartbeat have a clean-output contract to keep."""
        saved = os.environ.get("KB_NO_PROGRESS")
        os.environ["KB_NO_PROGRESS"] = "1"
        self.addCleanup(lambda: os.environ.__setitem__("KB_NO_PROGRESS", saved)
                        if saved is not None else os.environ.pop("KB_NO_PROGRESS", None))
        out = io.StringIO()
        with Progress(5, "quiet", stream=out) as p:
            for _ in range(5):
                p.step()
        self.assertEqual(out.getvalue(), "")


class NeverBreaksTheCallerTest(unittest.TestCase):
    class _BrokenStream:
        def write(self, *_a, **_k):
            raise OSError("pipe closed")

        def flush(self):
            raise OSError("pipe closed")

        def isatty(self):
            return False

    def test_a_dead_stream_does_not_reach_the_caller(self):
        """A progress bar that kills the job it reports on is worse than none."""
        p = Progress(10, "broken", stream=self._BrokenStream())
        for _ in range(10):
            p.step()  # must not raise
        p.close()
        self.assertEqual(p.done, 10, "the work keeps counting, reporting or not")

    def test_the_counter_keeps_counting_after_the_stream_dies(self):
        p = Progress(None, "x", stream=self._BrokenStream())
        p.step(5)
        self.assertFalse(p.enabled)
        p.step(5)
        self.assertEqual(p.done, 10)


if __name__ == "__main__":
    unittest.main()

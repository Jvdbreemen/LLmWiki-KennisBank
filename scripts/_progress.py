#!/usr/bin/env python3
"""_progress.py - progress and an estimate for anything that takes a while.

Every heavy path in this repo stayed silent until it was done. A sweep that ran
ten minutes writing nothing, a current_items() reading 1500 memories, an index
build over 1800 documents: from the outside, indistinguishable from a hang.
That is the same class as TASK-143/148 one level down -- a silence you cannot
tell apart from a crash -- except that here it costs attention rather than
knowledge.

Usage:

    from _progress import Progress
    with Progress(len(files), "indexing documents") as p:
        for f in files:
            ...
            p.step()

Renders to stderr, so stdout stays usable for JSON and pipes:

    indexing documents  63% [############.......]  945/1501  1m12s, ~42s left

On a terminal one line is rewritten in place. In a pipe, a log or a background
job (no tty) whole lines are written, heavily throttled, so a log file does not
end up made of thousands of carriage returns.

Silence is available and stays the default where it belongs: KB_NO_PROGRESS=1
in the environment or quiet=True in the call. Hooks and the heartbeat stay
clean.

This module must NEVER let an error escape to its caller. A progress bar that
breaks the work it reports on is worse than no bar, so every render sits inside
a broad except.

Stdlib, no dependencies.
"""
from __future__ import annotations

import os
import sys
import time

#: Terminal: often enough to feel alive, not so often that it flickers.
TTY_INTERVAL_SECONDS = 0.25
#: No terminal: every line is a line in someone's log. Far quieter.
PIPE_INTERVAL_SECONDS = 10.0
#: ... and then only when something actually changed.
PIPE_MIN_PERCENT_STEP = 5

BAR_WIDTH = 20


def enabled_by_default() -> bool:
    """False when the environment explicitly asks for silence.

    Case-insensitive on purpose. People set environment variables as TRUE, True
    and yes as readily as 1, and a silence contract that only honours some of
    those spellings is not a contract. (The same case-sensitive comparison
    still sits in _llm.KB_LLM_THINK; that one only turns a feature on, so it
    fails towards the safe side rather than towards unexpected output.)
    """
    return os.environ.get("KB_NO_PROGRESS", "").strip().lower() not in ("1", "true", "yes")


def format_duration(seconds: float) -> str:
    """Readable duration: 45s, 2m14s, 1h03m. Never 3600.0 seconds."""
    try:
        s = int(max(0, round(seconds)))
    except Exception:
        return "?"
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


class Progress:
    """Progress reporter with an estimate from measured throughput.

    total=None or 0 means "unknown how many": no percentage and no bar, because
    an invented percentage is worse than none. The count and the elapsed time
    are still shown, so it stays visible that something is happening.
    """

    def __init__(self, total=None, label: str = "", stream=None,
                 quiet: bool = False, min_items_for_eta: int = 3):
        self.total = int(total) if total else None
        self.label = str(label or "")
        self.stream = stream if stream is not None else sys.stderr
        self.done = 0
        self.started = time.monotonic()
        self._last_render = 0.0
        self._last_percent = -1
        self._dirty = False  # is there a written line still to be terminated?
        self.min_items_for_eta = max(1, int(min_items_for_eta))
        self.enabled = bool(not quiet and enabled_by_default() and self._usable())
        self.is_tty = self._isatty()

    # -- internal helpers ---------------------------------------------------
    def _usable(self) -> bool:
        try:
            return self.stream is not None and hasattr(self.stream, "write")
        except Exception:
            return False

    def _isatty(self) -> bool:
        try:
            return bool(self.stream.isatty())
        except Exception:
            return False

    def _eta_seconds(self):
        """Estimate from what has been measured so far; None while that says nothing."""
        if not self.total or self.done < self.min_items_for_eta:
            return None
        elapsed = time.monotonic() - self.started
        if elapsed <= 0 or self.done <= 0:
            return None
        return (elapsed / self.done) * (self.total - self.done)

    def _should_render(self, percent) -> bool:
        now = time.monotonic()
        if self.is_tty:
            return (now - self._last_render) >= TTY_INTERVAL_SECONDS
        # Without a tty every line is a line in a log: only on a noticeable
        # jump OR after a long silence, so that a slow step still shows
        # something is happening.
        if percent is not None and percent - self._last_percent >= PIPE_MIN_PERCENT_STEP:
            return True
        return (now - self._last_render) >= PIPE_INTERVAL_SECONDS

    def render_line(self, note: str = "") -> str:
        """The line as it is shown. Separate so a test can read it."""
        elapsed = time.monotonic() - self.started
        parts = []
        if self.label:
            parts.append(self.label)
        if self.total:
            percent = min(100, int(self.done * 100 / self.total))
            filled = int(BAR_WIDTH * self.done / self.total)
            bar = "#" * min(BAR_WIDTH, filled) + "." * max(0, BAR_WIDTH - filled)
            parts.append(f"{percent:3d}% [{bar}]")
            parts.append(f"{self.done}/{self.total}")
        else:
            parts.append(f"{self.done} done")
        eta = self._eta_seconds()
        tail = format_duration(elapsed)
        if eta is not None:
            tail += f", ~{format_duration(eta)} left"
        parts.append(tail)
        if note:
            parts.append(str(note))
        return "  ".join(parts)

    # -- public API ---------------------------------------------------------
    def step(self, n: int = 1, note: str = "") -> None:
        """Report n processed items. Renders at most as often as the interval allows."""
        try:
            self.done += int(n)
            if not self.enabled:
                return
            percent = (min(100, int(self.done * 100 / self.total))
                       if self.total else None)
            if not self._should_render(percent):
                return
            self._write(self.render_line(note))
            self._last_render = time.monotonic()
            if percent is not None:
                self._last_percent = percent
        except Exception:
            # A broken bar must not touch the work. From here on, stay silent
            # entirely rather than retrying on every single step.
            self.enabled = False

    def note(self, text: str) -> None:
        """A one-off remark in between, on its own line."""
        try:
            if not self.enabled:
                return
            self._finish_line()
            self.stream.write(f"{text}\n")
            self.stream.flush()
        except Exception:
            self.enabled = False

    def close(self, note: str = "") -> None:
        """Finish with a final line: what was done and how long it took."""
        try:
            if not self.enabled:
                return
            elapsed = format_duration(time.monotonic() - self.started)
            counted = f"{self.done}/{self.total}" if self.total else f"{self.done}"
            tail = f" {note}" if note else ""
            self._finish_line()
            self.stream.write(f"{self.label or 'done'}: {counted} in {elapsed}{tail}\n")
            self.stream.flush()
        except Exception:
            pass
        finally:
            self.enabled = False

    def _write(self, line: str) -> None:
        if self.is_tty:
            # \r + clear to end of line: no leftovers from a longer previous line.
            self.stream.write("\r\033[K" + line)
            self._dirty = True
        else:
            self.stream.write(line + "\n")
        self.stream.flush()

    def _finish_line(self) -> None:
        """Terminate a pending \\r line so the next output does not overwrite it."""
        if self._dirty:
            self.stream.write("\n")
            self._dirty = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

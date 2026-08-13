#!/usr/bin/env python3
"""_progress.py - voortgang en een schatting voor alles wat langer dan even duurt.

Elk zwaar pad in deze repo zweeg tot het klaar was. Een sweep die tien minuten
draait en niets schrijft, een current_items() die 1500 memories inleest, een
index-build over 1800 documenten: van buiten niet te onderscheiden van een hang.
Dat is dezelfde klasse als TASK-143/148 een laag lager -- een stilte die je niet
uit elkaar kunt houden van een crash -- alleen kost hij hier aandacht in plaats
van kennis.

Gebruik:

    from _progress import Progress
    with Progress(len(files), "documenten indexeren") as p:
        for f in files:
            ...
            p.step()

Rendert naar stderr, zodat stdout bruikbaar blijft voor JSON en pipes:

    documenten indexeren  63% [############.......]  945/1501  1m12s, nog ~42s

Op een terminal wordt één regel overschreven. In een pipe, log of
achtergrondjob (geen tty) worden losse regels geschreven, flink getemperd,
zodat een logbestand niet uit duizenden carriage returns bestaat.

Stil houden kan en blijft de default waar dat hoort: KB_NO_PROGRESS=1 in de
omgeving of quiet=True in de aanroep. Hooks en de heartbeat blijven schoon.

Deze module mag NOOIT een fout naar zijn aanroeper laten ontsnappen. Een
voortgangsbalk die het werk sloopt waarover hij rapporteert is erger dan geen
balk; elke render zit daarom in een brede except.

Stdlib, geen dependencies.
"""
from __future__ import annotations

import os
import sys
import time

#: Terminal: vaak genoeg om te leven, niet zo vaak dat het flikkert.
TTY_INTERVAL_SECONDS = 0.25
#: Geen terminal: elke regel is een regel in iemands log. Veel rustiger.
PIPE_INTERVAL_SECONDS = 10.0
#: ... en dan nog alleen als er echt iets veranderd is.
PIPE_MIN_PERCENT_STEP = 5

BAR_WIDTH = 20


def enabled_by_default() -> bool:
    """False als de omgeving expliciet om stilte vraagt."""
    return os.environ.get("KB_NO_PROGRESS", "").strip() not in ("1", "true", "yes")


def format_duration(seconds: float) -> str:
    """Leesbare duur: 45s, 2m14s, 1u03m. Geen 3600.0 seconds."""
    try:
        s = int(max(0, round(seconds)))
    except Exception:
        return "?"
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}u{(s % 3600) // 60:02d}m"


class Progress:
    """Voortgangsmelder met een schatting uit de gemeten doorvoer.

    total=None of 0 betekent 'onbekend hoeveel': dan geen percentage en geen
    balk, want een verzonnen percentage is erger dan geen percentage. Wel het
    aantal en de verstreken tijd, zodat zichtbaar blijft dat er iets gebeurt.
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
        self._dirty = False  # is er iets geschreven dat nog afgesloten moet?
        self.min_items_for_eta = max(1, int(min_items_for_eta))
        self.enabled = bool(not quiet and enabled_by_default() and self._usable())
        self.is_tty = self._isatty()

    # -- interne helpers ----------------------------------------------------
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
        """Schatting uit wat er tot nu toe gemeten is; None als dat nog niets zegt."""
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
        # Zonder tty is elke regel een regel in een log: alleen bij een
        # merkbare sprong OF na een lange stilte, zodat een trage stap nog
        # steeds laat zien dat er iets gebeurt.
        if percent is not None and percent - self._last_percent >= PIPE_MIN_PERCENT_STEP:
            return True
        return (now - self._last_render) >= PIPE_INTERVAL_SECONDS

    def render_line(self, note: str = "") -> str:
        """De regel zoals hij getoond wordt. Apart zodat een test hem kan lezen."""
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
            parts.append(f"{self.done} verwerkt")
        eta = self._eta_seconds()
        tail = format_duration(elapsed)
        if eta is not None:
            tail += f", nog ~{format_duration(eta)}"
        parts.append(tail)
        if note:
            parts.append(str(note))
        return "  ".join(parts)

    # -- publieke API -------------------------------------------------------
    def step(self, n: int = 1, note: str = "") -> None:
        """Meld n verwerkte items. Rendert hooguit zo vaak als het interval toestaat."""
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
            # Een kapotte balk mag het werk niet raken. Vanaf hier zwijgen we
            # liever helemaal dan dat we het bij elke stap opnieuw proberen.
            self.enabled = False

    def note(self, text: str) -> None:
        """Een losse mededeling tussendoor, op zijn eigen regel."""
        try:
            if not self.enabled:
                return
            self._finish_line()
            self.stream.write(f"{text}\n")
            self.stream.flush()
        except Exception:
            self.enabled = False

    def close(self, note: str = "") -> None:
        """Sluit af met een definitieve regel: wat er gedaan is en hoe lang het duurde."""
        try:
            if not self.enabled:
                return
            elapsed = format_duration(time.monotonic() - self.started)
            geteld = f"{self.done}/{self.total}" if self.total else f"{self.done}"
            staart = f" {note}" if note else ""
            self._finish_line()
            self.stream.write(f"{self.label or 'klaar'}: {geteld} in {elapsed}{staart}\n")
            self.stream.flush()
        except Exception:
            pass
        finally:
            self.enabled = False

    def _write(self, line: str) -> None:
        if self.is_tty:
            # \r + wissen tot regeleinde: geen resten van een langere vorige regel.
            self.stream.write("\r\033[K" + line)
            self._dirty = True
        else:
            self.stream.write(line + "\n")
        self.stream.flush()

    def _finish_line(self) -> None:
        """Sluit een lopende \\r-regel af zodat de volgende output niet overschrijft."""
        if self._dirty:
            self.stream.write("\n")
            self._dirty = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

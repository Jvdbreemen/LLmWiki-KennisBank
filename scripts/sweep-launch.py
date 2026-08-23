#!/usr/bin/env python3
"""sweep-launch.py - SessionStart-launcher voor de capture-sweep.

Dun en NIET-blokkerend: gegate op memory_capture, neemt een single-flight lock,
spawnt memory-sweep.py DETACHED, en eindigt met exit 0 (fail-open). De zware
LLM-sweep draait dus los van SessionStart zodat de sessiestart snel blijft.

Spawnt bewust GEEN indexbouw meer. Dat deed het wel, met een comment die
"sweep eerst, dan de index" beloofde -- maar beide processen werden losgekoppeld
gestart en niets dwong die volgorde af, dus ze schreven tegelijk naar dezelfde
index. index-launch.py draait sweep en bouwers sequentieel achter één lock; zie
TASK-63.

Stdlib only.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sweepstate  # noqa: E402

#: De lock woont in _sweepstate en wordt door de SWEEP verworven, niet hier.
#: Deze launcher is alleen nog een gate: is er een levende lock, spawn dan niet.
#: Verliest hij die race, dan verwerft de gespawnde sweep niets en eindigt hij
#: meteen -- goedkoper dan hier een lock nemen dat een ander proces moet
#: vrijgeven. Twee aanroepers slaan deze launcher sowieso over
#: (commands/kennisbank/rebuild-memory.md en index-launch.py), dus eigenaarschap
#: bij de sweep leggen maakt die twee correct in plaats van uitzonderingen.


def _lock_alive() -> bool:
    lock = _sweepstate.lock_path()
    return lock.exists() and not _sweepstate.is_stale(lock)


def _spawn_detached(script: str, *args) -> None:
    cmd = [sys.executable, script, *args]
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x08000000  # DETACHED_PROCESS|CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(cmd, **kwargs)
    except Exception:
        pass


def main() -> int:
    try:
        import _settings
        if not _settings.get("memory_capture", True):
            return 0
    except Exception:
        pass
    if _lock_alive():
        return 0  # al een sweep bezig
    d = os.path.dirname(os.path.abspath(__file__))
    # ALLEEN de sweep. De index wordt niet meer vanuit hier gespawnd: dat gaf
    # twee losgekoppelde processen die allebei kb-index.db schrijven, zonder dat
    # iets de "sweep eerst, dan de index"-ordening uit de comment afdwong.
    # index-launch.py draait beide sequentieel achter een gedeelde lock.
    _spawn_detached(os.path.join(d, "memory-sweep.py"))
    # Deze launcher neemt geen lock; de gespawnde sweep verwerft en beheert hem
    # zelf. Verliest hij de race met een andere sweep, dan verwerft hij niets en
    # eindigt hij meteen. Het comment dat hier stond ("de lock wordt door de
    # volgende run als stale opgeruimd; sweep zelf is kort") klopte op beide
    # punten niet meer: de sweep geeft nu zelf vrij, en een gemeten run duurde
    # 23m52s.
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

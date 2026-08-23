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
from _common import outside_window  # noqa: E402
from _vaultpath import vault_root  # noqa: E402
import _sweepstate  # noqa: E402

#: Eigenaar is _sweepstate: de sweep zelf ververst deze lock als lease terwijl
#: hij werkt. Alias hier zodat bestaande lezers van sweep-launch.LOCK_NAME
#: blijven werken.
LOCK_NAME = _sweepstate.LOCK_NAME
STALE_SEC = 3600  # een lock ouder dan 1u geldt als verweesd


def _lock_path() -> Path:
    return _sweepstate.lock_path()


def is_stale(lock: Path) -> bool:
    """True als de lock verder dan STALE_SEC van nu af ligt -- in het verleden
    (verweesd) of in de toekomst (klokverzetting; zonder die kant verloopt zo'n
    lock nooit en ligt het onderhoud permanent stil).

    Het venster is SYMMETRISCH en niet `age < 0`, want een verse mtime kan op
    Windows in de toekomst liggen: `time.time()` leest daar
    GetSystemTimeAsFileTime met een resolutie van 15,625 ms, terwijl het
    bestandssysteem de mtime van een fijnere klok stempelt. Gemeten: 586 van
    5000 net aangemaakte bestanden gaven age < 0 (max +0,016 s). Met `age < 0`
    verklaarde acquire_lock dus 12% van zijn EIGEN verse locks stale, ruimde ze
    op en gaf single-flight weg (TASK-140)."""
    try:
        age = time.time() - lock.stat().st_mtime
        return outside_window(age, STALE_SEC)
    except OSError:
        return True


def acquire_lock() -> bool:
    """Probeer de lock atomair te verkrijgen (O_EXCL-first).

    1. Probeer O_CREAT|O_EXCL direct — slaagt als de lock nog niet bestaat.
    2. Bij FileExistsError: controleer of de lock stale is.
       - Niet stale → een actieve sweep draait; return False.
       - Stale → unlink + één retry van de O_EXCL-create (reclaim).
    Concurrent sweeps beschadigen elkaars data niet: de watermark (nu
    outage-veilig) + dedup voorkomen dubbele writes. Ze zijn wel duur, want ze
    delen een GPU en verdubbelen het werk, en dat was precies waar de oude
    leeftijds-only staleness in liep: een sweep die langer dan STALE_SEC duurde
    liet zijn eigen lock verlopen. De sweep ververst hem nu als lease
    (_sweepstate.refresh_lock), dus stale betekent weer "niemand werkt eraan".
    """
    lock = _lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        if not is_stale(lock):
            return False
        # Stale lock: opruimen en één keer opnieuw proberen.
        try:
            lock.unlink()
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except (FileExistsError, OSError):
            return False
    except OSError:
        return False


def release_lock() -> None:
    try:
        _lock_path().unlink()
    except OSError:
        pass


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
    if not acquire_lock():
        return 0  # al een sweep bezig
    d = os.path.dirname(os.path.abspath(__file__))
    # ALLEEN de sweep. De index wordt niet meer vanuit hier gespawnd: dat gaf
    # twee losgekoppelde processen die allebei kb-index.db schrijven, zonder dat
    # iets de "sweep eerst, dan de index"-ordening uit de comment afdwong.
    # index-launch.py draait beide sequentieel achter een gedeelde lock.
    _spawn_detached(os.path.join(d, "memory-sweep.py"))
    # de lock wordt door de volgende run als 'stale' opgeruimd; sweep zelf is kort
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

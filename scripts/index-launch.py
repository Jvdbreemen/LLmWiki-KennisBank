#!/usr/bin/env python3
"""index-launch.py - detacht al het indexonderhoud weg van SessionStart.

De coordinator draaide de drie indexbouwers BLOKKEREND: worst case ~210 s voor
Claude en Codex, ~300 s voor Copilot -- die laatste hoger dan de timeout die de
Copilot-integratie zelf declareert, zodat de coordinator zijn eigen plafond kon
overschrijden. Dat botst met noord-ster 1 in CLAUDE.md: zware verwerking hoort
off de interactieve weg.

Twee modi in een script, zodat er geen tweede bestand nodig is:

  (standaard)  neem de lock, spawn een losgekoppelde worker, keer direct terug.
  --worker     draai de bouwers SEQUENTIEEL en geef de lock daarna vrij.

Sequentieel, niet parallel: alle bouwers schrijven naar dezelfde vault en
sqlite-bestanden. De oude sweep-launcher spawnde memory-sweep en build-kb-index
allebei losgekoppeld -- de comment sprak van "sweep eerst, dan de index", maar
niets dwong die volgorde af. Hier wel.

Fail-open overal: elke fout eindigt in exit 0. Een mislukt indexonderhoud is een
gemiste verversing, geen reden om een sessie te blokkeren.

Stdlib only.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

LOCK_NAME = ".kb-index-worker.lock"

# Plafond per bouwer. De activity-bouwer is de traagste (volledige rebuild over
# een grote vault); de rest is normaal seconden.
PER_JOB_TIMEOUT = 300

# Volgorde is betekenisvol: de sweep flipt memory-statussen en schrijft
# markdown, dus die moet klaar zijn voordat de index eroverheen loopt.
JOBS = (
    ("memory-sweep.py", "memory_capture"),
    ("build-embed-index.py", None),
    ("build-kb-index.py", None),
    ("build-activity-index.py", None),
)

# De worker draait de jobs sequentieel, dus de bovengrens is PER_JOB_TIMEOUT maal
# het aantal jobs. De lock-vervaltijd moet daar strikt boven liggen: anders kan
# een tweede sessie een nog draaiende worker als verweesd beschouwen en een
# tweede starten -- precies de dubbele-schrijver-situatie die dit script moet
# uitsluiten. De factor is bewust ruim, en afgeleid in plaats van los genoteerd:
# een los getal in een comment drift zodra JOBS groeit.
# test_stale_window_exceeds_the_worst_case_run bewaakt de ongelijkheid.
STALE_SEC = PER_JOB_TIMEOUT * len(JOBS) * 2


def _lock_path() -> Path:
    return vault_root() / ".claude" / LOCK_NAME


def is_stale(lock: Path, now: float | None = None) -> bool:
    """True bij een lock ouder dan STALE_SEC of met een toekomstige mtime.

    Die tweede clausule vangt een klokverzetting af: zonder hem zou een lock met
    een mtime in de toekomst nooit verlopen en het onderhoud permanent stilzetten.
    """
    try:
        age = (time.time() if now is None else now) - lock.stat().st_mtime
        return age > STALE_SEC or age < 0
    except OSError:
        return True


def acquire_lock(now: float | None = None) -> bool:
    """Atomair claimen via O_EXCL; bij een verweesde lock eenmalig heroveren."""
    lock = _lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)

    def _create() -> bool:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            return False
        except OSError:
            return False

    if _create():
        return True
    if not is_stale(lock, now=now):
        return False
    try:
        lock.unlink()
    except OSError:
        return False
    return _create()


def release_lock() -> None:
    try:
        _lock_path().unlink()
    except OSError:
        pass


def _enabled(toggle: "str | None") -> bool:
    if toggle is None:
        return True
    try:
        import _settings
        return bool(_settings.get(toggle, True))
    except Exception:
        return True          # fail-open: liever draaien dan stil overslaan


def spawn_worker() -> None:
    """Start deze module opnieuw in --worker-modus, losgekoppeld van de sessie."""
    cmd = [sys.executable, os.path.abspath(__file__), "--worker"]
    kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x08000000  # DETACHED_PROCESS|CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **kwargs)


def run_jobs(runner=None) -> list:
    """Draai de bouwers sequentieel. Geeft [(script, returncode|None)] terug."""
    if runner is None:
        def runner(path, timeout):
            proc = subprocess.run(
                [sys.executable, path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=timeout)
            return proc.returncode
    here = os.path.dirname(os.path.abspath(__file__))
    out = []
    for script, toggle in JOBS:
        if not _enabled(toggle):
            out.append((script, None))
            continue
        try:
            out.append((script, runner(os.path.join(here, script), PER_JOB_TIMEOUT)))
        except Exception:
            out.append((script, None))
    return out


def main(argv: "list[str] | None" = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--worker" in argv:
        try:
            run_jobs()
        finally:
            release_lock()
        return 0
    if not acquire_lock():
        return 0                      # er draait al onderhoud
    try:
        spawn_worker()
    except Exception:
        release_lock()                # niets gespawnd -> lock niet laten staan
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

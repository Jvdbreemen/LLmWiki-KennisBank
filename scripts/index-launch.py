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
import uuid
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
    # Laadt graphify-out/graph.json in kb-graph.db. Stond tot TASK-78 in geen
    # enkele launcher, waardoor de graaf-db stil verouderde na een graphify-run.
    # Zonder graph.json of bij ongewijzigde vingerafdruk is het een no-op.
    ("build-graph-index.py", None),
    # Netwerk. Stond tot 2026-07-25 blokkerend in git-upstream-check op de
    # sessiestart-weg: 801 ms van de 1384 ms daar, en bij een trage verbinding
    # oplopend tot FETCH_TIMEOUT. Hier kost het de gebruiker geen wachttijd.
    ("git-fetch-refresh.py", None),
)

# De worker draait de jobs sequentieel, dus de bovengrens is PER_JOB_TIMEOUT maal
# het aantal jobs. De lock-vervaltijd moet daar strikt boven liggen: anders kan
# een tweede sessie een nog draaiende worker als verweesd beschouwen en een
# tweede starten -- precies de dubbele-schrijver-situatie die dit script moet
# uitsluiten. De factor is bewust ruim, en afgeleid in plaats van los genoteerd:
# een los getal in een comment drift zodra JOBS groeit.
# test_stale_window_exceeds_the_worst_case_run bewaakt de ongelijkheid.
STALE_SEC = PER_JOB_TIMEOUT * len(JOBS) * 2
#: How long a lock without a readable PID counts as freshly created rather than
#: orphaned. Covers the microseconds between O_EXCL and the PID write; anything
#: longer than this and the file really is truncated.
PID_GRACE_SEC = 5.0


def _lock_path() -> Path:
    return vault_root() / ".claude" / LOCK_NAME


def _lock_pid(lock: Path) -> int | None:
    """Read the current owner PID stored in the lock."""
    try:
        value = lock.read_text(encoding="ascii").strip().splitlines()[0]
        pid = int(value)
        return pid if pid > 0 else None
    except (OSError, IndexError, TypeError, ValueError):
        return None


def _lock_token(lock: Path) -> str | None:
    """Read the launch token that prevents an old worker deleting a new lock."""
    try:
        value = lock.read_text(encoding="ascii").strip().splitlines()
        token = value[1].strip()
        return token or None
    except (OSError, IndexError, TypeError, ValueError):
        return None


def _pid_alive(pid: int | None) -> bool:
    """Return whether *pid* currently identifies a process on this host."""
    if pid is None:
        return False
    if os.name == "nt":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(
                0x1000,  # PROCESS_QUERY_LIMITED_INFORMATION
                False,
                pid,
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            pass
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except (ProcessLookupError, OSError):
        return False
    return True


def is_stale(lock: Path, now: float | None = None) -> bool:
    """True when the owner is dead, or the lock lies outside its time window.

    The window is SYMMETRIC (`abs(age) > STALE_SEC`), not `age < 0`. It has to
    expire a lock stamped far in the future, or a clock change parks maintenance
    forever -- but on Windows `time.time()` reads GetSystemTimeAsFileTime at a
    15.625 ms resolution while the filesystem stamps mtime from a finer clock,
    so a lock created microseconds ago can carry a future mtime: 586 of 5000
    measured. With `age < 0` acquire_lock reclaimed its OWN fresh lock and two
    index builders could write kb-index.db at once -- exactly what TASK-63 put
    behind this lock (TASK-140).

    The PID has the same race one level down, which is what PID_GRACE_SEC is
    for: _create() opens the lock with O_EXCL and writes the PID as a second
    step, so for a few microseconds the file is empty and _lock_pid() reads
    nothing. Calling that a dead owner would hand the lock to the process that
    LOST the race. An unreadable lock is therefore only orphaned once it is also
    old -- which is still far quicker than the full stale window, so a genuinely
    truncated lock does not block maintenance for an hour.
    """
    try:
        age = (time.time() if now is None else now) - lock.stat().st_mtime
    except OSError:
        return True
    pid = _lock_pid(lock)
    if pid is None:
        return abs(age) > PID_GRACE_SEC
    # A worker that died before its finally-block ran must not suppress the
    # next maintenance launch for the full stale window. The old code only
    # used mtime, which made a dead PID look active for up to an hour.
    if not _pid_alive(pid):
        return True
    return abs(age) > STALE_SEC


def acquire_lock(now: float | None = None) -> bool:
    """Atomair claimen via O_EXCL; bij een verweesde lock eenmalig heroveren."""
    lock = _lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)

    def _create() -> bool:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(
                fd,
                f"{os.getpid()}\n{uuid.uuid4().hex}\n".encode("ascii"),
            )
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


def release_lock(token: str | None = None) -> None:
    """Release only our lock; an old worker must not remove a newer one."""
    try:
        lock = _lock_path()
        if token is not None and _lock_token(lock) != token:
            return
        lock.unlink()
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


def _adopt_lock(token: str) -> bool:
    """Transfer ownership from the launcher PID to this detached worker."""
    lock = _lock_path()
    if _lock_token(lock) != token:
        return False
    temporary = lock.with_name(f"{lock.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            f"{os.getpid()}\n{token}\n", encoding="ascii"
        )
        os.replace(temporary, lock)
        return True
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
        return False


def spawn_worker(token: str) -> None:
    """Start deze module opnieuw in --worker-modus, losgekoppeld van de sessie."""
    cmd = [
        sys.executable,
        os.path.abspath(__file__),
        "--worker",
        "--lock-token",
        token,
    ]
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
            kwargs: dict = {"stdout": subprocess.DEVNULL,
                            "stderr": subprocess.DEVNULL}
            if os.name == "nt":
                # The worker itself is DETACHED_PROCESS and has no console; a
                # console-less parent spawning python.exe makes Windows pop up
                # a visible console per job. CREATE_NO_WINDOW keeps it hidden.
                kwargs["creationflags"] = 0x08000000
            proc = subprocess.run([sys.executable, path], timeout=timeout,
                                  **kwargs)
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
            token = argv[argv.index("--lock-token") + 1]
        except (ValueError, IndexError):
            return 0
        if not _adopt_lock(token):
            return 0
        try:
            run_jobs()
        finally:
            release_lock(token)
        return 0
    if not acquire_lock():
        return 0                      # er draait al onderhoud
    token = _lock_token(_lock_path())
    if not token:
        release_lock()
        return 0
    try:
        spawn_worker(token)
    except Exception:
        release_lock(token)            # niets gespawnd -> lock niet laten staan
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

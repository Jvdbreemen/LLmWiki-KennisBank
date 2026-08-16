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

import contextlib
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import outside_window, pid_alive  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

LOCK_NAME = ".kb-index-worker.lock"
#: OS-level mutex serialising every MUTATION of the lock file. The lock file's
#: content (pid + token) says who owns maintenance; this mutex says who may
#: change that file right now. Without it, a second session could judge the
#: lock stale, and between that judgement and its unlink the worker's
#: os.replace adoption landed — the unlink then deleted a LIVE lock and two
#: builders wrote kb-index.db at once (TASK-183, reproduced deterministically).
#: The mutex file itself is never deleted, so its identity is stable.
MUTEX_NAME = LOCK_NAME + ".mutex"

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
#: How long a lock without a readable PID counts as freshly created rather
#: than orphaned (covers the microseconds between O_EXCL and the PID write),
#: AND how long a lock naming a DEAD pid counts as a handoff in flight: the
#: launcher writes its own PID and exits, and until the detached worker's
#: _adopt_lock rewrites it (Python startup, 0.1-1s, longer under AV scans)
#: the lock legitimately names an exited process (TASK-183). A genuinely
#: crashed worker therefore waits out these seconds, not the full stale hour.
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


# Alias keeps the module-level monkeypatch surface tests rely on; the one
# implementation (and its access-denied-means-alive rule) lives in _common.
_pid_alive = pid_alive


@contextlib.contextmanager
def _lock_mutex(timeout: float = 2.0):
    """Hold the OS-level mutex around a lock-file mutation; yields got: bool.

    Byte-range lock (msvcrt.locking / fcntl.flock) on a stable file in the
    vault's .claude/. OS locks die with their process, which is exactly why a
    file-content lock alone cannot do this job. Assumes a local filesystem
    (NTFS/ext4); flock semantics degrade on NFS/SMB-mounted vaults. Fail-open:
    a busy or broken mutex yields False and the caller skips — a missed
    maintenance pass, never a double one.
    """
    path = vault_root() / ".claude" / MUTEX_NAME
    fd = None
    locked = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_CREAT | os.O_RDWR)
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"1")  # msvcrt region-locks need at least one byte
        deadline = time.monotonic() + timeout
        while True:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
        yield locked
    except Exception:
        yield False
    finally:
        if fd is not None:
            if locked:
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
            try:
                os.close(fd)
            except OSError:
                pass


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
        return outside_window(age, PID_GRACE_SEC)
    # A worker that died before its finally-block ran must not suppress the
    # next maintenance launch for the full stale window — but a FRESH lock
    # naming a dead pid is the launcher->worker handoff, not an orphan: the
    # launcher exits before the worker adopts (TASK-183). Dead pid is only
    # stale once the lock is also older than the grace.
    if not _pid_alive(pid):
        return outside_window(age, PID_GRACE_SEC)
    return outside_window(age, STALE_SEC)


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
    with _lock_mutex() as got:
        if not got:
            return False  # someone else is mutating; fail-open, skip
        # Re-judge INSIDE the mutex: between the first judgement and this
        # point the worker's adoption may have landed (the TASK-183
        # interleave). Unlinking without re-judging deleted a live lock.
        if not is_stale(lock, now=now):
            return False
        try:
            lock.unlink()
        except OSError:
            return False
        return _create()


def release_lock(token: str | None = None) -> None:
    """Release only our lock; an old worker must not remove a newer one.

    Uniform rule since TASK-183: every mutation of the lock file happens
    under the mutex."""
    try:
        with _lock_mutex() as got:
            if not got:
                return
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
    """Transfer ownership from the launcher PID to this detached worker.

    Under the mutex (TASK-183): adoption raced acquire_lock's stale-reclaim,
    and the reclaim's unlink could land right after this os.replace."""
    with _lock_mutex() as got:
        if not got:
            return False
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

#!/usr/bin/env python3
"""sweep-launch.py - SessionStart-launcher voor de capture-sweep.

Dun en NIET-blokkerend: gegate op memory_capture, neemt een single-flight lock,
spawnt memory-sweep.py DETACHED en daarna build-kb-index.py (sweep->index-ordening),
en eindigt met exit 0 (fail-open). De zware LLM-sweep draait dus los van SessionStart
zodat de sessiestart onzichtbaar/snel blijft.

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

LOCK_NAME = ".sweep.lock"
STALE_SEC = 3600  # een lock ouder dan 1u geldt als verweesd


def _lock_path() -> Path:
    return vault_root() / ".claude" / LOCK_NAME


def is_stale(lock: Path) -> bool:
    """True als de lock ouder is dan STALE_SEC of een toekomstige mtime heeft (clock skew)."""
    try:
        age = time.time() - lock.stat().st_mtime
        return age > STALE_SEC or age < 0
    except OSError:
        return True


def acquire_lock() -> bool:
    """Probeer de lock atomair te verkrijgen (O_EXCL-first).

    1. Probeer O_CREAT|O_EXCL direct — slaagt als de lock nog niet bestaat.
    2. Bij FileExistsError: controleer of de lock stale is.
       - Niet stale → een actieve sweep draait; return False.
       - Stale → unlink + één retry van de O_EXCL-create (reclaim).
    Concurrent sweeps zijn onschadelijk: de watermark (nu outage-veilig) +
    dedup voorkomen dubbele writes.
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
    # ordening: sweep (status-flips/schrijven) eerst, dan de index
    _spawn_detached(os.path.join(d, "memory-sweep.py"))
    _spawn_detached(os.path.join(d, "build-kb-index.py"))
    # de lock wordt door de volgende run als 'stale' opgeruimd; sweep zelf is kort
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

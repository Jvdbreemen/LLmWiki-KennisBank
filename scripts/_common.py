"""Shared helpers for the KennisBank scripts.

Single source of truth for small utilities that were duplicated verbatim
across scripts:

- :func:`slugify` — filename-safe slug from arbitrary text.
- :func:`_utcnow_iso` / :func:`_today_iso` — UTC timestamp helpers.
- :func:`print_summary` — render the import summary (JSON or one-line text).
- :func:`env_int` / :func:`env_float` — fail-soft numeric env-var readers.

Stdlib only. No hyphen in the filename so the scripts can ``import`` it after
``sys.path.insert`` (the same trick used for ``_frontmatter.py`` /
``_vaultpath.py``).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone


def env_int(name: str, default: int) -> int:
    """Read an int env var; empty, whitespace or malformed values fall back
    to *default*. Never raises: an import-time ``int()`` over an env var once
    turned one typo (``KB_EMBED_NUM_CTX=4k``) into a silent retrieval outage —
    the fail-open hook swallowed the ValueError from ``import _embeddings``
    and injected nothing (TASK-185)."""
    try:
        s = os.environ.get(name, "").strip()
        return int(s) if s else default
    except (ValueError, TypeError):
        return default


#: Cores left free when a session hook fans out. A hook is a background
#: courtesy: the person who triggered it is still typing in the same machine,
#: so the fan-out must never be able to claim the whole box.
POOL_HEADROOM = 2


def pool_workers(jobs: int) -> int:
    """How many of *jobs* child processes may run at once.

    The three session coordinators used ``max_workers=len(jobs)``, which sizes
    the pool to the WORK instead of to the MACHINE. Each job starts a real
    Python interpreter, so that spelling has no upper bound: add a sixth index
    builder and every one of them starts at the same instant, on whatever
    hardware happens to run it. Today the job lists are short enough that the
    difference is invisible on a 16-core desktop -- which is exactly why it is
    worth pinning down now, while it is a one-line change and not an incident
    on someone's two-core laptop or a CI container with a fractional CPU quota.

    Leave POOL_HEADROOM cores free so the machine stays usable, never go below
    2 (a fan-out of one is not a fan-out), and never exceed the job count.
    ``KB_MAX_WORKERS`` overrides the whole calculation for the rare case where
    the operator knows better than the core count -- a CI container whose
    cgroup quota os.cpu_count() cannot see, most of all."""
    if jobs <= 0:
        return 1
    cap = env_int("KB_MAX_WORKERS", 0)
    if cap <= 0:
        cap = max(2, (os.cpu_count() or 4) - POOL_HEADROOM)
    return max(1, min(jobs, cap))


def env_float(name: str, default: float) -> float:
    """Float twin of :func:`env_int`, same fallback contract."""
    try:
        s = os.environ.get(name, "").strip()
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def pid_alive(pid) -> bool:
    """Canonical liveness probe (TASK-183 ended two divergent copies).

    Semantics: access-denied means ALIVE — a PID we may not inspect exists,
    and for single-flight locking "alive" is the safe direction. The old
    _embeddings copy read PermissionError as dead, so an EPERM-protected
    warm child looked finished and spawned duplicates.

    Windows caveat, measured: OpenProcess succeeds on a zombie for as long
    as ANY handle to the exited process exists (exit code readable); only
    after the last handle closes does it return NULL (error 87). That errs
    toward "alive", which the callers tolerate by design. Never falls back
    to os.kill on Windows: signal 0 there is CTRL_C_EVENT — a signal SEND to
    process group *pid*, not a probe.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            # Explicit prototypes: without them the 64-bit HANDLE truncates
            # to the default c_int and a valid handle can read as NULL.
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int,
                                             ctypes.c_uint32)
            kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
            handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED: exists
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def outside_window(age: float, window: float) -> bool:
    """The one spelling of the symmetric staleness window: |age| > window.

    Symmetric on purpose (TASK-140): on Windows, time.time() reads a
    15.625 ms clock while the filesystem stamps mtime from a finer one, so a
    file created microseconds ago can carry a slightly FUTURE mtime (586 of
    5000 measured). A one-sided `age > window` would also let a lock stamped
    hours ahead (clock set back, restored file) suppress its owner forever.
    """
    return abs(age) > window


def slugify(text: str, max_len: int = 50) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        return "untitled"
    return text[:max_len].rstrip("-") or "untitled"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def print_summary(summary: dict, as_json: bool) -> None:
    """Print the import summary the same way all three importers always did.

    ``summary`` is the dict with ``imported`` / ``skipped`` / ``errors`` /
    ``files`` / ``errors_detail`` keys. When ``as_json`` is true the full dict
    is dumped as indented JSON; otherwise a single ``--- summary: ...`` line is
    printed. Byte-faithful to the previous inline blocks.
    """
    if as_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(
            f"--- summary: imported={summary['imported']} "
            f"skipped={summary['skipped']} errors={summary['errors']}"
        )

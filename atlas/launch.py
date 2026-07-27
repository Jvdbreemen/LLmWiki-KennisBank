#!/usr/bin/env python3
"""KennisBank Atlas dev launcher (TASK-27.10).

One command to run Atlas in dev mode: it starts the FastAPI sidecar on a free
loopback port and the Vite dev server, then prints the URL to open. Ctrl-C
stops both. The vault comes from KENNISBANK_VAULT (ADR-0002); no hardcoded path.

Bundled/Tauri launch is TASK-27.12 (needs the Rust toolchain); this covers the
dev workflow used throughout development.
"""
from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRONTEND = HERE / "frontend"


def _windows_kill_on_close_job() -> object | None:
    """Bind this process to a Job Object that kills the whole tree on close.

    On Windows, SIGTERM handlers are dead code: a terminated launcher (task
    manager, a stopped wrapper shell) never runs Python cleanup, so the
    sidecar and vite children survive as orphans. A Job Object with
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE makes the OS tear down every child
    the moment the launcher dies, no cooperation required. Children spawned
    after assignment inherit job membership automatically.

    Returns the job handle (kept alive by the caller) or None off-Windows.
    """
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    # Explicit prototypes: without these ctypes truncates 64-bit HANDLEs to
    # 32-bit ints and AssignProcessToJobObject fails with ERROR_INVALID_HANDLE.
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(
        job, JobObjectExtendedLimitInformation,
        ctypes.byref(info), ctypes.sizeof(info))
    if ok:
        ok = kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess())
    if not ok:
        # Fail-open: better a working launcher without the guard than no
        # launcher (e.g. already in an incompatible job on old Windows).
        kernel32.CloseHandle(job)
        return None
    return job


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _resolve_vault() -> str:
    v = os.environ.get("KENNISBANK_VAULT")
    if not v:
        sys.exit("KENNISBANK_VAULT is niet gezet (ADR-0002; geen hardcoded default).")
    return v


def main() -> None:
    # Keep a reference for the process lifetime: closing the handle kills the job.
    _job = _windows_kill_on_close_job()  # noqa: F841
    vault = _resolve_vault()
    sidecar_port = _free_port()
    vite_port = _free_port()

    env = {**os.environ, "KENNISBANK_VAULT": vault}
    procs: list[subprocess.Popen] = []

    def _stop(*_):
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print(f"[atlas] sidecar -> 127.0.0.1:{sidecar_port}  (vault: {vault})")
    procs.append(subprocess.Popen(
        [sys.executable, "-m", "atlas.sidecar", "--host", "127.0.0.1",
         "--port", str(sidecar_port)],
        cwd=HERE.parent, env=env))

    print(f"[atlas] vite    -> 127.0.0.1:{vite_port}")
    procs.append(subprocess.Popen(
        ["npx", "vite", "--host", "127.0.0.1", "--port", str(vite_port), "--strictPort"],
        cwd=FRONTEND, env=env, shell=(os.name == "nt")))

    # wait briefly for the sidecar health, then print the open URL
    import urllib.request
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{sidecar_port}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)

    url = f"http://127.0.0.1:{vite_port}/?port={sidecar_port}"
    print(f"\n[atlas] OPEN:  {url}\n[atlas] Ctrl-C stopt sidecar + vite.\n")

    try:
        while all(p.poll() is None for p in procs):
            time.sleep(1)
    finally:
        _stop()


if __name__ == "__main__":
    main()

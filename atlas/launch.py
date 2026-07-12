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

#!/usr/bin/env python3
"""KennisBank Atlas doctor (TASK-27.10).

Reports the Atlas build/run readiness: Python + sidecar deps, Node/npm, the Rust
toolchain (cargo/tauri, needed only for the bundled app), Ollama, the vault
stores, and — if a sidecar is passed via --port — its live health. Exit 0 when
nothing is a hard failure; the Rust toolchain is OPTIONAL (only needed for the
Tauri bundle) so its absence is a warning, never a failure.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
from pathlib import Path

OK, WARN, FAIL = "ok ", "warn", "FAIL"


def _line(status: str, label: str, detail: str = "") -> None:
    print(f"[{status}] {label}{(' - ' + detail) if detail else ''}")


def _have_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> int:
    ap = argparse.ArgumentParser(prog="atlas-doctor")
    ap.add_argument("--port", type=int, default=None, help="live sidecar port to health-check")
    args = ap.parse_args()

    failures = 0

    # sidecar runtime deps
    for mod in ("fastapi", "uvicorn", "httpx"):
        if _have_module(mod):
            _line(OK, f"python: {mod}")
        else:
            _line(FAIL, f"python: {mod}", "pip install -r atlas/sidecar/requirements.txt")
            failures += 1
    if _have_module("sqlite_vec"):
        _line(OK, "python: sqlite-vec (recall)")
    else:
        _line(FAIL, "python: sqlite-vec", "recall needs it; pip install sqlite-vec")
        failures += 1

    # frontend toolchain
    _line(OK if shutil.which("node") else FAIL, "node", shutil.which("node") or "install Node 18+")
    _line(OK if shutil.which("npm") else FAIL, "npm", shutil.which("npm") or "install npm")
    if not shutil.which("node"):
        failures += 1

    # rust toolchain (OPTIONAL — only for the bundled Tauri app, TASK-27.12)
    cargo = shutil.which("cargo")
    _line(OK if cargo else WARN, "cargo (Tauri bundle)",
          cargo or "optional; install rustup for the standalone .exe (dev mode works without)")

    # ollama (recall)
    try:
        import httpx
        httpx.get("http://127.0.0.1:11434/api/version", timeout=1.0)
        _line(OK, "ollama", "127.0.0.1:11434")
    except Exception:
        _line(WARN, "ollama", "not reachable; /recall degrades, other lenses fine")

    # vault stores
    vault = os.environ.get("KENNISBANK_VAULT")
    if not vault:
        _line(WARN, "vault", "KENNISBANK_VAULT not set")
    else:
        v = Path(vault)
        for rel, label in [(".claude/kb-index.db", "kb-index"),
                           (".claude/kb-activity.db", "activity"),
                           ("graphify-out/graph.json", "graph"),
                           ("09-memory", "memory")]:
            p = v / rel
            _line(OK if p.exists() else WARN, f"vault: {label}", str(p) if p.exists() else "afwezig")

    # live sidecar health
    if args.port:
        try:
            import httpx
            h = httpx.get(f"http://127.0.0.1:{args.port}/health", timeout=2.0).json()
            live = [k for k, ok in h.get("sources", {}).items() if ok]
            _line(OK if h.get("status") == "ok" else WARN, f"sidecar :{args.port}",
                  f"{h.get('status')} · bronnen: {', '.join(live)}")
        except Exception as exc:
            _line(FAIL, f"sidecar :{args.port}", str(exc))
            failures += 1

    print()
    _line(OK if failures == 0 else FAIL, "samenvatting",
          "klaar voor dev" if failures == 0 else f"{failures} harde fout(en)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

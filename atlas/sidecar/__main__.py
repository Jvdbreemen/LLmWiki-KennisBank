"""Run the Atlas sidecar (dev-mode uvicorn), loopback-only.

Binds 127.0.0.1 on a free ephemeral port and prints ``ATLAS_PORT <port>`` on
stdout so the Tauri shell can read the negotiated port (TASK-27.3). The vault
root comes from KENNISBANK_VAULT (ADR-0002 vault_root convention); never a
hardcoded path.
"""
from __future__ import annotations

import argparse
import os
import socket
from pathlib import Path

import uvicorn

from atlas.sidecar.app import create_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _resolve_vault(cli_vault: str | None) -> Path:
    if cli_vault:
        return Path(cli_vault)
    env = os.environ.get("KENNISBANK_VAULT")
    if env:
        return Path(env)
    raise SystemExit(
        "no vault: pass --vault or set KENNISBANK_VAULT (no hardcoded default)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="atlas-sidecar")
    parser.add_argument("--host", default="127.0.0.1")  # loopback only
    parser.add_argument("--port", type=int, default=0)   # 0 = ephemeral
    parser.add_argument("--vault", default=None)
    args = parser.parse_args()

    vault = _resolve_vault(args.vault)
    port = args.port or _free_port()
    # Emit the port before blocking so the shell can connect.
    print(f"ATLAS_PORT {port}", flush=True)
    uvicorn.run(create_app(vault), host=args.host, port=port, log_level="warning")


if __name__ == "__main__":
    main()

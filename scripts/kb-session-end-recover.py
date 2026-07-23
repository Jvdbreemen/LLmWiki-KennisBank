#!/usr/bin/env python3
"""Recover a SessionEnd hook that was cancelled before it finished.

The exit coordinator writes a 'running' state before its work and a 'completed'
state after. If the client kills the hook process on shutdown (observed as
"Hook cancelled"), the state stays 'running' and the transcript may never have
been archived. This script runs at the next SessionStart: if it finds a stale
'running' state, it re-runs the capture for the recorded transcript, so a killed
exit costs at most a one-session delay instead of losing the transcript.

Stdlib-only and always fails open: session start must never depend on it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _vaultpath import vault_root  # noqa: E402

STATE_NAME = "kb-session-end-state.json"
LOG_NAME = "kb-session-end.log"
# A run younger than this may still be in flight in another process; leave it.
MIN_AGE_SECONDS = 120


def _log(vault: Path, message: str) -> None:
    try:
        path = vault / ".claude" / LOG_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} pid={os.getpid()} recover {message}\n")
    except Exception:
        pass


def _read_state(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def recover(vault: Path, *, now: float | None = None) -> str | None:
    """Re-run capture for a stale 'running' exit state. Returns a note or None."""
    now = time.time() if now is None else now
    state_path = vault / ".claude" / STATE_NAME
    state = _read_state(state_path)
    if state.get("status") != "running":
        return None

    age = now - float(state.get("started_at") or 0)
    if age < MIN_AGE_SECONDS:
        return None  # possibly still in flight; do not race it

    transcript = state.get("transcript_path") or ""
    client = state.get("client") or "claude"
    scripts = vault / ".claude" / "scripts"
    capture = "kb-copilot-capture.py" if client == "copilot" else "archive-transcript.py"

    payload = json.dumps({"transcript_path": transcript}).encode("utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, str(scripts / capture)],
            input=payload,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        ok = proc.returncode == 0
    except Exception as exc:  # noqa: BLE001 - fail open
        ok, detail = False, f"could not run: {exc}"

    # Close the stale state either way, so it is recovered at most once.
    try:
        state["status"] = "recovered" if ok else "recovery-failed"
        state["recovered_at"] = now
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass

    note = (
        f"recovered cancelled {client} exit (age={int(age)}s, capture={capture}, "
        f"ok={ok}{': ' + detail if detail else ''})"
    )
    _log(vault, note)
    return note


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--client", default="claude")
    parser.add_argument("--emit-context", action="store_true",
                        help="print a SessionStart additionalContext note when a recovery ran")
    try:
        args, _unknown = parser.parse_known_args(argv)
        try:
            sys.stdin.buffer.read()
        except OSError:
            pass
        note = recover(vault_root())
        if note and args.emit_context:
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": f"KennisBank: {note}",
                }
            }))
    except Exception:
        # Session start must never depend on KennisBank.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

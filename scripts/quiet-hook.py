#!/usr/bin/env python3
"""Run a KennisBank maintenance hook without exposing routine process output.

The wrapped hook receives the original stdin payload. Its stdout and stderr are
captured, and every result fails open so background indexing or telemetry can
never block an agent client. Meaningful changes and warnings are returned as
structured agent context; no-change maintenance output remains silent.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def _changed_count(text: str, pattern: str) -> int:
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _relevant_report(script: str, stdout: str, stderr: str) -> str:
    """Return only maintenance output that changes state or needs attention."""
    out = stdout.strip()
    err = stderr.strip()
    relevant = bool(err)
    if script == "build-embed-index.py":
        relevant = relevant or _changed_count(out, r"(\d+)\s+\(re\)embedded") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+failed") > 0
    elif script == "build-kb-index.py":
        relevant = relevant or _changed_count(out, r"(\d+)\s+\(re\)indexed") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+verwijderd") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+failed") > 0
    elif script == "build-activity-index.py":
        relevant = relevant or _changed_count(out, r"(\d+)\s+changed") > 0
    else:
        relevant = relevant or bool(out)
    if not relevant:
        return ""
    details = "\n".join(part for part in (out, err) if part)
    return (
        f"KennisBank report from {script}:\n{details}\n"
        "Briefly report this to the user when it changes available knowledge "
        "or requires action; do not repeat routine implementation details."
    )


def _emit_context(client: str, event: str, report: str) -> None:
    if not report:
        return
    if client == "claude":
        payload = {
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": report,
            },
        }
    elif client == "copilot":
        payload = {"additionalContext": report}
    else:
        payload = {
            "suppressOutput": True,
            "additionalContext": report,
        }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    client = "codex"
    event = "SessionStart"
    while len(args) >= 2 and args[0] in {"--client", "--event"}:
        option, value = args[:2]
        args = args[2:]
        if option == "--client":
            client = value
        else:
            event = value
    if not args:
        return 0
    script_path = args[0]
    try:
        payload = sys.stdin.buffer.read()
    except OSError:
        payload = b""
    try:
        result = subprocess.run(
            [sys.executable, *args],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        report = _relevant_report(
            Path(script_path).name,
            result.stdout.decode("utf-8", errors="replace"),
            result.stderr.decode("utf-8", errors="replace"),
        )
        _emit_context(client, event, report)
    except (OSError, subprocess.SubprocessError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

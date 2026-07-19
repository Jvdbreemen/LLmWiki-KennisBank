#!/usr/bin/env python3
"""Coordinate KennisBank exit work behind one fail-open client hook.

Capture is a deterministic first phase. Independent post-capture jobs then run
concurrently. Routine output is never written to stdout, because clients own
their exit lifecycle UI and a hook cannot portably suppress that UI.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _vaultpath import vault_root  # noqa: E402


STATE_NAME = "kb-session-end-state.json"


@dataclass(frozen=True)
class Job:
    script: str
    args: tuple[str, ...] = ()
    timeout: int = 30


@dataclass
class Result:
    script: str
    returncode: int = 0
    stderr: str = ""
    error: str = ""


def _vault() -> Path:
    return vault_root()


def run_child(job: Job, scripts: Path, payload: bytes) -> Result:
    try:
        proc = subprocess.run(
            [sys.executable, str(scripts / job.script), *job.args],
            input=payload,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=job.timeout,
            check=False,
        )
        return Result(
            script=job.script,
            returncode=proc.returncode,
            stderr=proc.stderr.decode("utf-8", errors="replace").strip(),
        )
    except subprocess.TimeoutExpired:
        return Result(job.script, error=f"timed out after {job.timeout}s")
    except (OSError, subprocess.SubprocessError) as exc:
        return Result(job.script, error=f"could not run: {exc}")


def run_parallel(
    jobs: tuple[Job, ...],
    scripts: Path,
    payload: bytes,
    runner: Callable[[Job, Path, bytes], Result] = run_child,
) -> list[Result]:
    if not jobs:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(runner, job, scripts, payload) for job in jobs]
        return [future.result() for future in futures]


def _issue(result: Result) -> str:
    if result.error:
        return f"{result.script}: {result.error}"
    if result.returncode:
        detail = f": {result.stderr}" if result.stderr else ""
        return f"{result.script}: exited with status {result.returncode}{detail}"
    # Exit children are independently fail-open and therefore may report a real
    # failure on stderr while still returning zero.
    if result.stderr:
        return f"{result.script}: {result.stderr}"
    return ""


def _write_state(vault: Path, client: str, issues: list[str]) -> None:
    path = vault / ".claude" / STATE_NAME
    temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(
            json.dumps(
                {
                    "completed_at": time.time(),
                    "client": client,
                    "ok": not issues,
                    "issues": issues,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temp, path)
    except OSError:
        try:
            temp.unlink()
        except OSError:
            pass


def coordinate(
    client: str,
    vault: Path,
    payload: bytes,
    *,
    runner: Callable[[Job, Path, bytes], Result] = run_child,
) -> list[str]:
    """Run capture, then independent post-capture work, and return issues."""
    scripts = vault / ".claude" / "scripts"
    if client == "copilot":
        capture = (Job("kb-copilot-capture.py", ("--event", "sessionEnd")),)
        after = (
            Job("import-copilot.py", ("--include-active",), 60),
            Job("kb-usage-scan.py"),
        )
    else:
        capture = (Job("archive-transcript.py"),)
        after = (Job("kb-usage-scan.py"),)

    results = run_parallel(capture, scripts, payload, runner)
    results.extend(run_parallel(after, scripts, payload, runner))
    issues = [issue for result in results if (issue := _issue(result))]
    _write_state(vault, client, issues)
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--client",
        choices=("claude", "codex", "copilot"),
        default="codex",
    )
    parser.add_argument(
        "--diagnostic-json",
        action="store_true",
        help="print the aggregate result for an explicit diagnostic run",
    )
    try:
        args, _unknown = parser.parse_known_args(argv)
        try:
            payload = sys.stdin.buffer.read()
        except OSError:
            payload = b""
        issues = coordinate(args.client, _vault(), payload)
        if args.diagnostic_json:
            sys.stdout.write(json.dumps({"ok": not issues, "issues": issues}))
    except Exception:
        # Agent shutdown must never depend on KennisBank.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

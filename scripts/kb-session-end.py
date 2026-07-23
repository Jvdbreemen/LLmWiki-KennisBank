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
LOG_NAME = "kb-session-end.log"
LOG_MAX_BYTES = 256 * 1024


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
    duration: float = 0.0


def _vault() -> Path:
    return vault_root()


def run_child(job: Job, scripts: Path, payload: bytes) -> Result:
    started = time.monotonic()
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
            duration=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired:
        return Result(
            job.script,
            error=f"timed out after {job.timeout}s",
            duration=time.monotonic() - started,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Result(
            job.script,
            error=f"could not run: {exc}",
            duration=time.monotonic() - started,
        )


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


def _log(vault: Path, message: str) -> None:
    """Append one diagnostic line. Never raises: shutdown must not depend on it.

    A cancelled hook writes no completion state, so without this log a killed run
    leaves no trace at all and cannot be diagnosed afterwards.
    """
    try:
        path = vault / ".claude" / LOG_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if path.stat().st_size > LOG_MAX_BYTES:
                tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
                path.write_text("\n".join(tail) + "\n", encoding="utf-8")
        except OSError:
            pass
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} pid={os.getpid()} {message}\n")
    except Exception:
        pass


def _transcript_path(payload: bytes) -> str:
    """Best-effort transcript path from the hook payload, for later recovery."""
    try:
        data = json.loads(payload.decode("utf-8", errors="replace") or "{}")
    except (ValueError, AttributeError):
        return ""
    if not isinstance(data, dict):
        return ""
    value = data.get("transcript_path") or ""
    return value if isinstance(value, str) else ""


def _write_state(
    vault: Path,
    client: str,
    issues: list[str] | None = None,
    *,
    started_at: float | None = None,
    transcript_path: str = "",
) -> None:
    """Write the run state.

    Called twice: once with issues=None before any work (so a run that is
    cancelled mid-flight leaves a 'running' record), and once on completion.
    """
    path = vault / ".claude" / STATE_NAME
    temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    try:
        now = time.time()
        if issues is None:
            state = {
                "status": "running",
                "started_at": now,
                "client": client,
                "pid": os.getpid(),
                # Kept so a killed run can still be recovered at the next session
                # start: the payload is gone by then, the path is not.
                "transcript_path": transcript_path,
            }
        else:
            state = {
                "status": "completed",
                "completed_at": now,
                "client": client,
                "ok": not issues,
                "issues": issues,
            }
            if started_at is not None:
                state["started_at"] = started_at
                state["duration_s"] = round(now - started_at, 3)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
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

    started_at = time.time()
    budget = max((job.timeout for job in capture), default=0) + max(
        (job.timeout for job in after), default=0
    )
    _write_state(vault, client, None, transcript_path=_transcript_path(payload))
    _log(vault, f"start client={client} worst_case_budget={budget}s")

    results = run_parallel(capture, scripts, payload, runner)
    results.extend(run_parallel(after, scripts, payload, runner))

    for result in results:
        outcome = result.error or (
            f"exit={result.returncode}" if result.returncode else "ok"
        )
        _log(vault, f"job {result.script} {result.duration:.2f}s {outcome}")

    issues = [issue for result in results if (issue := _issue(result))]
    _write_state(vault, client, issues, started_at=started_at)
    _log(
        vault,
        f"done client={client} {time.time() - started_at:.2f}s "
        f"ok={not issues} issues={len(issues)}",
    )
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

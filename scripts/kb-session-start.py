#!/usr/bin/env python3
"""Coordinate KennisBank SessionStart work behind one client hook.

Independent maintenance jobs run concurrently. Work with a data dependency runs
in deterministic phases, and all actionable results are folded into one
client-native context payload. The coordinator is stdlib-only and always fails
open.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _vaultpath import vault_root  # noqa: E402


FRESHNESS_SECONDS = 300
LOCK_STALE_SECONDS = 600
STATE_NAME = "kb-session-start-state.json"
LOCK_NAME = ".kb-session-start.lock"


@dataclass(frozen=True)
class Job:
    script: str
    args: tuple[str, ...] = ()
    timeout: int = 180


@dataclass
class Result:
    script: str
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    error: str = ""


MAINTENANCE = (
    Job("build-embed-index.py"),
    Job("build-kb-index.py"),
    Job("build-activity-index.py"),
    Job("sweep-launch.py", timeout=30),
)
NOTIFICATIONS = (
    Job("memory-notify.py", timeout=30),
    Job("distill-notify.py", timeout=30),
)


def _vault() -> Path:
    return vault_root()


def _changed_count(text: str, pattern: str) -> int:
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _context_text(text: str) -> str:
    """Extract useful text from a child hook's structured output."""
    stripped = text.strip()
    if not stripped:
        return ""
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    if not isinstance(payload, dict):
        return stripped
    direct = payload.get("additionalContext")
    if isinstance(direct, str):
        return direct.strip()
    nested = payload.get("hookSpecificOutput")
    if isinstance(nested, dict) and isinstance(nested.get("additionalContext"), str):
        return nested["additionalContext"].strip()
    return stripped


def relevant_report(result: Result) -> str:
    """Keep changes, warnings and failures; discard routine no-change output."""
    out = _context_text(result.stdout)
    err = result.stderr.strip()
    if result.error:
        return f"{result.script}: {result.error}"

    actionable_err = bool(re.search(
        r"\b(?:error|failed|failure|warning|warn|fout|mislukt|traceback|"
        r"timed out)\b",
        err,
        re.IGNORECASE,
    ))
    relevant = actionable_err or result.returncode != 0
    if result.script == "build-embed-index.py":
        relevant = relevant or _changed_count(out, r"(\d+)\s+\(re\)embedded") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+failed") > 0
    elif result.script == "build-kb-index.py":
        relevant = relevant or _changed_count(out, r"(\d+)\s+\(re\)indexed") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+verwijderd") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+removed") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+failed") > 0
    elif result.script == "build-activity-index.py":
        relevant = relevant or _changed_count(out, r"(\d+)\s+changed") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+failed") > 0
    elif result.script in {"import-copilot.py", "kb-copilot-capture.py", "sweep-launch.py"}:
        # These are side-effect jobs; successful routine output is not context.
        relevant = relevant or result.returncode != 0
    else:
        relevant = relevant or bool(out) or result.returncode != 0

    if not relevant:
        return ""
    parts = [part for part in (out, err if actionable_err else "") if part]
    if result.returncode:
        parts.append(f"exited with status {result.returncode}")
    details = "\n".join(parts)
    return f"{result.script}: {details}".strip()


def run_child(job: Job, scripts: Path, payload: bytes) -> Result:
    try:
        proc = subprocess.run(
            [sys.executable, str(scripts / job.script), *job.args],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=job.timeout,
            check=False,
        )
        return Result(
            script=job.script,
            stdout=proc.stdout.decode("utf-8", errors="replace"),
            stderr=proc.stderr.decode("utf-8", errors="replace"),
            returncode=proc.returncode,
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
        # Preserve declared order even though execution is concurrent.
        return [future.result() for future in futures]


def _read_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def is_fresh(state_path: Path, now: float | None = None) -> bool:
    state = _read_state(state_path)
    completed = state.get("completed_at")
    if not isinstance(completed, (int, float)):
        return False
    return (time.time() if now is None else now) - float(completed) < FRESHNESS_SECONDS


def acquire_lock(path: Path, now: float | None = None) -> bool:
    current = time.time() if now is None else now
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            age = current - path.stat().st_mtime
            if age <= LOCK_STALE_SECONDS:
                return False
            path.unlink()
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except (FileExistsError, FileNotFoundError, OSError):
            return False
    except OSError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"pid": os.getpid(), "started_at": current}, handle)
    return True


def _write_state(path: Path, client: str) -> None:
    temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    try:
        temp.write_text(
            json.dumps(
                {"completed_at": time.time(), "client": client},
                ensure_ascii=False,
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


def _emit(client: str, report: str) -> None:
    if not report:
        return
    context = (
        "KennisBank session report (only changes or actions):\n"
        f"{report}\n"
        "Briefly tell the user what changed or what action is useful. Do not "
        "repeat routine hook or implementation details."
    )
    if client == "claude":
        payload = {
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            },
        }
    elif client == "copilot":
        payload = {"additionalContext": context}
    else:
        payload = {"suppressOutput": True, "additionalContext": context}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


def coordinate(
    client: str,
    vault: Path,
    payload: bytes,
    *,
    runner: Callable[[Job, Path, bytes], Result] = run_child,
    now: float | None = None,
) -> str:
    """Run one deterministic SessionStart cycle and return an aggregate report."""
    scripts = vault / ".claude" / "scripts"
    runtime = vault / ".claude"
    state_path = runtime / STATE_NAME
    lock_path = runtime / LOCK_NAME

    always: list[Result] = []
    if client == "copilot":
        always.extend(run_parallel(
            (Job("kb-copilot-capture.py", ("--event", "sessionStart"), 30),),
            scripts,
            payload,
            runner,
        ))

    if is_fresh(state_path, now=now):
        return "\n".join(filter(None, (relevant_report(r) for r in always)))
    if not acquire_lock(lock_path, now=now):
        return "\n".join(filter(None, (relevant_report(r) for r in always)))

    results = list(always)
    try:
        if client == "copilot":
            results.extend(run_parallel(
                (Job("import-copilot.py", timeout=60),),
                scripts,
                payload,
                runner,
            ))
        results.extend(run_parallel(MAINTENANCE, scripts, payload, runner))
        # Notifications observe the maintenance phase's completed state.
        results.extend(run_parallel(NOTIFICATIONS, scripts, payload, runner))
        _write_state(state_path, client)
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass
    return "\n".join(filter(None, (relevant_report(r) for r in results)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--client", choices=("claude", "codex", "copilot"), default="codex")
    try:
        args, _unknown = parser.parse_known_args(argv)
        try:
            payload = sys.stdin.buffer.read()
        except OSError:
            payload = b""
        report = coordinate(args.client, _vault(), payload)
        _emit(args.client, report)
    except Exception:
        # Session startup and agent operation must never depend on KennisBank.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

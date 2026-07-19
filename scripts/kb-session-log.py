#!/usr/bin/env python3
"""Run deterministic post-save work for the native sessielog workflow.

The agent remains responsible for writing and curating the semantic session log
and wiki changes. This helper coordinates only mechanical follow-up work.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _vaultpath import vault_root  # noqa: E402


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


INDEX_JOBS = (
    Job("build-karpathy-index.py", ("--force",)),
    Job("build-embed-index.py"),
    Job("build-kb-index.py"),
    Job("build-activity-index.py"),
    Job("sweep-launch.py", timeout=30),
)
NOTIFICATION_JOBS = (
    Job("memory-notify.py", timeout=30),
    Job("distill-notify.py", timeout=30),
)


def _vault() -> Path:
    return vault_root()


def run_child(job: Job, scripts: Path) -> Result:
    try:
        proc = subprocess.run(
            [sys.executable, str(scripts / job.script), *job.args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=job.timeout,
            check=False,
        )
        return Result(
            script=job.script,
            stdout=proc.stdout.decode("utf-8", errors="replace").strip(),
            stderr=proc.stderr.decode("utf-8", errors="replace").strip(),
            returncode=proc.returncode,
        )
    except subprocess.TimeoutExpired:
        return Result(job.script, error=f"timed out after {job.timeout}s")
    except (OSError, subprocess.SubprocessError) as exc:
        return Result(job.script, error=f"could not run: {exc}")


def run_parallel(
    jobs: tuple[Job, ...],
    scripts: Path,
    runner: Callable[[Job, Path], Result] = run_child,
) -> list[Result]:
    if not jobs:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(runner, job, scripts) for job in jobs]
        return [future.result() for future in futures]


def _count(text: str, pattern: str) -> int:
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _context_text(text: str) -> str:
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
    if result.error:
        return f"{result.script}: {result.error}"
    out = _context_text(result.stdout)
    actionable_err = bool(re.search(
        r"\b(?:error|failed|failure|warning|warn|fout|mislukt|traceback|"
        r"timed out)\b",
        result.stderr,
        re.IGNORECASE,
    ))
    relevant = actionable_err or result.returncode != 0
    if result.script == "build-embed-index.py":
        relevant = relevant or _count(out, r"(\d+)\s+\(re\)embedded") > 0
    elif result.script == "build-kb-index.py":
        relevant = relevant or _count(out, r"(\d+)\s+\(re\)indexed") > 0
        relevant = relevant or _count(out, r"(\d+)\s+(?:removed|verwijderd)") > 0
    elif result.script == "build-activity-index.py":
        relevant = relevant or _count(out, r"(\d+)\s+changed") > 0
    elif result.script == "sweep-launch.py":
        relevant = relevant or result.returncode != 0
    else:
        relevant = relevant or bool(out)
    if not relevant:
        return ""
    details = "\n".join(
        part for part in (out, result.stderr if actionable_err else "") if part
    )
    if result.returncode:
        details = f"{details}\nexited with status {result.returncode}".strip()
    return f"{result.script}: {details}".strip()


def _validate_session_log(vault: Path, value: str) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(value))).resolve()
    root = (vault / "01-raw" / "sessies").resolve()
    if not path.is_file() or root not in path.parents:
        raise ValueError("session log must exist below <vault>/01-raw/sessies")
    return path


def coordinate(
    vault: Path,
    session_log: str,
    *,
    runner: Callable[[Job, Path], Result] = run_child,
) -> str:
    _validate_session_log(vault, session_log)
    scripts = vault / ".claude" / "scripts"
    results = run_parallel(INDEX_JOBS, scripts, runner)
    # Notices observe the completed indexes.
    results.extend(run_parallel(NOTIFICATION_JOBS, scripts, runner))
    return "\n".join(filter(None, (relevant_report(result) for result in results)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-log", required=True)
    parser.add_argument("--json", action="store_true")
    try:
        args = parser.parse_args(argv)
        report = coordinate(_vault(), args.session_log)
        if args.json:
            sys.stdout.write(json.dumps({"ok": True, "report": report}))
        elif report:
            print(report)
        else:
            print("KennisBank session log indexed; no follow-up action is needed.")
    except Exception as exc:
        # The semantic log is already saved; mechanical follow-up must not make
        # the agent report the whole workflow as failed.
        if "--json" in (argv if argv is not None else sys.argv[1:]):
            sys.stdout.write(json.dumps({"ok": False, "report": str(exc)}))
        else:
            print(f"KennisBank session-log follow-up skipped: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

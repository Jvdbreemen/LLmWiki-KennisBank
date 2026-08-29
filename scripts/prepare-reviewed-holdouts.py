#!/usr/bin/env python3
"""Promote interactive reviews into private source and experience inputs."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _reviewed_holdouts as reviewed  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[1]


def _jsonl(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid review JSON on line {line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"review line {line_number} must be an object")
        rows.append(row)
    return rows


def _states(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and isinstance(value.get("states"), dict):
        value = value["states"]
    if not isinstance(value, dict):
        raise ValueError("experience states must be a JSON object")
    return {str(key): str(state) for key, state in value.items()}


def _outside_repo(path: Path) -> None:
    target = path.resolve()
    try:
        target.relative_to(REPO_ROOT)
    except ValueError:
        return
    raise ValueError("private holdouts must be written outside the repository")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8")
    os.replace(temporary, path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", required=True, type=Path)
    parser.add_argument("--experience-states", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--include-source-negative-experience-probes",
                        action="store_true")
    args = parser.parse_args(argv)
    try:
        _outside_repo(args.output_dir)
        rows = _jsonl(args.reviews)
        source_cases = reviewed.prepare_source_cases(rows)
        experience_cases = reviewed.prepare_experience_cases(
            rows, states=_states(args.experience_states))
        if args.include_source_negative_experience_probes:
            experience_cases.extend(
                reviewed.prepare_experience_negative_probes(source_cases))
        _write_jsonl(args.output_dir / "source-cases.jsonl", source_cases)
        _write_jsonl(args.output_dir / "experience-cases.jsonl", experience_cases)
        print(json.dumps({
            "status": "ok",
            "counts": {"source": len(source_cases),
                       "experience": len(experience_cases)},
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, sort_keys=True),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Promote interactive reviews into private source and experience inputs."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(str(__import__("pathlib").Path(__file__).resolve().parents[1]))  # shipped scripts/; dev tools live in scripts/dev/
import _reviewed_holdouts as reviewed  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _state_bundle(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {"states": {}, "attempt_states": {}, "resolution_states": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("experience states must be a JSON object")
    if not isinstance(value.get("states"), dict):
        return {
            "states": {str(key): str(state) for key, state in value.items()},
            "attempt_states": {},
            "resolution_states": {},
        }
    result = {}
    for key in ("states", "attempt_states", "resolution_states"):
        mapping = value.get(key) or {}
        if not isinstance(mapping, dict):
            raise ValueError(f"experience {key} must be a JSON object")
        result[key] = {str(case_id): str(state)
                       for case_id, state in mapping.items()}
    return result


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
        state_bundle = _state_bundle(args.experience_states)
        experience_cases = reviewed.prepare_experience_cases(
            rows, states=state_bundle["states"],
            attempt_states=state_bundle["attempt_states"],
            resolution_states=state_bundle["resolution_states"])
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

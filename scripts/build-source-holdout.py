#!/usr/bin/env python3
"""Freeze reviewed source cases without copying raw source content."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _source_holdout import freeze_manifest  # noqa: E402


def _read_cases(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        value = json.loads(raw)
        if not isinstance(value, list):
            raise ValueError("JSON holdout input must be an array")
        return value
    cases = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on holdout input line {line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"holdout input line {line_number} must be an object")
        cases.append(value)
    return cases


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path,
                        help="reviewed JSON or JSONL cases kept inside the local boundary")
    parser.add_argument("--output", required=True, type=Path,
                        help="versioned JSON manifest path")
    parser.add_argument("--vault", type=Path,
                        help="vault root; defaults to KENNISBANK_VAULT")
    args = parser.parse_args(argv)
    vault = args.vault or Path(os.environ.get("KENNISBANK_VAULT", "."))
    payload = freeze_manifest(_read_cases(args.cases), vault, args.output)
    print(json.dumps({"output": str(args.output), "counts": payload["counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

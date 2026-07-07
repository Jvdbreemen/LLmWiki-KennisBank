#!/usr/bin/env python3
"""Run a hermetic temporal activity recall eval set."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _activity  # noqa: E402


def _load_eval(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("cases", [])
    if not isinstance(data, list):
        raise SystemExit(f"eval set must be a list or object with cases: {path}")
    return [x for x in data if isinstance(x, dict)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.environ.get("KENNISBANK_VAULT", ""))
    ap.add_argument("--set", dest="eval_set", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--threshold", type=float, default=1.0)
    args = ap.parse_args(argv)

    vault = Path(args.vault) if args.vault else _activity.vault_root()
    eval_path = Path(args.eval_set) if args.eval_set else vault / "06-claude" / "kb-activity-eval-set.json"
    if not eval_path.is_file():
        fallback = Path(__file__).resolve().parents[1] / "kb-activity-eval-set.example.json"
        if fallback.is_file():
            eval_path = fallback
        else:
            raise SystemExit(f"eval set not found: {eval_path}")
    cases = _load_eval(eval_path)
    result = _activity.eval_queries(vault, cases)
    pass_rate = result["metrics"]["case_pass_rate"]
    result["threshold"] = args.threshold
    result["eval_set"] = str(eval_path)
    result["ok"] = result["ok"] and pass_rate >= args.threshold
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            f"temporal eval: {result['passed']}/{result['total']} passed "
            f"(threshold {args.threshold:.2f}, pass_rate {pass_rate:.2f})"
        )
        for case in result["cases"]:
            status = "PASS" if case["ok"] else "FAIL"
            print(f"- {status} {case['id']}: {case['events']} events")
            for warning in case.get("warnings", []):
                print(f"  WARN: {warning}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

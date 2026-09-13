#!/usr/bin/env python3
"""Record private owner-canary verdicts and emit content-free aggregates."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _projection_canary as canary  # noqa: E402


def _vault() -> Path:
    raw = str(os.environ.get("KENNISBANK_VAULT") or "").strip()
    if not raw:
        raise ValueError("KENNISBANK_VAULT is required")
    return Path(raw).resolve()


def default_log_path() -> Path:
    return (_vault() / "06-claude" / "evaluations" / "production-canary" /
            "source-experience-canary.jsonl")


def _private_path(value: str | Path | None) -> Path:
    path = Path(value).resolve() if value else default_log_path()
    if not path.is_relative_to(_vault()):
        raise ValueError("canary files must stay inside KENNISBANK_VAULT")
    return path


def _yes_no(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"yes", "true", "1", "y"}:
        return True
    if normalized in {"no", "false", "0", "n"}:
        return False
    raise argparse.ArgumentTypeError("expected yes or no")


def _common(subparser, *, routes: tuple[str, ...]) -> None:
    subparser.add_argument("--id", required=True)
    subparser.add_argument("--observed-at", required=True)
    subparser.add_argument("--status", required=True,
                           choices=("ok", "no_hit", "evidence_unavailable"))
    subparser.add_argument("--route", required=True, choices=routes)
    subparser.add_argument("--shown-count", required=True, type=int)
    subparser.add_argument("--latency-ms", required=True, type=float)
    subparser.add_argument("--owner-reviewed", required=True, type=_yes_no)
    subparser.add_argument("--candidate-leakage", required=True, type=int)
    subparser.add_argument("--idempotency-key", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", help="private JSONL path inside KENNISBANK_VAULT")
    commands = parser.add_subparsers(dest="command", required=True)

    source = commands.add_parser("record-source")
    _common(source, routes=("exact_ref", "lexical_fts"))
    source.add_argument("--reconstruction-correct", required=True, type=_yes_no)
    source.add_argument("--provenance-correct", required=True, type=_yes_no)

    experience = commands.add_parser("record-experience")
    _common(experience, routes=("hybrid", "lexical_fallback"))
    experience.add_argument("--natural-explicit-use", required=True, type=_yes_no)
    experience.add_argument("--useful", required=True, type=_yes_no)
    experience.add_argument("--harmful", required=True, type=_yes_no)
    experience.add_argument("--evidence-correct", required=True, type=_yes_no)

    report = commands.add_parser("report")
    report.add_argument("--output", help="optional aggregate JSON inside the vault")
    return parser


def _record(args) -> dict:
    common = {
        "schema_version": canary.SCHEMA_VERSION,
        "canary_id": args.id,
        "layer": "source" if args.command == "record-source" else "experience",
        "route": args.route,
        "observed_at": args.observed_at,
        "result_status": args.status,
        "shown_count": args.shown_count,
        "latency_ms": args.latency_ms,
        "owner_reviewed": args.owner_reviewed,
        "candidate_leakage": args.candidate_leakage,
        "idempotency_key": args.idempotency_key,
    }
    if args.command == "record-source":
        common.update({
            "reconstruction_correct": args.reconstruction_correct,
            "provenance_correct": args.provenance_correct,
        })
    else:
        common.update({
            "natural_explicit_use": args.natural_explicit_use,
            "useful": args.useful,
            "harmful": args.harmful,
            "evidence_correct": args.evidence_correct,
        })
    appended = canary.append_record(_private_path(args.log), common)
    return {"schema_version": canary.SCHEMA_VERSION, "appended": appended,
            "layer": common["layer"]}


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    log = _private_path(args.log)
    if args.command in {"record-source", "record-experience"}:
        result = _record(args)
    else:
        result = canary.aggregate(canary.load_records(log))
        if args.output:
            output = _private_path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = output.with_name(output.name + ".tmp")
            temporary.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            os.replace(temporary, output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

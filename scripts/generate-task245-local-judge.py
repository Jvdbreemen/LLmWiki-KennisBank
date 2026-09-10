"""Generate a private local answerability score map for TASK-245.

The judge is deliberately an evaluation arm, not an advisory route.  It sees
the user query and content-only candidate records, never provenance or review
metadata, and it must answer every candidate.  Any malformed or unavailable
response makes the case unavailable; it is never scored as a negative hit.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "evaluate-experience-applicability.py"
spec = importlib.util.spec_from_file_location("task245_applicability", RUNNER_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"cannot load {RUNNER_PATH}")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


SYSTEM = """You are a strict applicability classifier for an offline evaluation.
Do not answer the user's question and do not invent facts. For each candidate,
return true only when that candidate directly covers the same problem, goal,
or outcome asked about. Shared technology words are insufficient. A related
but unsupported quantity, operation, platform, or outcome is false. Return
only one JSON object mapping every candidate ID to a JSON boolean."""


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prompt_for(case: dict, records: list[dict]) -> str:
    lines = [
        "Classify applicability for this query:",
        f"QUERY: {case['query']}",
        "",
        "Candidates (classify every ID exactly once):",
    ]
    for record in records:
        lines.append(f"ID: {runner._record_id(record)}")
        lines.append(runner.scoring_text(record))
        lines.append("")
    lines.append("Return JSON only, with boolean values, for these exact IDs.")
    return "\n".join(lines)


def run(cases, records, *, model="qwen3.5:4b", endpoint="http://localhost:11434",
        timeout=120.0):
    runner.validate_cases(cases, records)
    import _llm
    if not _llm.is_local() or not _llm._endpoint("ollama").startswith(("http://localhost", "http://127.0.0.1")):
        raise ValueError("local Ollama must be the configured first provider")
    ids = [runner._record_id(record) for record in records]
    scores, failures, timings = {}, [], []
    for case in cases:
        started = time.perf_counter()
        raw = _llm._call("ollama", model, endpoint, "", prompt_for(case, records),
                          SYSTEM, timeout)
        timings.append((time.perf_counter() - started) * 1000)
        if not raw:
            failures.append({"case_id": case["id"], "reason": "empty_judgment"})
            continue
        try:
            values = runner.parse_judgments(raw, ids)
        except ValueError as exc:
            failures.append({"case_id": case["id"],
                             "reason": "invalid_judgment",
                             "error": str(exc)})
            continue
        scores[case["id"]] = dict(zip(ids, values))
    return scores, {"model": model, "cases": len(cases),
                    "completed": len(scores), "failed": failures,
                    "p95_ms": sorted(timings)[max(0, round(len(timings) * .95) - 1)]
                    if timings else None,
                    "mean_ms": sum(timings) / len(timings) if timings else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--endpoint", default="http://localhost:11434")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        raise ValueError("timeout must be positive")
    output = runner.validate_private_output(args.output)
    metadata_path = output.with_name(output.stem + "-metadata.json")
    if metadata_path.exists():
        raise ValueError("refusing to overwrite score metadata")
    cases = runner._read_jsonl(args.cases)
    records = runner._read_records(args.records)
    scores, info = run(cases, records, model=args.model, endpoint=args.endpoint,
                       timeout=args.timeout)
    output.write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    metadata = {"schema_version": 1,
                "input_sha256": {"cases": _sha(args.cases), "records": _sha(args.records)},
                "system_prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
                "offline_only": True, **info}
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=2))
    return 0 if not info["failed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Evaluate experience applicability and abstention on a frozen fixture split.

This is an experiment runner, not a production recall policy.  It deliberately
keeps the corpus, labels, scoring text, and policy selection separate:

* development data may select a threshold;
* a sealed holdout may only be opened after that policy is hashed;
* no source passage, review state, or private path is sent to a scorer;
* an unavailable scorer is a failure, never a correct abstention.

The default ``lexical`` arm is dependency-free.  Other arms can be supplied by
the caller as a JSON score map, which keeps model-specific experiments private
and prevents a model dependency from becoming a production dependency merely
because it was useful in one evaluation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

_FIELDS = (
    "situation", "goal", "approach", "action", "observed_result",
    "lesson", "applicability",
)


def _load_helper():
    path = SCRIPTS / "_experience_applicability.py"
    spec = importlib.util.spec_from_file_location("_experience_applicability", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scoring_text(record: dict) -> str:
    """Return an unambiguous, content-only representation of a record.

    Field labels and length-prefixed values prevent accidental concatenation
    collisions (``ab`` + ``c`` versus ``a`` + ``bc``).  Provenance, lifecycle,
    confidence, and review fields are intentionally not represented.
    """
    if not isinstance(record, dict):
        raise ValueError("record must be an object")
    parts = []
    for field in _FIELDS:
        value = str(record.get(field) or "")
        parts.append(f"{field}[{len(value)}]={value}")
    return "\n".join(parts)


def _loads_no_duplicates(raw: str):
    duplicates = []

    def hook(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                duplicates.append(str(key))
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except json.JSONDecodeError as exc:
        raise ValueError("judge output is not valid JSON") from exc
    if duplicates:
        raise ValueError("judge output contains duplicate keys")
    return value


def parse_judgments(raw: str, candidate_ids: list[str]) -> list[float]:
    """Parse an exact id -> boolean answerability map.

    Every candidate must occur exactly once and values must be JSON booleans.
    Numeric values, strings, and missing/extra candidates are rejected rather
    than silently converted into labels.
    """
    value = _loads_no_duplicates(raw)
    if not isinstance(value, dict):
        raise ValueError("judge output must be a JSON object")
    expected = [str(item) for item in candidate_ids]
    if len(set(expected)) != len(expected):
        raise ValueError("candidate IDs must be unique")
    if set(value) != set(expected) or len(value) != len(expected):
        raise ValueError("judge output must cover candidates exactly")
    if any(type(value[key]) is not bool for key in expected):
        raise ValueError("judge values must be booleans")
    return [1.0 if value[key] else 0.0 for key in expected]


def validate_cases(cases: list[dict], records: list[dict]) -> None:
    """Validate labels and corpus membership before any scoring call."""
    if not cases or not records:
        raise ValueError("nonempty cases and records are required")
    record_ids = [str(row.get("experience_id") or row.get("id") or "")
                  for row in records]
    if any(not item for item in record_ids) or len(set(record_ids)) != len(record_ids):
        raise ValueError("record IDs must be nonempty and unique")
    ids = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each case must be an object")
        case_id = str(case.get("id") or "")
        query = str(case.get("query") or "").strip()
        if not case_id or not query:
            raise ValueError("each case requires a nonempty id and query")
        if case_id in ids:
            raise ValueError("case IDs must be unique")
        ids.append(case_id)
        expected = case.get("expected_experience")
        if expected is not None and str(expected) not in record_ids:
            raise ValueError("expected experience is missing from fixture corpus")
        if "polarity" in case:
            polarity = case["polarity"]
            if polarity not in {"positive", "negative"}:
                raise ValueError("invalid case polarity")
            if (polarity == "positive") != (expected is not None):
                raise ValueError("case polarity and expected experience disagree")


def _record_id(record: dict) -> str:
    return str(record.get("experience_id") or record.get("id") or "")


def _finite(value) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("scores must be finite")
    return result


def observations_from_scores(cases: list[dict], records: list[dict], scores: dict) -> list[dict]:
    """Convert a complete case x corpus score map to helper observations."""
    validate_cases(cases, records)
    record_ids = [_record_id(row) for row in records]
    case_ids = [case["id"] for case in cases]
    if set(scores) not in (set(record_ids), set(case_ids)):
        raise ValueError("score map must cover either cases or the corpus exactly")
    if set(scores) == set(case_ids) and any(not isinstance(item, dict)
                                            for item in scores.values()):
        raise ValueError("per-case score map must contain objects")
    rows = []
    for case in cases:
        case_scores = scores_for_case(scores, case["id"], record_ids)
        rows.append({"id": case["id"],
                     "expected_experience": case.get("expected_experience"),
                     "candidates": [{"id": rid, "score": _finite(value)}
                                    for rid, value in zip(record_ids, case_scores)],
                     "status": "ok"})
    return rows


def scores_for_case(scores: dict, case_id: str, record_ids: list[str]) -> list[float]:
    """Accept either ``{record_id: score}`` or ``{case_id: {record_id: score}}``."""
    value = scores.get(case_id)
    if isinstance(value, dict):
        if set(value) != set(record_ids):
            raise ValueError("per-case score map must cover the corpus exactly")
        return [_finite(value[key]) for key in record_ids]
    if any(isinstance(item, dict) for item in scores.values()):
        raise ValueError("score map is missing a case")
    return [_finite(scores[key]) for key in record_ids]


def lexical_scores(cases: list[dict], records: list[dict]) -> dict:
    helper = _load_helper()
    corpus = {_record_id(record): record for record in records}
    return {case["id"]: {rid: helper.lexical_score(case["query"], record)
                          for rid, record in corpus.items()}
            for case in cases}


def _retrieval_text(record: dict) -> str:
    return " ".join(str(record.get(field) or "") for field in _FIELDS)


def _cosine(left, right) -> float:
    if not left or not right or len(left) != len(right):
        raise ValueError("embedding dimensions must match")
    left = [float(value) for value in left]
    right = [float(value) for value in right]
    if any(not math.isfinite(value) for value in left + right):
        raise ValueError("embedding values must be finite")
    norm_left = math.sqrt(sum(value * value for value in left))
    norm_right = math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / (norm_left * norm_right) \
        if norm_left and norm_right else 0.0


def embedding_scores(cases: list[dict], records: list[dict], embed) -> tuple[dict, dict]:
    """Compute a local query/document cosine score map for development data.

    ``embed`` is injected so the evaluator can be unit-tested without a model.
    It receives ``kind='query'`` or ``kind='doc'``; callers must ensure that
    the implementation is local before passing private text to it.
    """
    validate_cases(cases, records)
    vectors = {}
    durations = []
    for record in records:
        started = time.perf_counter()
        vector = embed(_retrieval_text(record), kind="doc")
        durations.append((time.perf_counter() - started) * 1000)
        if vector is None:
            raise ValueError(f"missing document embedding for {_record_id(record)}")
        vectors[_record_id(record)] = list(vector)
    dimension = len(next(iter(vectors.values())))
    if not dimension or any(len(vector) != dimension for vector in vectors.values()):
        raise ValueError("document embeddings must have one nonzero dimension")
    result, failures = {}, []
    for case in cases:
        started = time.perf_counter()
        vector = embed(case["query"], kind="query")
        durations.append((time.perf_counter() - started) * 1000)
        if vector is None:
            failures.append({"case_id": case["id"], "reason": "missing_query_embedding"})
            continue
        if len(vector) != dimension:
            raise ValueError(f"query embedding dimension differs for {case['id']}")
        result[case["id"]] = {rid: _cosine(vector, doc_vector)
                               for rid, doc_vector in vectors.items()}
    return result, {"failed": failures, "embedding_calls": len(durations),
                    "p95_ms": sorted(durations)[max(0, math.ceil(len(durations) * .95) - 1)]
                    if durations else None}


def evaluate_arm(cases: list[dict], records: list[dict], score_map: dict,
                 thresholds: list[float], *, min_hit=.85, min_specificity=.90) -> dict:
    helper = _load_helper()
    observations = observations_from_scores(cases, records, score_map)
    selection = helper.select_threshold(observations, thresholds=thresholds,
                                        min_hit=min_hit,
                                        min_specificity=min_specificity)
    selected = selection["selected_threshold"]
    return {"selection": selection,
            "selected": helper.measure(observations, selected)
            if selected is not None else None,
            "observations": observations}


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"expected object at {path}:{line_number}")
        rows.append(row)
    return rows


def _read_records(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("records JSON must be a list of objects")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_private_output(path: Path) -> Path:
    """Require a new output below the configured vault evaluation directory."""
    configured = os.environ.get("KENNISBANK_VAULT", "").strip()
    if not configured:
        raise ValueError("KENNISBANK_VAULT is required for private evaluation output")
    root = (Path(configured).resolve() / "06-claude" / "evaluations").resolve()
    output = Path(path).resolve()
    if output == root or not output.is_relative_to(root) or output.exists():
        raise ValueError("output must be a new directory under the private evaluation vault")
    return output


def _thresholds(start=-1.0, stop=1.0, step=.01) -> list[float]:
    count = round((stop - start) / step)
    return [round(start + index * step, 10) for index in range(count + 1)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scores", type=Path,
                        help="optional private JSON score map; default is lexical")
    parser.add_argument("--cosine-local", action="store_true",
                        help="embed the fixture locally and score query/document cosine")
    parser.add_argument("--arm", default="lexical")
    parser.add_argument("--threshold-start", type=float, default=-1.0)
    parser.add_argument("--threshold-stop", type=float, default=1.0)
    parser.add_argument("--threshold-step", type=float, default=.01)
    parser.add_argument("--min-hit", type=float, default=.85)
    parser.add_argument("--min-specificity", type=float, default=.90)
    args = parser.parse_args(argv)
    cases = _read_jsonl(args.cases)
    records = _read_records(args.records)
    validate_cases(cases, records)
    if args.scores and args.cosine_local:
        parser.error("--scores and --cosine-local are mutually exclusive")
    embedding_info = None
    if args.cosine_local:
        import _embeddings
        provider, _, endpoint, _ = _embeddings._resolve()
        if provider != "ollama" or not _embeddings.is_local_endpoint(endpoint):
            raise ValueError("--cosine-local requires a local Ollama embedding endpoint")
        scores, embedding_info = embedding_scores(
            cases, records,
            lambda text, *, kind: _embeddings.embed(text, timeout=60, kind=kind))
    else:
        scores = (json.loads(args.scores.read_text(encoding="utf-8"))
                  if args.scores else lexical_scores(cases, records))
    result = evaluate_arm(cases, records, scores,
                          _thresholds(args.threshold_start, args.threshold_stop,
                                      args.threshold_step),
                          min_hit=args.min_hit,
                          min_specificity=args.min_specificity)
    output = validate_private_output(args.output_dir)
    output.mkdir(parents=True)
    public = {key: value for key, value in result.items() if key != "observations"}
    public.update({"schema_version": 1, "evaluation_kind": "applicability_development",
                   "arm": args.arm, "case_count": len(cases),
                   "record_count": len(records),
                   "input_sha256": {"cases": _sha(args.cases), "records": _sha(args.records)},
                   "policy": {"min_hit_at_3": args.min_hit,
                              "min_negative_specificity": args.min_specificity},
                   "holdout_opened": False})
    if embedding_info is not None:
        public["embedding"] = embedding_info
    (output / "aggregate.json").write_text(json.dumps(public, indent=2) + "\n",
                                             encoding="utf-8")
    (output / "private-observations.json").write_text(
        json.dumps(result["observations"], indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"arm": args.arm, "selected_threshold":
                      result["selection"]["selected_threshold"],
                      "selected": result["selected"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

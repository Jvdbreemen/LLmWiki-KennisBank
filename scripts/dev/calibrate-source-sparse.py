#!/usr/bin/env python3
"""Select sparse-first source settings on an independent private dev set."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPOSITORY = SCRIPTS.parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.append(str(__import__("pathlib").Path(__file__).resolve().parents[1]))  # shipped scripts/; dev tools live in scripts/dev/

import _source_sparse_eval as sparse  # noqa: E402
import _source_sparse_selection as selection  # noqa: E402

SCHEMA_VERSION = 1
SELECTION_POLICY = "independent_development_only"


def private_path(path: Path) -> Path:
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(REPOSITORY.resolve())
    except ValueError:
        return resolved
    raise ValueError("private source calibration inputs and outputs must remain outside the repository")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _load_cases(path: Path) -> list[dict]:
    target = Path(path)
    raw = target.read_text(encoding="utf-8")
    if target.suffix.casefold() == ".jsonl":
        cases = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid source development JSONL line {line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(
                    f"source development JSONL line {line_number} must be an object")
            cases.append(value)
        return cases
    payload = json.loads(raw)
    if isinstance(payload, dict):
        if payload.get("schema_version") != 1:
            raise ValueError("unsupported source development schema")
        cases = payload.get("cases")
    else:
        cases = payload
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise ValueError("source development input requires a cases array")
    return cases


def load_development_cases(path: Path) -> list[dict]:
    cases = _load_cases(path)
    ids = [str(case.get("id") or "").strip() for case in cases]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("source development cases require unique ids")
    if any(not str(case.get("query") or "").strip() for case in cases):
        raise ValueError("source development cases require queries")
    if any(str(case.get("review_status") or "").casefold() != "reviewed"
           or str(case.get("review_decision") or "").casefold() != "keep"
           for case in cases):
        raise ValueError("source development cases must be owner-reviewed and kept")
    positive = [case for case in cases if case.get("expected_source") is not None]
    negative = [case for case in cases if case.get("expected_source") is None]
    if (len(cases), len(positive), len(negative)) != (30, 20, 10):
        raise ValueError("source development set must contain exactly 20 positive and 10 negative cases")
    if any(not case.get("expected_windows") for case in positive):
        raise ValueError("positive source development cases require reviewed windows")
    if any(not str(case.get("expected_hash") or "").startswith("sha256:")
           or len(str(case.get("expected_hash"))) != 71 for case in positive):
        raise ValueError("positive source development cases require exact sha256 hashes")
    sources = [str(case.get("expected_source")) for case in positive]
    if len(sources) != len(set(sources)):
        raise ValueError("positive source development cases require unique source documents")
    return cases


def load_frozen_cases(path: Path) -> list[dict]:
    cases = _load_cases(path)
    if not cases:
        raise ValueError("frozen source cases are empty")
    return cases


def validate_case_provenance(cases: list[dict], *, vault: Path,
                             source_db: Path) -> None:
    """Fail before calibration when reviewed sources or the FTS snapshot drift."""
    root = Path(vault).resolve()
    uri = Path(source_db).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        for case in cases:
            source_path = case.get("expected_source")
            if source_path is None:
                continue
            case_id = str(case.get("id") or "<unknown>")
            path = (root / Path(str(source_path))).resolve()
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"source development path escapes vault: {case_id}") from exc
            try:
                snapshot = sparse.read_source_snapshot(path)
            except (OSError, UnicodeError) as exc:
                raise ValueError(f"source development file unavailable: {case_id}") from exc
            if snapshot["source_hash"] != case.get("expected_hash"):
                raise ValueError(f"source development hash drift: {case_id}")
            text_length = len(snapshot["text"])
            for window in case.get("expected_windows") or []:
                try:
                    start, end = int(window["start"]), int(window["end"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"source development window invalid: {case_id}") from exc
                if start < 0 or end <= start or end > text_length:
                    raise ValueError(f"source development window invalid: {case_id}")
            row = conn.execute(
                "SELECT body FROM source_fts WHERE source_path=?", (source_path,)
            ).fetchone()
            if row is None:
                raise ValueError(f"source development document absent from FTS: {case_id}")
            indexed_hash = "sha256:" + hashlib.sha256(
                str(row[0]).encode("utf-8")).hexdigest()
            if indexed_hash != snapshot["indexed_body_hash"]:
                raise ValueError(f"source development FTS snapshot stale: {case_id}")
    finally:
        conn.close()


def _counts(cases: list[dict]) -> dict:
    positive = sum(case.get("expected_source") is not None for case in cases)
    return {"total": len(cases), "positive": positive,
            "negative": len(cases) - positive}


def build_selection_report(*, development_sha256: str, frozen_sha256: str,
                           source_db_sha256: str, repository_revision: str,
                           document_model_id: str, query_model_id: str,
                           cases: list[dict], selection_result: dict) -> dict:
    selected = dict(selection_result["selected"])
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "selection_policy": SELECTION_POLICY,
        "development_sha256": development_sha256,
        "frozen_input_sha256": frozen_sha256,
        "source_db_sha256": source_db_sha256,
        "repository_revision": repository_revision,
        "model_ids": {"document": document_model_id, "query": query_model_id},
        "counts": _counts(cases),
        "constraints": dict(selection_result.get("constraints") or {}),
        "development_constraints_pass": bool(
            selection_result.get("development_constraints_pass")),
        "selection_reason": selection_result.get("reason"),
        "trial_count": int(selection_result.get("trial_count") or 0),
        "selected_configuration": dict(selected.get("configuration") or {}),
        "selected_development_metrics": {
            "retrieval": dict(selected.get("retrieval") or {}),
            "passage_hit@5": float(selected.get("passage_hit@5") or 0.0),
            "citation_precision": float(selected.get("citation_precision") or 0.0),
            "provenance_precision": float(selected.get("provenance_precision") or 0.0),
            "no_hit_specificity": float(selected.get("no_hit_specificity") or 0.0),
        },
        "development_warm_latency": dict(selected.get("warm_latency") or {}),
        "selected_cache_bytes": int(selected.get("cache_bytes") or 0),
    }


def _csv_ints(value: str) -> list[int]:
    values = sorted({int(part.strip()) for part in value.split(",") if part.strip()})
    if not values or any(item <= 0 for item in values):
        raise argparse.ArgumentTypeError("positive comma-separated integers required")
    return values


def _csv_floats(value: str) -> list[float]:
    values = sorted({float(part.strip()) for part in value.split(",") if part.strip()})
    if not values or any(item < -1.0 or item > 1.0 for item in values):
        raise argparse.ArgumentTypeError("cosine thresholds must be between -1 and 1")
    return values


def _cache_bytes(path: Path) -> int:
    return sum(candidate.stat().st_size for candidate in (
        path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm"))
               if candidate.exists())


def memoize_embeddings(embed_fn):
    """Reuse exact query embeddings across configurations and warm runs."""
    cache = {}

    def cached(texts: list[str]) -> list[list[float]]:
        keys = list(texts)
        missing = [value for value in dict.fromkeys(keys) if value not in cache]
        if missing:
            vectors = embed_fn(missing)
            if len(vectors) != len(missing):
                raise RuntimeError("embedding backend returned an unexpected vector count")
            cache.update(zip(missing, vectors))
        return [cache[value] for value in keys]

    return cached


def run_trial_grid(cases: list[dict], *, cache_dir: Path,
                   candidate_docs: list[int], max_passages: list[int],
                   min_cos: list[float], base_options: dict) -> list[dict]:
    """Evaluate a grid with one content cache and one exact query cache."""
    shared_cache = Path(cache_dir) / "embeddings.db"
    common = dict(base_options)
    query_embedder = common.get("embed_query_fn")
    if query_embedder is not None:
        common["embed_query_fn"] = memoize_embeddings(query_embedder)
    trials = []
    grid = itertools.product(candidate_docs, max_passages, min_cos)
    for candidate_count, passage_count, cosine_threshold in grid:
        options = dict(common)
        options.update({
            "cache_db": shared_cache,
            "candidate_docs": candidate_count,
            "max_passages": passage_count,
            "min_cos": cosine_threshold,
        })
        measured = sparse.evaluate(cases, **options)
        warm = sparse.evaluate(cases, **options)
        trial = dict(measured)
        trial["warm_latency"] = dict(warm["latency_ms"])
        trials.append(trial)
    shared_bytes = _cache_bytes(shared_cache)
    for trial in trials:
        trial["cache_bytes"] = shared_bytes
    return trials


def _embedding_functions():
    import _embeddings

    def documents(texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = _embeddings.embed(text, kind="doc")
            if vector is None:
                raise RuntimeError("document embedding failed")
            vectors.append(vector)
        return vectors

    def queries(texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = _embeddings.embed_query(text)
            if vector is None:
                raise RuntimeError("query embedding failed")
            vectors.append(vector)
        return vectors

    return _embeddings.embed_id(), documents, queries


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--vault", type=Path)
    parser.add_argument("--candidate-docs", type=_csv_ints,
                        default=_csv_ints("20,50,100"))
    parser.add_argument("--max-passages", type=_csv_ints,
                        default=_csv_ints("40,100"))
    parser.add_argument("--min-cos", type=_csv_floats,
                        default=_csv_floats("0.40,0.55,0.70"))
    parser.add_argument("--chunk-size", type=int, default=2000)
    parser.add_argument("--overlap", type=int, default=200)
    args = parser.parse_args(argv)
    try:
        development_path = private_path(args.development)
        frozen_path = private_path(args.frozen)
        source_db = private_path(args.source_db)
        cache_dir = private_path(args.cache_dir)
        report_path = private_path(args.report)
        vault = (args.vault or Path(os.environ.get("KENNISBANK_VAULT", "."))).resolve()
        cases = load_development_cases(development_path)
        frozen = load_frozen_cases(frozen_path)
        selection.assert_independent_source_cases(cases, frozen)
        if not source_db.is_file():
            raise ValueError("source FTS database does not exist")
        validate_case_provenance(cases, vault=vault, source_db=source_db)
        if report_path.exists():
            raise ValueError("source calibration report already exists")
        cache_dir.mkdir(parents=True, exist_ok=False)
        os.environ["KB_USAGE_DISABLE"] = "1"
        model_id, embed_documents, embed_queries = _embedding_functions()
        trials = run_trial_grid(
            cases, cache_dir=cache_dir,
            candidate_docs=args.candidate_docs,
            max_passages=args.max_passages, min_cos=args.min_cos,
            base_options={
                "vault": vault, "source_db": source_db,
                "embed_fn": embed_documents, "embed_query_fn": embed_queries,
                "model_id": model_id, "document_model_id": model_id,
                "query_model_id": model_id, "chunk_size": args.chunk_size,
                "overlap": args.overlap, "k": 5,
            })
        selected = selection.select_configuration(trials)
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, text=True).strip()
        report = build_selection_report(
            development_sha256=sha256_file(development_path),
            frozen_sha256=sha256_file(frozen_path),
            source_db_sha256=sha256_file(source_db),
            repository_revision=revision,
            document_model_id=model_id, query_model_id=model_id,
            cases=cases, selection_result=selected)
        sparse.write_once_report(report_path, lambda: report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report["development_constraints_pass"] else 2
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)},
                         ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

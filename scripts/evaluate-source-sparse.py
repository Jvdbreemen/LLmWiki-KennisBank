#!/usr/bin/env python3
"""Run the frozen sparse-first source holdout once and report aggregates."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPOSITORY = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _source_sparse_eval as sparse  # noqa: E402

SCHEMA_VERSION = 1
HOLDOUT_POLICY = "frozen_one_shot_no_further_tuning"


def private_path(path: Path) -> Path:
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(REPOSITORY.resolve())
    except ValueError:
        return resolved
    raise ValueError("private source evaluation inputs and outputs must remain outside the repository")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def load_selection(path: Path, *, frozen_sha256: str, source_db_sha256: str,
                   document_model_id: str, query_model_id: str) -> dict:
    selection = json.loads(Path(path).read_text(encoding="utf-8"))
    if (selection.get("schema_version") != 1
            or selection.get("status") != "complete"
            or selection.get("selection_policy") != "independent_development_only"):
        raise ValueError("invalid sparse source development selection")
    expected = {
        "frozen_input_sha256": frozen_sha256,
        "source_db_sha256": source_db_sha256,
    }
    for field, value in expected.items():
        if selection.get(field) != value:
            raise ValueError(f"sparse source selection {field} mismatch")
    model_ids = selection.get("model_ids") or {}
    if model_ids.get("document") != document_model_id:
        raise ValueError("sparse source selection document model mismatch")
    if model_ids.get("query") != query_model_id:
        raise ValueError("sparse source selection query model mismatch")
    configuration = selection.get("selected_configuration")
    warm = selection.get("development_warm_latency")
    required = {"candidate_docs", "max_passages", "chunk_size", "overlap", "k", "min_cos"}
    if not isinstance(configuration, dict) or not required.issubset(configuration):
        raise ValueError("sparse source selection lacks a complete configuration")
    if not isinstance(warm, dict) or "p95_ms" not in warm:
        raise ValueError("sparse source selection lacks development warm latency")
    return selection


def load_cases(path: Path, *, frozen: bool) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if payload.get("schema_version") != 1:
            raise ValueError("unsupported source evaluation schema")
        cases = payload.get("cases")
    else:
        cases = payload
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise ValueError("source evaluation requires a list of case objects")
    ids = [str(case.get("id") or "").strip() for case in cases]
    if any(not case_id for case_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("source evaluation cases require unique ids")
    if any(not str(case.get("query") or "").strip() for case in cases):
        raise ValueError("source evaluation cases require queries")
    positive = [case for case in cases if case.get("expected_source") is not None]
    negative = [case for case in cases if case.get("expected_source") is None]
    if frozen and (len(cases), len(positive), len(negative)) != (60, 50, 10):
        raise ValueError("unexpected frozen source holdout composition")
    for case in positive:
        if not case.get("expected_windows"):
            raise ValueError("positive source case requires reviewed passage windows")
    return cases


def claim_report(path: Path, *, input_sha256: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    marker = {
        "schema_version": SCHEMA_VERSION,
        "status": "running",
        "holdout_policy": HOLDOUT_POLICY,
        "input_sha256": input_sha256,
    }
    try:
        with target.open("x", encoding="utf-8") as handle:
            json.dump(marker, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise ValueError(f"source holdout report already exists: {target}") from exc


def mark_failed(path: Path, *, failure_class: str) -> None:
    """Retain a content-safe spent marker without exception or case text."""
    target = Path(path)
    marker = json.loads(target.read_text(encoding="utf-8"))
    marker.update({"status": "failed", "failure_class": str(failure_class)})
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(
        json.dumps(marker, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.replace(temporary, target)


def run_holdout_once(cases: list[dict], *, evaluator, options: dict) -> dict:
    """Keep the one-shot call boundary explicit and independently testable."""
    return evaluator(cases, **dict(options))


def choose_decision(measured: dict, *, lexical_hit5: float,
                    required_gain: float, minimum_specificity: float,
                    maximum_warm_p95_ms: float) -> dict:
    hit5 = float((measured.get("retrieval") or {}).get("hit@5") or 0.0)
    specificity = float(measured.get("no_hit_specificity") or 0.0)
    p95 = float((measured.get("latency_ms") or {}).get("p95_ms") or 0.0)
    checks = {
        "hit@5_gain": hit5 - float(lexical_hit5) + 1e-12 >= float(required_gain),
        "no_hit_specificity": specificity >= float(minimum_specificity),
        "warm_p95": p95 < float(maximum_warm_p95_ms),
    }
    passes = all(checks.values())
    return {
        "choice": "sparse-first" if passes else "reject",
        "passes": passes,
        "checks": checks,
        "hit@5_delta_vs_lexical": hit5 - float(lexical_hit5),
        "alternatives": {
            "full-vector": "not operationally feasible in this experiment",
            "lexical-only": "baseline only; does not inherit sparse-first approval",
        },
    }


def build_report(*, input_sha256: str, model_id: str, measured: dict,
                 warm_latency: dict,
                 source_db_bytes: int, cache_db_bytes: int,
                 lexical_hit5: float, lexical_index_bytes: int,
                 selection_sha256: str | None = None,
                 source_db_sha256: str | None = None,
                 required_gain: float = 0.10,
                 minimum_specificity: float = 0.95,
                 maximum_warm_p95_ms: float = 2000.0) -> dict:
    decision_input = dict(measured)
    decision_input["latency_ms"] = dict(warm_latency)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "holdout_policy": HOLDOUT_POLICY,
        "input_sha256": input_sha256,
        "selection_sha256": selection_sha256,
        "source_db_sha256": source_db_sha256,
        "model_id": model_id,
        "counts": dict(measured.get("counts") or {}),
        "configuration": dict(measured.get("configuration") or {}),
        "measured": measured,
        "development_warm_latency": dict(warm_latency),
        "costs": {
            "source_fts_bytes": int(source_db_bytes),
            "lexical_index_bytes": int(lexical_index_bytes),
            "on_demand_cache_bytes": int(cache_db_bytes),
            "naive_full_vector_built": False,
        },
        "baseline": {"lexical_hit@5": float(lexical_hit5)},
        "decision": choose_decision(
            decision_input, lexical_hit5=lexical_hit5, required_gain=required_gain,
            minimum_specificity=minimum_specificity,
            maximum_warm_p95_ms=maximum_warm_p95_ms),
    }


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
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--cache-db", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--selection-report", type=Path, required=True)
    parser.add_argument("--vault", type=Path)
    parser.add_argument("--lexical-hit5", type=float, default=0.66)
    parser.add_argument("--confirm-frozen-once", action="store_true")
    args = parser.parse_args(argv)

    try:
        if not args.confirm_frozen_once:
            raise ValueError("frozen source holdout requires --confirm-frozen-once")
        cases_path = private_path(args.cases)
        source_db = private_path(args.source_db)
        cache_db = private_path(args.cache_db)
        report_path = private_path(args.report)
        selection_path = private_path(args.selection_report)
        vault = (args.vault or Path(os.environ.get("KENNISBANK_VAULT", "."))).resolve()
        if not source_db.is_file():
            raise ValueError(f"source FTS database does not exist: {source_db}")
        if cache_db.exists():
            raise ValueError(f"frozen source cache already exists: {cache_db}")
        cases = load_cases(cases_path, frozen=True)
        input_sha256 = sha256_file(cases_path)
        source_db_sha256 = sha256_file(source_db)
        model_id, embed_documents, embed_queries = _embedding_functions()
        selected = load_selection(
            selection_path, frozen_sha256=input_sha256,
            source_db_sha256=source_db_sha256,
            document_model_id=model_id, query_model_id=model_id)
        claim_report(report_path, input_sha256=input_sha256)

        os.environ["KB_USAGE_DISABLE"] = "1"
        configuration = dict(selected["selected_configuration"])
        options = {
            "vault": vault,
            "source_db": source_db,
            "cache_db": cache_db,
            "embed_fn": embed_documents,
            "embed_query_fn": embed_queries,
            "model_id": model_id,
            "document_model_id": model_id,
            "query_model_id": model_id,
            **configuration,
        }
        measured = run_holdout_once(
            cases, evaluator=sparse.evaluate, options=options)
        report = build_report(
            input_sha256=input_sha256,
            model_id=model_id,
            measured=measured,
            warm_latency=selected["development_warm_latency"],
            source_db_bytes=source_db.stat().st_size,
            cache_db_bytes=cache_db.stat().st_size,
            lexical_hit5=args.lexical_hit5,
            lexical_index_bytes=source_db.stat().st_size,
            selection_sha256=sha256_file(selection_path),
            source_db_sha256=source_db_sha256,
        )
        temporary = report_path.with_name(report_path.name + ".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        os.replace(temporary, report_path)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        try:
            if "report_path" in locals() and Path(report_path).exists():
                mark_failed(report_path, failure_class=type(exc).__name__)
        except Exception:
            pass
        print(f"source sparse evaluation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

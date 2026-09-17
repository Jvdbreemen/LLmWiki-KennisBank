#!/usr/bin/env python3
"""Calibrate failure advisories on an independent private development set."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPOSITORY = SCRIPTS.parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.append(str(__import__("pathlib").Path(__file__).resolve().parents[1]))  # shipped scripts/; dev tools live in scripts/dev/

import _advisory_calibration as calibration  # noqa: E402


def validate_cases(cases) -> list[dict]:
    rows = [dict(case) for case in cases]
    if not rows:
        raise ValueError("development set is empty")
    seen = set()
    positives = negatives = 0
    for case in rows:
        case_id = str(case.get("case_id") or case.get("id") or "").strip()
        if not case_id or case_id in seen:
            raise ValueError("development cases require unique ids")
        seen.add(case_id)
        if (case.get("review_status") != "reviewed"
                or case.get("review_decision") != "keep"):
            raise ValueError("all development cases must be reviewed and kept")
        advisory = case.get("expected_advisory") is True
        expected = case.get("expected_experience")
        if advisory:
            positives += 1
            if not isinstance(expected, dict):
                raise ValueError(f"positive case lacks expected experience: {case_id}")
        else:
            negatives += 1
            if expected is not None:
                raise ValueError(f"negative case contains expected experience: {case_id}")
    if not positives or not negatives:
        raise ValueError("development set requires positive and negative cases")
    return rows


def _source_refs(case: dict) -> list[str]:
    refs = []
    for source in case.get("evidence_sources") or []:
        path = str(source.get("path") or "").strip().replace("\\", "/")
        digest = str(source.get("hash") or "").strip()
        if not path or not digest:
            raise ValueError("evidence source requires path and hash")
        for window in source.get("windows") or []:
            start, end = int(window["start"]), int(window["end"])
            if start < 0 or start >= end:
                raise ValueError("invalid evidence window")
            refs.append(f"{path}#{start}:{end}@{digest}")
    if not refs:
        raise ValueError("positive experience requires source evidence")
    return refs


def record_for(case: dict) -> dict | None:
    """Map one reviewed positive case to a private validated experience."""
    if case.get("expected_advisory") is not True:
        return None
    expected = case.get("expected_experience") or {}
    case_id = str(case.get("case_id") or case.get("id") or "").strip()
    failed = str(expected.get("failed_approach") or "").strip()
    action = str(expected.get("recommended_action") or "").strip()
    scope = str(expected.get("scope") or "").strip()
    tradeoff = str(expected.get("tradeoff") or "").strip()
    outcome = str(expected.get("outcome") or "").strip()
    if not all((case_id, failed, action, scope, outcome)):
        raise ValueError(f"incomplete expected experience: {case_id or '<unknown>'}")
    return {
        "experience_id": case_id,
        "session_id": "advisory-development",
        "task_id": case_id,
        "situation": scope,
        "goal": "prevent a repeated failed approach",
        "approach": failed,
        "action": action,
        "observed_result": outcome,
        "lesson": f"Avoid: {failed} Recommended: {action}",
        "applicability": " ".join(part for part in (scope, tradeoff) if part),
        "outcome_state": str(case.get("expected_state") or "unknown"),
        "attempt_state": str(case.get("expected_attempt_state") or "unknown"),
        "resolution_state": str(
            case.get("expected_resolution_state") or "not_applicable"),
        "confidence": 1.0,
        "source_refs": _source_refs(case),
    }


def _lexical_metrics(cases: list[dict], results: list[dict]) -> dict:
    by_id = {str(row.get("id") or ""): row for row in results}
    positives = [case for case in cases if case.get("expected_advisory") is True]
    negatives = [case for case in cases if case.get("expected_advisory") is not True]
    warnings = correct = false_warnings = 0
    for case in cases:
        case_id = str(case.get("case_id") or case.get("id") or "")
        candidate = (by_id.get(case_id) or {}).get("candidate_experience")
        if candidate is None:
            continue
        warnings += 1
        if case.get("expected_advisory") is True and candidate == case_id:
            correct += 1
        elif case.get("expected_advisory") is not True:
            false_warnings += 1
    return {
        "positive_n": len(positives),
        "negative_n": len(negatives),
        "warnings": warnings,
        "correct_warnings": correct,
        "false_warnings": false_warnings,
        "positive_recall": correct / len(positives) if positives else 0.0,
        "precision": correct / warnings if warnings else 0.0,
        "false_warning_rate": (
            false_warnings / len(negatives) if negatives else 0.0),
    }


def calibration_report(cases, hybrid_results, lexical_results, *, thresholds,
                       embedding_id: str, min_precision: float = 0.9,
                       max_false_warning_rate: float = 0.1) -> dict:
    rows = validate_cases(cases)
    expected_ids = {
        str(case.get("case_id") or case.get("id")) for case in rows}
    hybrid_by_id = {str(row.get("id") or ""): dict(row)
                    for row in hybrid_results}
    lexical_by_id = {str(row.get("id") or ""): dict(row)
                     for row in lexical_results}
    if set(hybrid_by_id) != expected_ids or set(lexical_by_id) != expected_ids:
        raise ValueError("retrieval observations must cover every development case")
    observations = []
    for case in rows:
        case_id = str(case.get("case_id") or case.get("id"))
        result = hybrid_by_id[case_id]
        observations.append({
            "id": case_id,
            "expected_experience": (
                case_id if case.get("expected_advisory") is True else None),
            "candidate_experience": result.get("candidate_experience"),
            "score": result.get("score"),
        })
    tuned = calibration.calibrate_threshold(
        observations, thresholds=thresholds, min_precision=min_precision,
        max_false_warning_rate=max_false_warning_rate)
    lexical = _lexical_metrics(rows, list(lexical_by_id.values()))
    selected = tuned.get("selected") or {
        "positive_recall": 0.0, "precision": 0.0,
        "false_warning_rate": 0.0,
    }
    comparison = calibration.compare_to_lexical(selected, lexical)
    accepted = tuned.get("selected_threshold") is not None and comparison["passes"]
    return {
        "schema_version": 1,
        "selection_source": "development_only",
        "embedding_id": str(embedding_id or ""),
        "cases": {
            "total": len(rows),
            "positive": sum(case.get("expected_advisory") is True for case in rows),
            "negative": sum(case.get("expected_advisory") is not True for case in rows),
        },
        "constraints": tuned["constraints"],
        "selected_threshold": tuned.get("selected_threshold"),
        "selected": tuned.get("selected"),
        "trials": tuned["trials"],
        "lexical": lexical,
        "hybrid_vs_lexical": comparison,
        "accepted": accepted,
        "reason": (
            "selected_safe_threshold_with_hybrid_gain" if accepted
            else tuned.get("reason") if tuned.get("selected_threshold") is None
            else comparison["reason"]),
    }


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {number} must contain an object")
        rows.append(row)
    return rows


def _require_private(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPOSITORY.resolve())
    except ValueError:
        return resolved
    raise ValueError("private calibration data and outputs must remain outside the repository")


def _body(record: dict) -> str:
    return " ".join((record["situation"], record["goal"], record["approach"],
                     record["action"], record["lesson"], record["applicability"]))


def _seed_database(cases: list[dict], database: Path, *, embed_doc,
                   embedding_id: str) -> None:
    import _experience as experience

    stage = database.with_name(database.name + ".staging")
    if stage.exists():
        stage.unlink()
    conn = experience.connect(stage)
    try:
        experience.ensure_schema(conn)
        indexed = []
        dimension = None
        for case in cases:
            record = record_for(case)
            if record is None:
                continue
            outcome_id = "outcome-" + record["experience_id"]
            experience.record_outcome(
                conn, outcome_id=outcome_id, session_id=record["session_id"],
                task_id=record["task_id"], state=record["outcome_state"],
                evidence=[{"source_refs": record["source_refs"]}],
                attribution_strength="reviewed")
            experience.save_experience(
                conn, status="validated", outcome_refs=[outcome_id],
                **record)
            vector = embed_doc(_body(record))
            if vector is None:
                raise RuntimeError("document embedding failed")
            if dimension is None:
                dimension = len(vector)
                experience.ensure_recall_schema(
                    conn, dim=dimension, embed_id=embedding_id)
            elif len(vector) != dimension:
                raise RuntimeError("embedding dimension changed during calibration")
            indexed.append((record["experience_id"], vector))
        for experience_id, vector in indexed:
            experience.index_experience(conn, experience_id, vector=vector)
        conn.commit()
    finally:
        conn.close()
    os.replace(stage, database)


def _failed(item: dict) -> bool:
    attempt = item.get("attempt_state") or "unknown"
    return attempt == "failure" or (
        attempt == "unknown" and item.get("outcome_state") == "failure")


def _lexical_candidate(conn, query: str) -> str | None:
    import _experience as experience
    import _kbindex

    expr = _kbindex.fts_expr(query)
    if not expr:
        return None
    rows = conn.execute(
        "SELECT docs.path FROM fts_docs JOIN docs ON docs.doc_id=fts_docs.rowid "
        "WHERE fts_docs MATCH ? AND docs.layer='experience' "
        "AND docs.status='validated' ORDER BY rank LIMIT 20", (expr,)).fetchall()
    for (path,) in rows:
        item = experience.experience(conn, str(path).removeprefix("experience::"))
        if item is not None and _failed(item):
            return item["experience_id"]
    return None


def _observe(cases: list[dict], database: Path, *, embed_query) -> tuple[list, list]:
    import _experience as experience

    conn = experience.connect(database)
    hybrid, lexical = [], []
    try:
        first = conn.execute("SELECT value FROM meta WHERE key='dim'").fetchone()
        if first is None:
            raise RuntimeError("development index lacks embedding metadata")
        dimension = int(first[0])
        embed_id = conn.execute(
            "SELECT value FROM meta WHERE key='embed_id'").fetchone()[0]
        experience.ensure_recall_schema(conn, dim=dimension, embed_id=embed_id)
        for case in cases:
            case_id = str(case.get("case_id") or case.get("id"))
            query = str(case.get("query") or "").strip()
            vector = embed_query(query)
            if vector is None or len(vector) != dimension:
                raise RuntimeError(f"query embedding failed: {case_id}")
            candidate = None
            for item in experience.experience_hits(
                    conn, query_vector=vector, query_text=query, k=8,
                    statuses=("validated",)):
                if _failed(item):
                    candidate = item
                    break
            hybrid.append({
                "id": case_id,
                "candidate_experience": (
                    candidate.get("experience_id") if candidate else None),
                "score": candidate.get("cos") if candidate else None,
            })
            lexical.append({
                "id": case_id,
                "candidate_experience": _lexical_candidate(conn, query),
            })
    finally:
        conn.close()
    return hybrid, lexical


def _thresholds(value: str) -> list[float]:
    values = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one threshold is required")
    return values


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--thresholds", type=_thresholds,
        default=_thresholds("0.40,0.45,0.50,0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90"))
    parser.add_argument("--min-precision", type=float, default=0.9)
    parser.add_argument("--max-false-warning-rate", type=float, default=0.1)
    args = parser.parse_args(argv)
    try:
        development = _require_private(args.development)
        frozen_path = _require_private(args.frozen)
        database = _require_private(args.database)
        report_path = _require_private(args.report)
        cases = validate_cases(_load_jsonl(development))
        frozen_doc = json.loads(frozen_path.read_text(encoding="utf-8"))
        frozen = frozen_doc.get("cases") if isinstance(frozen_doc, dict) else frozen_doc
        if not isinstance(frozen, list):
            raise ValueError("frozen input must contain a cases array")
        calibration.assert_independent(cases, frozen)
        import _embeddings as embeddings

        embedding_id = embeddings.embed_id()
        database.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ["KB_USAGE_DISABLE"] = "1"
        _seed_database(
            cases, database,
            embed_doc=lambda text: embeddings.embed(text, kind="doc"),
            embedding_id=embedding_id)
        hybrid, lexical = _observe(
            cases, database, embed_query=lambda text: embeddings.embed_query(text))
        report = calibration_report(
            cases, hybrid, lexical, thresholds=args.thresholds,
            embedding_id=embedding_id, min_precision=args.min_precision,
            max_false_warning_rate=args.max_false_warning_rate)
        temporary = report_path.with_name(report_path.name + ".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        os.replace(temporary, report_path)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report["accepted"] else 2
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)},
                         ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

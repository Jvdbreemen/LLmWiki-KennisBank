"""Run reviewed experience retrieval against the real disposable projection."""
from __future__ import annotations

import os
import time
from pathlib import Path

import _experience
import _layer_eval
import _layer_eval_runner


def _body(record: dict) -> str:
    return " ".join((record.get("situation", ""), record.get("goal", ""),
                     record.get("approach", ""), record.get("action", ""),
                     record.get("lesson", ""), record.get("applicability", "")))


def _build(cases, db_path: Path, embed_fn, embed_id: str, *, vault: Path) -> None:
    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_name(target.name + ".staging")
    stage.unlink(missing_ok=True)
    conn = _experience.connect(stage)
    try:
        _experience.ensure_schema(conn)
        records = {}
        for case in cases:
            for record in case.get("records") or []:
                records.setdefault(record["experience_id"], record)
        vectors = [(record, embed_fn(_body(record))) for record in records.values()]
        if vectors:
            _experience.ensure_recall_schema(
                conn, dim=len(vectors[0][1]), embed_id=embed_id)
        for record, vector in vectors:
            for outcome_id in record.get("outcome_refs") or []:
                _experience.record_outcome(
                    conn, outcome_id=outcome_id, session_id="reviewed-holdout",
                    task_id=record["experience_id"],
                    state=record["outcome_state"],
                    evidence=[{"source_refs": record.get("source_refs") or []}],
                    attribution_strength="reviewed")
            _experience.save_experience(
                conn, experience_id=record["experience_id"],
                session_id="reviewed-holdout", task_id=record["experience_id"],
                status="candidate", situation=record.get("situation", ""),
                goal=record.get("goal", ""), approach=record.get("approach", ""),
                action=record.get("action", ""),
                observed_result=record.get("observed_result", ""),
                lesson=record.get("lesson", ""),
                applicability=record.get("applicability", ""),
                outcome_state=record["outcome_state"], confidence=0.2,
                attempt_state=record.get("attempt_state", "unknown"),
                resolution_state=record.get("resolution_state", "not_applicable"),
                source_refs=record.get("source_refs") or [],
                outcome_refs=record.get("outcome_refs") or [])
            if record.get("status") == "validated":
                review = dict(record.get("review") or {})
                if (review.get("decision") != "accepted"
                        or any(not str(review.get(field) or "").strip()
                               for field in ("actor", "reviewed_at", "reason"))):
                    raise ValueError(
                        "validated evaluation record requires an accepted human review")
                stored = _experience.experience(conn, record["experience_id"])
                review_id = str(
                    review.get("review_id") or f"eval-review-{record['experience_id']}")
                _experience.record_review(
                    conn, review_id=review_id,
                    experience_id=record["experience_id"], decision="accepted",
                    actor=str(review["actor"]), reviewed_at=str(review["reviewed_at"]),
                    reason=str(review["reason"]), content_hash=stored["content_hash"],
                    idempotency_key=str(review.get("idempotency_key") or review_id))
                _experience.transition(
                    conn, record["experience_id"], "validated", vault=vault)
            _experience.index_experience(
                conn, record["experience_id"], vector=vector)
        conn.commit()
    finally:
        conn.close()
    os.replace(stage, target)


def _lexical_hits(conn, query: str, *, k: int = 3) -> list[dict]:
    expr = _experience._kbindex.fts_expr(query)
    if not expr:
        return []
    try:
        rows = conn.execute(
            "SELECT d.path FROM fts_docs f JOIN docs d ON d.doc_id=f.rowid "
            "WHERE fts_docs MATCH ? AND d.layer='experience' "
            "AND d.status='validated' ORDER BY rank LIMIT ?", (expr, k)).fetchall()
    except Exception:
        return []
    hits = []
    for (path,) in rows:
        item = _experience.experience(conn, str(path).removeprefix("experience::"))
        if item is not None:
            item.update({"fts": True, "cos": None})
            hits.append(item)
    return hits


def evaluate_experience_holdout(cases, *, db_path: Path, embed_id: str,
                                embed_fn=None, embed_doc_fn=None,
                                embed_query_fn=None,
                                advisory_min_cos: float = 0.5,
                                vault: Path | None = None) -> dict:
    """Return aggregate hybrid/lexical metrics without prompts or passages."""
    cases = list(cases)
    embed_doc = embed_doc_fn or embed_fn
    embed_query = embed_query_fn or embed_fn
    if embed_doc is None or embed_query is None:
        raise ValueError("document and query embedding functions are required")
    _build(cases, Path(db_path), embed_doc, embed_id,
           vault=Path(vault) if vault is not None else Path(db_path).parent)
    conn = _experience.connect(db_path)
    hybrid = {}
    lexical = {}
    advisory_total = advisory_correct = 0
    warning_probes = false_warnings = 0
    latencies = []
    try:
        dimension = int(_experience._kbindex.meta_get(conn, "dim") or 0)
        _experience.ensure_recall_schema(conn, dim=dimension, embed_id=embed_id)
        for case in cases:
            started = time.perf_counter()
            vector = embed_query(case["query"])
            hybrid[case["id"]] = _experience.experience_hits(
                conn, query_vector=vector, query_text=case["query"], k=3,
                statuses=("validated",))
            latencies.append((time.perf_counter() - started) * 1000.0)
            lexical[case["id"]] = _lexical_hits(conn, case["query"], k=3)
            attempt_state = case.get("expected_attempt_state", case.get("expected_state"))
            if attempt_state == "failure" or case.get("expected_experience") is None:
                if case.get("expected_experience") is None:
                    warning_probes += 1
                warning = _experience.failure_advisory(
                    conn, query_vector=vector, query_text=case["query"],
                    min_score=advisory_min_cos)
                if warning:
                    advisory_total += 1
                    if case.get("expected_experience") is None:
                        false_warnings += 1
                    if (attempt_state == "failure"
                            and warning.get("experience_id") == case.get("expected_experience")):
                        advisory_correct += 1
    finally:
        conn.close()
    hybrid_report = _layer_eval_runner.evaluate_experience(
        cases, lambda case: hybrid[case["id"]])
    hybrid_report["false_warning_rate"] = (
        false_warnings / warning_probes if warning_probes else 0.0)
    lexical_report = _layer_eval_runner.evaluate_experience(
        cases, lambda case: lexical[case["id"]])
    return {
        "cases": len(cases),
        "hybrid": hybrid_report,
        "lexical": lexical_report,
        "advisory_precision": (advisory_correct / advisory_total
                               if advisory_total else 0.0),
        "advisories": advisory_total,
        "correct_advisories": advisory_correct,
        "warning_probes": warning_probes,
        "false_warnings": false_warnings,
        "latency_ms": _layer_eval.latency_summary(latencies),
        "candidate_leakage": hybrid_report["candidate_leakage"],
    }

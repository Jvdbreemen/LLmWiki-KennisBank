#!/usr/bin/env python3
"""Run the reviewed experience holdout once after development calibration."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPOSITORY = SCRIPTS.parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.append(str(__import__("pathlib").Path(__file__).resolve().parents[1]))  # shipped scripts/; dev tools live in scripts/dev/

import _layer_eval_runner as layer_runner  # noqa: E402


def advisory_metrics(cases, warnings) -> dict:
    warning_by_id = {str(row.get("id") or ""): dict(row) for row in warnings}
    failure_cases = [
        case for case in cases
        if case.get("expected_experience") is not None
        and case.get("expected_attempt_state") == "failure"]
    negative_cases = [case for case in cases
                      if case.get("expected_experience") is None]
    advisories = correct = false_warnings = 0
    for case in failure_cases + negative_cases:
        case_id = str(case.get("id") or "")
        candidate = (warning_by_id.get(case_id) or {}).get("candidate_experience")
        if candidate is None:
            continue
        advisories += 1
        expected = case.get("expected_experience")
        if expected is None:
            false_warnings += 1
        elif candidate == expected:
            correct += 1
    return {
        "failure_attempts": len(failure_cases),
        "negative_probes": len(negative_cases),
        "advisories": advisories,
        "correct_advisories": correct,
        "false_warnings": false_warnings,
        "advisory_precision": correct / advisories if advisories else 0.0,
        "false_warning_rate": (
            false_warnings / len(negative_cases) if negative_cases else 0.0),
        "failure_advisory_recall": (
            correct / len(failure_cases) if failure_cases else 0.0),
    }


def gate_summary(retrieval: dict, advisories: dict, *, lexical_hit3: float) -> dict:
    hybrid_hit3 = float((retrieval.get("retrieval") or {}).get("hit@3") or 0.0)
    checks = {
        "failure_hit@3": float(retrieval.get("failure_hit@3") or 0.0) >= 0.70,
        "evidence_precision": float(retrieval.get("evidence_precision") or 0.0) >= 1.0,
        "candidate_leakage": int(retrieval.get("candidate_leakage") or 0) == 0,
        "advisory_precision": float(advisories.get("advisory_precision") or 0.0) >= 0.90,
        "false_warning_rate": float(advisories.get("false_warning_rate") or 0.0) <= 0.10,
        "hybrid_gain": hybrid_hit3 > float(lexical_hit3),
    }
    return {"passes": all(checks.values()), "checks": checks,
            "hybrid_hit@3_delta": hybrid_hit3 - float(lexical_hit3)}


def require_fresh_report(path: Path) -> None:
    if path.exists():
        raise ValueError(f"holdout report already exists: {path}")


def require_fresh_database(path: Path) -> None:
    if path.exists():
        raise ValueError(f"holdout database already exists: {path}")


def claim_report(path: Path, *, input_sha256: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = {
        "schema_version": 1,
        "status": "running",
        "holdout_policy": "frozen_one_shot_no_further_tuning",
        "input_sha256": input_sha256,
    }
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(marker, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise ValueError(f"holdout report already exists: {path}") from exc


def _private(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPOSITORY.resolve())
    except ValueError:
        return resolved
    raise ValueError("private holdout inputs and outputs must remain outside the repository")


def _review_contract(record: dict) -> tuple[list[dict], dict]:
    source_refs = list(record.get("source_refs") or [])
    if (not source_refs
            or any(not isinstance(ref, dict) or not ref.get("source_ref_id")
                   for ref in source_refs)):
        raise ValueError("reviewed record requires structured source refs")
    review = record.get("review") or {}
    if (review.get("decision") != "accepted"
            or not str(review.get("actor") or "").strip()
            or not str(review.get("reviewed_at") or "").strip()
            or not str(review.get("reason") or "").strip()):
        raise ValueError("reviewed record requires an explicit accepted human review")
    return source_refs, review


def _load_cases(path: Path) -> list[dict]:
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
    ids = [str(row.get("id") or "") for row in rows]
    if len(set(ids)) != len(ids) or any(not value for value in ids):
        raise ValueError("holdout cases require unique ids")
    positives = [row for row in rows if row.get("expected_experience") is not None]
    negatives = [row for row in rows if row.get("expected_experience") is None]
    failures = [row for row in positives
                if row.get("expected_attempt_state") == "failure"]
    if (len(rows), len(positives), len(negatives), len(failures)) != (70, 60, 10, 29):
        raise ValueError("unexpected frozen holdout composition")
    for case in positives:
        records = case.get("records") or []
        if len(records) != 1 or records[0].get("experience_id") != case.get(
                "expected_experience"):
            raise ValueError("positive holdout case requires one matching record")
        if records[0].get("attempt_state") != case.get("expected_attempt_state"):
            raise ValueError("record attempt state differs from reviewed case")
        if records[0].get("resolution_state") != case.get(
                "expected_resolution_state"):
            raise ValueError("record resolution state differs from reviewed case")
        _review_contract(records[0])
    return rows


def _body(record: dict) -> str:
    return " ".join(str(record.get(key) or "") for key in (
        "situation", "goal", "approach", "action", "lesson", "applicability"))


def _seed(cases: list[dict], database: Path, *, embed_doc, embedding_id: str,
          vault: Path | None = None) -> None:
    import _experience as experience
    import _source_ref as source_ref
    from _vaultpath import vault_root

    evidence_root = Path(vault) if vault is not None else vault_root()
    stage = database.with_name(database.name + ".staging")
    if stage.exists():
        stage.unlink()
    conn = experience.connect(stage)
    try:
        experience.ensure_schema(conn)
        indexed = []
        dimension = None
        for case in cases:
            if case.get("expected_experience") is None:
                continue
            record = dict(case["records"][0])
            source_refs, review = _review_contract(record)
            invalid_refs = [
                ref.get("source_ref_id") or "<missing-id>"
                for ref in source_refs
                if source_ref.resolve_source_ref(evidence_root, ref).get("status") != "valid"
            ]
            if invalid_refs:
                raise ValueError(
                    "reviewed record requires fresh exact source refs: "
                    + ", ".join(invalid_refs))
            outcome_refs = list(record.get("outcome_refs") or [])
            if len(outcome_refs) != 1:
                raise ValueError("reviewed record requires one outcome reference")
            experience.record_outcome(
                conn, outcome_id=outcome_refs[0], session_id=case["id"],
                task_id=case["id"], state=record["outcome_state"],
                evidence=[{"source_refs": source_refs}],
                attribution_strength="reviewed")
            experience.save_experience(
                conn, experience_id=record["experience_id"],
                session_id=case["id"], task_id=case["id"],
                status="candidate", situation=record.get("situation") or "",
                goal=record.get("goal") or "", approach=record.get("approach") or "",
                action=record.get("action") or "",
                observed_result=record.get("observed_result") or "",
                lesson=record.get("lesson") or "",
                applicability=record.get("applicability") or "",
                outcome_state=record["outcome_state"],
                attempt_state=record["attempt_state"],
                resolution_state=record["resolution_state"], confidence=0.2,
                source_refs=source_refs,
                outcome_refs=outcome_refs)
            stored = experience.experience(conn, record["experience_id"])
            experience.record_review(
                conn,
                review_id=str(review.get("review_id") or f"holdout-review-{case['id']}"),
                experience_id=record["experience_id"], decision="accepted",
                actor=str(review["actor"]), reviewed_at=str(review["reviewed_at"]),
                reason=str(review.get("reason") or ""),
                content_hash=stored["content_hash"],
                idempotency_key=str(
                    review.get("idempotency_key") or f"holdout-review-{case['id']}"))
            experience.transition(
                conn, record["experience_id"], "validated", vault=evidence_root)
            vector = embed_doc(_body(record))
            if vector is None:
                raise RuntimeError("document embedding failed")
            if dimension is None:
                dimension = len(vector)
                experience.ensure_recall_schema(
                    conn, dim=dimension, embed_id=embedding_id)
            elif len(vector) != dimension:
                raise RuntimeError("embedding dimension changed during holdout build")
            indexed.append((record["experience_id"], vector))
        for experience_id, vector in indexed:
            experience.index_experience(conn, experience_id, vector=vector)
        conn.commit()
    finally:
        conn.close()
    os.replace(stage, database)


def _lexical_hits(conn, query: str, *, k: int = 3) -> list[dict]:
    import _experience as experience
    import _kbindex

    expr = _kbindex.fts_expr(query)
    if not expr:
        return []
    rows = conn.execute(
        "SELECT docs.path FROM fts_docs JOIN docs ON docs.doc_id=fts_docs.rowid "
        "WHERE fts_docs MATCH ? AND docs.layer='experience' "
        "AND docs.status='validated' ORDER BY rank LIMIT ?", (expr, k)).fetchall()
    result = []
    for (path,) in rows:
        record = experience.experience(
            conn, str(path).removeprefix("experience::"))
        if record is not None:
            result.append(record)
    return result


def _latency(values: list[float]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "p50_ms": 0.0, "p95_ms": 0.0}
    def nearest(q):
        return ordered[max(0, min(len(ordered) - 1, round(q * (len(ordered) - 1))))]
    return {"n": len(ordered), "p50_ms": nearest(0.50), "p95_ms": nearest(0.95)}


def _evaluate(cases: list[dict], database: Path, *, embed_query) -> dict:
    import _experience as experience

    conn = experience.connect(database)
    hybrid_by_id = {}
    lexical_by_id = {}
    warnings = []
    latencies = []
    try:
        dimension = int(conn.execute(
            "SELECT value FROM meta WHERE key='dim'").fetchone()[0])
        embed_id = conn.execute(
            "SELECT value FROM meta WHERE key='embed_id'").fetchone()[0]
        experience.ensure_recall_schema(conn, dim=dimension, embed_id=embed_id)
        for case in cases:
            started = time.perf_counter()
            vector = embed_query(str(case.get("query") or ""))
            if vector is None or len(vector) != dimension:
                raise RuntimeError("query embedding failed")
            hits = experience.experience_hits(
                conn, query_vector=vector, query_text=case["query"], k=3,
                statuses=("validated",))
            latencies.append((time.perf_counter() - started) * 1000.0)
            warning = None
            if (case.get("expected_attempt_state") == "failure"
                    or case.get("expected_experience") is None):
                warning = experience.failure_advisory(
                    conn, query_vector=vector, query_text=case["query"])
                warnings.append({
                    "id": case["id"],
                    "candidate_experience": (
                        warning.get("experience_id") if warning else None),
                })
            hybrid_by_id[case["id"]] = (
                hits if case.get("expected_experience") is not None
                else ([warning] if warning else []))
            lexical_by_id[case["id"]] = _lexical_hits(conn, case["query"], k=3)
    finally:
        conn.close()
    hybrid = layer_runner.evaluate_experience(
        cases, lambda case: hybrid_by_id[case["id"]])
    lexical = layer_runner.evaluate_experience(
        cases, lambda case: lexical_by_id[case["id"]])
    advisories = advisory_metrics(cases, warnings)
    return {
        "hybrid": hybrid,
        "lexical": lexical,
        "advisories": advisories,
        "latency_ms": _latency(latencies),
        "gates": gate_summary(
            hybrid, advisories,
            lexical_hit3=float(lexical["retrieval"]["hit@3"])),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--confirm-frozen-once", action="store_true")
    args = parser.parse_args(argv)
    report_path = None
    claimed = False
    input_sha256 = None
    try:
        if not args.confirm_frozen_once:
            raise ValueError("one-shot holdout run requires --confirm-frozen-once")
        cases_path = _private(args.cases)
        database = _private(args.database)
        report_path = _private(args.report)
        require_fresh_report(report_path)
        require_fresh_database(database)
        cases = _load_cases(cases_path)
        input_sha256 = "sha256:" + hashlib.sha256(
            cases_path.read_bytes()).hexdigest()
        claim_report(report_path, input_sha256=input_sha256)
        claimed = True
        import _embeddings as embeddings
        import _experience as experience

        os.environ["KB_USAGE_DISABLE"] = "1"
        database.parent.mkdir(parents=True, exist_ok=True)
        embedding_id = embeddings.embed_id()
        _seed(cases, database,
              embed_doc=lambda text: embeddings.embed(text, kind="doc"),
              embedding_id=embedding_id)
        measured = _evaluate(cases, database, embed_query=embeddings.embed_query)
        report = {
            "schema_version": 1,
            "selection_commit_required": True,
            "holdout_policy": "frozen_one_shot_no_further_tuning",
            "input_sha256": input_sha256,
            "embedding_id": embedding_id,
            "advisory_threshold": experience.FAILURE_ADVISORY_MIN_COS,
            "cases": {"total": 70, "positive": 60, "negative": 10,
                      "failure_attempts": 29},
            **measured,
        }
        temporary = report_path.with_name(report_path.name + ".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        os.replace(temporary, report_path)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        if claimed and report_path is not None:
            failure = {
                "schema_version": 1,
                "status": "failed",
                "holdout_policy": "frozen_one_shot_no_further_tuning",
                "input_sha256": input_sha256,
                "reason": str(exc),
            }
            temporary = report_path.with_name(report_path.name + ".tmp")
            try:
                temporary.write_text(
                    json.dumps(failure, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n",
                    encoding="utf-8")
                os.replace(temporary, report_path)
            except OSError:
                pass
        print(json.dumps({"status": "failed", "reason": str(exc)},
                         ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

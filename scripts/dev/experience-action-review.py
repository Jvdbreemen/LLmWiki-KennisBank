#!/usr/bin/env python3
"""Generate, review, and score blinded experience action pairs privately."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
REPOSITORY = SCRIPTS.parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.append(str(__import__("pathlib").Path(__file__).resolve().parents[1]))  # shipped scripts/; dev tools live in scripts/dev/

import _paired_action_eval as paired  # noqa: E402


EXPECTED_CASES_SHA256 = (
    "0f5881ee6181fe8d9df94ea2779a1404ab71403dca61c7b29fccd443e36208be")
SYSTEM = """Je bent een lokale coding- en operations-assistent. Geef voor de taak
een concreet, veilig handelingsadvies van maximaal 140 woorden. Gebruik alleen
de aangeboden taak en context. Benoem niet dat je context, geheugen, een
ervaring, een experiment of een evaluatie gebruikt. Geef direct het advies,
zonder voorwoord en zonder achteraf om meer informatie te vragen."""


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _private(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPOSITORY.resolve())
    except ValueError:
        return resolved
    raise ValueError("private action-review artifacts must remain outside the repository")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {number} of {path.name}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {number} of {path.name} must be an object")
        rows.append(row)
    return rows


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8")
    os.replace(temporary, path)


def append_unique(path: Path, row: dict) -> None:
    rows = load_jsonl(path)
    case_id = str(row.get("id") or "")
    if not case_id:
        raise ValueError("row id is required")
    if any(str(existing.get("id") or "") == case_id for existing in rows):
        raise ValueError(f"case already exists: {case_id}")
    _write_jsonl(path, [*rows, row])


def action_prompt(query: str, common_context: str,
                  experience_context: str) -> str:
    common = str(common_context or "").strip() or "Geen relevante wiki- of memory-context."
    experience = (str(experience_context or "").strip()
                  or "Geen aanvullende gevalideerde ervaringscontext.")
    return (
        f"TAAK\n{str(query).strip()}\n\n"
        f"NORMALE KENNISBANK-CONTEXT\n{common}\n\n"
        f"AANVULLENDE ERVARINGSCONTEXT\n{experience}\n\n"
        "Geef nu het beste concrete handelingsadvies.")


def next_pair(pairs, reviews):
    pair_rows = list(pairs)
    reviewed = {str(row.get("id") or "") for row in reviews}
    known = {str(row.get("id") or "") for row in pair_rows}
    if "" in known or len(known) != len(pair_rows):
        raise ValueError("blind pairs require unique non-empty ids")
    if not reviewed.issubset(known):
        raise ValueError("review references an unknown blind pair")
    pending = [row for row in pair_rows if str(row["id"]) not in reviewed]
    progress = {
        "reviewed": len(reviewed),
        "total": len(pair_rows),
        "remaining": len(pending),
    }
    return (dict(pending[0]) if pending else None), progress


def record_review(blind_path: Path, reviews_path: Path, *, case_id: str,
                  verdict: str) -> None:
    if verdict not in paired.VERDICTS:
        raise ValueError("invalid verdict; use a_only, b_only, both, or neither")
    known = {str(row.get("id") or "") for row in load_jsonl(blind_path)}
    if case_id not in known:
        raise ValueError(f"unknown blind case: {case_id}")
    append_unique(reviews_path, {"id": case_id, "verdict": verdict})


def _load_cases(path: Path) -> list[dict]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_CASES_SHA256:
        raise ValueError(f"frozen cases hash differs: {digest}")
    rows = load_jsonl(path)
    positives = [row for row in rows if row.get("expected_experience") is not None]
    if len(rows) != 70 or len(positives) != 60:
        raise ValueError("expected the frozen 70-case set with 60 positive cases")
    ids = [str(row.get("id") or "") for row in positives]
    if len(ids) != len(set(ids)) or any(not case_id for case_id in ids):
        raise ValueError("positive cases require unique non-empty ids")
    return positives


def _load_recall_module():
    spec = importlib.util.spec_from_file_location(
        "kb_recall", SCRIPTS.parent / "kb-recall.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normal_context(query: str, vector) -> str:
    recall = _load_recall_module()
    hits = recall.recall_hits(
        vector, query_text=query, k=4, layers=("wiki", "memory"))
    if not hits:
        return ""
    return "\n".join(
        f"- [{hit.get('layer')}] {hit.get('title')}: {hit.get('snippet')}"
        for hit in hits)


def _experience_context(database: Path, query: str, vector):
    import _experience as experience

    conn = experience.connect(database)
    try:
        dimension = int(conn.execute(
            "SELECT value FROM meta WHERE key='dim'").fetchone()[0])
        embed_id = conn.execute(
            "SELECT value FROM meta WHERE key='embed_id'").fetchone()[0]
        experience.ensure_recall_schema(conn, dim=dimension, embed_id=embed_id)
        if len(vector) != dimension:
            raise ValueError("query vector dimension differs from frozen projection")
        hits = experience.experience_hits(
            conn, query_vector=vector, query_text=query, k=3,
            statuses=("validated",))
    finally:
        conn.close()
    blocks = []
    for hit in hits:
        fields = [
            ("Situatie", hit.get("situation")),
            ("Aanpak", hit.get("approach")),
            ("Actie", hit.get("action")),
            ("Resultaat", hit.get("observed_result")),
            ("Les", hit.get("lesson")),
            ("Toepassing", hit.get("applicability")),
        ]
        blocks.append("\n".join(
            f"{label}: {str(value or '').strip()[:500]}" for label, value in fields))
    return "\n\n".join(blocks), [str(hit["experience_id"]) for hit in hits]


def _sync_blind(master_path: Path, blind_path: Path) -> list[dict]:
    masters = load_jsonl(master_path)
    blinds = []
    seen = set()
    for row in masters:
        case_id = str(row.get("id") or "")
        blind = dict(row.get("blind") or {})
        key = dict(row.get("key") or {})
        if not case_id or case_id in seen or blind.get("id") != case_id:
            raise ValueError("master contains invalid or duplicate ids")
        paired.verify_pair(blind, key)
        seen.add(case_id)
        blinds.append(blind)
    _write_jsonl(blind_path, blinds)
    return masters


def _generate(args) -> dict:
    cases_path = _private(args.cases)
    database = _private(args.database)
    master_path = _private(args.master)
    blind_path = _private(args.blind)
    cases = _load_cases(cases_path)
    by_id = {str(case["id"]): case for case in cases}
    assignments = paired.assignment_map(by_id, seed=224)
    masters = _sync_blind(master_path, blind_path)
    completed = {str(row["id"]) for row in masters}
    pending = [case_id for case_id in sorted(by_id) if case_id not in completed]
    if args.case_id:
        if args.case_id not in by_id:
            raise ValueError(f"unknown positive case: {args.case_id}")
        if args.case_id in completed:
            raise ValueError(f"case already exists: {args.case_id}")
        pending = [args.case_id]
    else:
        pending = pending[:max(1, int(args.limit))]
    if not pending:
        return {"status": "complete", "generated": [], "total": len(masters)}

    import _embeddings as embeddings
    import _llm

    if _llm.providers() != ["ollama"] or not _llm.is_local():
        raise ValueError("paired action generation requires local Ollama only")
    os.environ["KB_USAGE_DISABLE"] = "1"
    generated = []
    for case_id in pending:
        case = by_id[case_id]
        query = str(case["query"])
        vector = embeddings.embed_query(query)
        if not vector:
            raise RuntimeError(f"embedding failed for {case_id}")
        common = _normal_context(query, vector)
        experience_context, experience_ids = _experience_context(
            database, query, vector)
        baseline = _llm.generate(
            action_prompt(query, common, ""), system=SYSTEM, timeout=180.0)
        experiment = _llm.generate(
            action_prompt(query, common, experience_context),
            system=SYSTEM, timeout=180.0)
        if not baseline or not experiment:
            raise RuntimeError(f"local action generation failed for {case_id}")
        blind, key = paired.make_pair(
            case=case, baseline=baseline, experience=experiment,
            a_arm=assignments[case_id],
            common_context_sha256=_sha256_text(common),
            experience_ids=experience_ids,
            model=_llm.model_for("ollama"))
        append_unique(master_path, {
            "id": case_id,
            "cases_sha256": "sha256:" + EXPECTED_CASES_SHA256,
            "blind": blind,
            "key": key,
        })
        _sync_blind(master_path, blind_path)
        generated.append(case_id)
    return {"status": "ok", "generated": generated,
            "total": len(load_jsonl(master_path))}


def _show(args) -> dict:
    blind_path = _private(args.blind)
    reviews_path = _private(args.reviews)
    row, progress = next_pair(load_jsonl(blind_path), load_jsonl(reviews_path))
    return {"status": "complete" if row is None else "pending",
            "progress": progress, "case": row}


def _record(args) -> dict:
    blind_path = _private(args.blind)
    reviews_path = _private(args.reviews)
    record_review(blind_path, reviews_path, case_id=args.case_id,
                  verdict=args.verdict)
    _row, progress = next_pair(load_jsonl(blind_path), load_jsonl(reviews_path))
    return {"status": "ok", "recorded": args.case_id, "progress": progress}


def _score(args) -> dict:
    master_path = _private(args.master)
    reviews_path = _private(args.reviews)
    report_path = _private(args.report)
    if report_path.exists():
        raise ValueError(f"action report already exists: {report_path}")
    masters = load_jsonl(master_path)
    if len(masters) != 60:
        raise ValueError("scoring requires all 60 frozen positive pairs")
    pairs = [dict(row.get("blind") or {}) for row in masters]
    keys = [dict(row.get("key") or {}) for row in masters]
    reviews = load_jsonl(reviews_path)
    result = paired.score(pairs, keys, reviews, bootstrap=10000, seed=224)
    report = {
        "schema_version": 1,
        "status": "complete",
        "cases_sha256": "sha256:" + EXPECTED_CASES_SHA256,
        "review_protocol": "four_way_blind_owner_judgment",
        "strongest_baseline": "same local model plus production wiki/memory context",
        "experience_arm": "baseline plus actual top-3 validated experience recall",
        **result,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_name(report_path.name + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.replace(temporary, report_path)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--cases", required=True, type=Path)
    generate.add_argument("--database", required=True, type=Path)
    generate.add_argument("--master", required=True, type=Path)
    generate.add_argument("--blind", required=True, type=Path)
    generate.add_argument("--case-id")
    generate.add_argument("--limit", type=int, default=1)
    show = commands.add_parser("show")
    show.add_argument("--blind", required=True, type=Path)
    show.add_argument("--reviews", required=True, type=Path)
    record = commands.add_parser("record")
    record.add_argument("--blind", required=True, type=Path)
    record.add_argument("--reviews", required=True, type=Path)
    record.add_argument("--case-id", required=True)
    record.add_argument("--verdict", required=True, choices=paired.VERDICTS)
    score = commands.add_parser("score")
    score.add_argument("--master", required=True, type=Path)
    score.add_argument("--reviews", required=True, type=Path)
    score.add_argument("--report", required=True, type=Path)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        functions = {
            "generate": _generate,
            "show": _show,
            "record": _record,
            "score": _score,
        }
        print(json.dumps(functions[args.command](args), ensure_ascii=False,
                         sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)},
                         ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

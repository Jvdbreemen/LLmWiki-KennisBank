#!/usr/bin/env python3
"""Inspect experience candidates and append explicit human review decisions.

The canonical ledger is resolved exclusively from ``KENNISBANK_VAULT``.
``list`` and ``inspect`` open that ledger read-only. ``review`` appends one
content-hash-bound decision; it never writes the disposable projection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _experience  # noqa: E402
import _experience_extract  # noqa: E402


REVIEW_SCHEMA_VERSION = "1"
_REVIEW_DECISIONS = ("accepted", "rejected")
_REVIEW_COLUMNS = {
    "review_id", "experience_id", "decision", "actor", "reviewed_at",
    "reason", "content_hash", "schema_version", "idempotency_key",
}


def vault_root() -> Path:
    raw = str(os.environ.get("KENNISBANK_VAULT") or "").strip()
    if not raw:
        raise ValueError("KENNISBANK_VAULT is required")
    return Path(raw).expanduser().resolve()


def canonical_ledger_path() -> Path:
    return _experience.ledger_path(vault_root())


def experience_id_for(session_id: str, task_id: str) -> str:
    key = f"{session_id}\0{task_id}".encode("utf-8")
    return "experience-" + hashlib.sha256(key).hexdigest()[:20]


def _readonly_connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"canonical experience ledger not found: {path}")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def _require_ledger_schema(conn: sqlite3.Connection) -> None:
    tables = {str(row[0]) for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"experience_events", "experience_outcomes", "experience_reviews"}
    missing = sorted(required - tables)
    if missing:
        raise ValueError("canonical ledger schema missing: " + ", ".join(missing))
    columns = {str(row[1]) for row in conn.execute(
        "PRAGMA table_info(experience_reviews)")}
    missing_columns = sorted(_REVIEW_COLUMNS - columns)
    if missing_columns:
        raise ValueError("experience review schema missing: " +
                         ", ".join(missing_columns))


def _tasks(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = conn.execute(
        "SELECT session_id, task_id FROM experience_events "
        "UNION SELECT session_id, task_id FROM experience_outcomes "
        "ORDER BY session_id, task_id").fetchall()
    return [(str(session_id), str(task_id)) for session_id, task_id in rows]


def _candidate(conn: sqlite3.Connection, experience_id: str) -> dict:
    for session_id, task_id in _tasks(conn):
        candidate_id = experience_id_for(session_id, task_id)
        if candidate_id != experience_id:
            continue
        record = _experience_extract.derive_experience_values(
            conn, session_id, task_id, candidate_id)
        review = _experience.review_for_content(
            conn, candidate_id, record["content_hash"])
        record["review_state"] = _experience.review_state_for_content(
            conn, candidate_id, record["content_hash"])
        record["latest_review"] = review
        return record
    raise KeyError(f"experience candidate not found: {experience_id}")


def list_candidates(path: Path, *, limit: int = 50) -> dict:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    conn = _readonly_connect(path)
    try:
        _require_ledger_schema(conn)
        tasks = _tasks(conn)
        candidates = []
        for session_id, task_id in tasks[:limit]:
            experience_id = experience_id_for(session_id, task_id)
            record = _candidate(conn, experience_id)
            candidates.append({
                "experience_id": experience_id,
                "session_id": session_id,
                "task_id": task_id,
                "status": "candidate",
                "review_state": record["review_state"],
                "content_hash": record["content_hash"],
                "lesson": record.get("lesson", ""),
                "outcome_state": record.get("outcome_state", "unknown"),
            })
        return {
            "status": "ok", "mutated": False, "ledger_path": str(path),
            "total": len(tasks), "returned": len(candidates),
            "candidates": candidates,
        }
    finally:
        conn.close()


def inspect_candidate(path: Path, experience_id: str) -> dict:
    conn = _readonly_connect(path)
    try:
        _require_ledger_schema(conn)
        return {
            "status": "ok", "mutated": False, "ledger_path": str(path),
            "candidate": _candidate(conn, experience_id),
        }
    finally:
        conn.close()


def _required_text(value: str, field: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field} must be non-empty")
    return cleaned


def _review_id(idempotency_key: str) -> str:
    digest = hashlib.sha256(
        f"experience-review-v{REVIEW_SCHEMA_VERSION}\0{idempotency_key}".encode(
            "utf-8")).hexdigest()
    return "review-" + digest[:24]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_review(path: Path, *, experience_id: str, decision: str,
                  actor: str, reason: str, content_hash: str,
                  idempotency_key: str, now_fn=_utc_timestamp) -> dict:
    if decision not in _REVIEW_DECISIONS:
        raise ValueError("decision must be accepted or rejected")
    actor = _required_text(actor, "actor")
    reason = _required_text(reason, "reason")
    idempotency_key = _required_text(idempotency_key, "idempotency key")
    content_hash = _required_text(content_hash, "content hash")
    if len(content_hash) != 71 or not content_hash.startswith("sha256:"):
        raise ValueError("content hash must be sha256:<64 lowercase hex characters>")
    try:
        int(content_hash[7:], 16)
    except ValueError as exc:
        raise ValueError(
            "content hash must be sha256:<64 lowercase hex characters>") from exc
    if content_hash.lower() != content_hash:
        raise ValueError("content hash must be sha256:<64 lowercase hex characters>")
    if not path.is_file():
        raise FileNotFoundError(f"canonical experience ledger not found: {path}")

    conn = sqlite3.connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _require_ledger_schema(conn)
        candidate = _candidate(conn, experience_id)
        if candidate["content_hash"] != content_hash:
            raise ValueError(
                "content hash mismatch; inspect the candidate again before reviewing")

        existing = conn.execute(
            "SELECT review_id, experience_id, decision, actor, reviewed_at, reason, "
            "content_hash, schema_version, idempotency_key FROM experience_reviews "
            "WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if existing:
            keys = ("review_id", "experience_id", "decision", "actor",
                    "reviewed_at", "reason", "content_hash", "schema_version",
                    "idempotency_key")
            review = dict(zip(keys, existing))
            intended = (experience_id, decision, actor, reason, content_hash,
                        REVIEW_SCHEMA_VERSION)
            stored = (review["experience_id"], review["decision"], review["actor"],
                      review["reason"], review["content_hash"],
                      review["schema_version"])
            if stored != intended:
                raise ValueError(
                    "idempotency key already belongs to a different review")
            conn.rollback()
            return {"status": "ok", "created": False, "review": review,
                    "ledger_path": str(path), "projection_written": False}

        reviewed_at = _required_text(now_fn(), "timestamp")
        review = {
            "review_id": _review_id(idempotency_key),
            "experience_id": experience_id,
            "decision": decision,
            "actor": actor,
            "reviewed_at": reviewed_at,
            "reason": reason,
            "content_hash": content_hash,
            "schema_version": REVIEW_SCHEMA_VERSION,
            "idempotency_key": idempotency_key,
        }
        _experience.record_review(conn, **review)
        return {"status": "ok", "created": True, "review": review,
                "ledger_path": str(path), "projection_written": False}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="list derived candidates read-only")
    listing.add_argument("--limit", type=int, default=50)
    inspect = commands.add_parser("inspect", help="inspect one candidate read-only")
    inspect.add_argument("experience_id")
    review = commands.add_parser("review", help="append a human review decision")
    review.add_argument("experience_id")
    review.add_argument("--decision", required=True, choices=_REVIEW_DECISIONS)
    review.add_argument("--actor", required=True)
    review.add_argument("--reason", required=True)
    review.add_argument("--content-hash", required=True)
    review.add_argument("--idempotency-key", required=True)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        ledger = canonical_ledger_path()
        if args.command == "list":
            result = list_candidates(ledger, limit=args.limit)
        elif args.command == "inspect":
            result = inspect_candidate(ledger, args.experience_id)
        else:
            result = append_review(
                ledger, experience_id=args.experience_id,
                decision=args.decision, actor=args.actor, reason=args.reason,
                content_hash=args.content_hash,
                idempotency_key=args.idempotency_key)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)},
                         ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

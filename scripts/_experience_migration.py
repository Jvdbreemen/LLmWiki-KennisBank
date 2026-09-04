#!/usr/bin/env python3
"""Recoverable migration from the mixed experimental experience database."""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
from pathlib import Path

from _experience import ensure_ledger_schema, ledger_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tables(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    conn = None
    try:
        conn = sqlite3.connect(path)
        names = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        result = {}
        for name in names:
            quoted = name.replace('"', '""')
            result[name] = int(conn.execute(
                f'SELECT count(*) FROM "{quoted}"').fetchone()[0])
        return result
    except sqlite3.DatabaseError:
        return {}
    finally:
        if conn is not None:
            conn.close()


def preflight(vault: Path) -> dict:
    root = Path(vault)
    legacy = root / ".claude" / "kb-experience.db"
    target = ledger_path(root)
    digest = _sha256(legacy) if legacy.is_file() else ""
    backup = legacy.with_name(f"{legacy.name}.backup-{digest[:12]}") if digest else None
    return {
        "status": "ready" if legacy.is_file() else "no_legacy",
        "mutated": False,
        "legacy_exists": legacy.is_file(),
        "legacy_sha256": digest,
        "legacy_tables": _tables(legacy),
        "target_exists": target.is_file(),
        "backup_path": str(backup) if backup else "",
    }


def _row_dicts(conn, table: str) -> list[dict]:
    try:
        cursor = conn.execute(f'SELECT * FROM "{table}"')
    except sqlite3.OperationalError:
        return []
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _copy_canonical(legacy: sqlite3.Connection, stage: sqlite3.Connection) -> dict[str, int]:
    event_rows = _row_dicts(legacy, "experience_events")
    outcome_rows = _row_dicts(legacy, "experience_outcomes")
    review_rows = _row_dicts(legacy, "experience_reviews")
    for row in event_rows:
        stage.execute(
            "INSERT OR IGNORE INTO experience_events(event_id, session_id, task_id, "
            "event_type, observed_at, payload_json, source_refs_json, schema_version) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (str(row.get("event_id") or ""), str(row.get("session_id") or ""),
             str(row.get("task_id") or ""), str(row.get("event_type") or "observation"),
             str(row.get("observed_at") or ""), str(row.get("payload_json") or "{}"),
             str(row.get("source_refs_json") or "[]"), str(row.get("schema_version") or "1")))
    for row in outcome_rows:
        stage.execute(
            "INSERT OR IGNORE INTO experience_outcomes(outcome_id, session_id, task_id, "
            "state, evidence_json, attribution_strength, observed_at) VALUES (?,?,?,?,?,?,?)",
            (str(row.get("outcome_id") or ""), str(row.get("session_id") or ""),
             str(row.get("task_id") or ""), str(row.get("state") or "unknown"),
             str(row.get("evidence_json") or "[]"),
             str(row.get("attribution_strength") or "unknown"),
             str(row.get("observed_at") or "")))
    for row in review_rows:
        stage.execute(
            "INSERT OR IGNORE INTO experience_reviews(review_id, experience_id, decision, "
            "actor, reviewed_at, reason, content_hash, schema_version, idempotency_key) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (str(row.get("review_id") or ""), str(row.get("experience_id") or ""),
             str(row.get("decision") or "rejected"), str(row.get("actor") or "legacy"),
             str(row.get("reviewed_at") or ""), str(row.get("reason") or ""),
             str(row.get("content_hash") or ""), str(row.get("schema_version") or "1"),
             str(row.get("idempotency_key") or row.get("review_id") or "")))
    return {
        "experience_events": len(event_rows),
        "experience_outcomes": len(outcome_rows),
        "experience_reviews": len(review_rows),
    }


def _current_for_legacy(target: Path, legacy_sha: str) -> bool:
    if not target.is_file():
        return False
    conn = None
    try:
        conn = sqlite3.connect(target)
        row = conn.execute(
            "SELECT value FROM _migration_meta WHERE key='legacy_sha256'").fetchone()
        return bool(row and row[0] == legacy_sha)
    except sqlite3.DatabaseError:
        return False
    finally:
        if conn is not None:
            conn.close()


def migrate(vault: Path, *, dry_run: bool = False, before_swap=None) -> dict:
    """Copy canonical rows through a staged ledger and preserve legacy data."""
    root = Path(vault)
    report = preflight(root)
    if not report["legacy_exists"]:
        return report
    if dry_run:
        return report

    legacy = root / ".claude" / "kb-experience.db"
    target = ledger_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    legacy_sha = report["legacy_sha256"]
    if _current_for_legacy(target, legacy_sha):
        report.update({"status": "current", "mutated": False})
        return report

    backup = Path(report["backup_path"])
    stage = target.with_name(target.name + ".staging")
    try:
        if not backup.exists():
            shutil.copy2(legacy, backup)
        if _sha256(backup) != legacy_sha:
            raise OSError("legacy backup hash mismatch")
        if stage.exists():
            stage.unlink()
        legacy_conn = sqlite3.connect(legacy)
        stage_conn = sqlite3.connect(stage)
        try:
            ensure_ledger_schema(stage_conn)
            expected_counts = _copy_canonical(legacy_conn, stage_conn)
            actual_counts = {
                table: int(stage_conn.execute(
                    f'SELECT count(*) FROM "{table}"').fetchone()[0])
                for table in expected_counts
            }
            if actual_counts != expected_counts:
                raise sqlite3.DatabaseError(
                    f"canonical row count mismatch: {actual_counts} != {expected_counts}")
            stage_conn.execute(
                "CREATE TABLE IF NOT EXISTS _migration_meta "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            stage_conn.execute(
                "INSERT OR REPLACE INTO _migration_meta(key, value) VALUES (?, ?)",
                ("legacy_sha256", legacy_sha))
            stage_conn.commit()
            integrity = stage_conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise sqlite3.DatabaseError(f"staged ledger integrity: {integrity}")
        finally:
            legacy_conn.close()
            stage_conn.close()
        if before_swap is not None:
            before_swap()
        os.replace(stage, target)
        report.update({"status": "ok", "mutated": True,
                       "target_tables": _tables(target),
                       "verified_counts": expected_counts})
        return report
    except Exception as exc:
        if stage.exists():
            stage.unlink()
        report.update({"status": "failed", "mutated": False,
                       "reason": type(exc).__name__})
        return report

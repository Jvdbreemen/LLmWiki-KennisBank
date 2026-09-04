#!/usr/bin/env python3
"""Append-only task experiences plus an evidence-gated retrieval projection."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kbindex  # noqa: E402


_STATUSES = {"candidate", "validated", "superseded", "retracted", "unknown"}
_EVENT_TYPES = {"task_context", "attempt", "observation", "test_result",
                "commit", "failure", "fix", "decision", "user_feedback"}
_OUTCOME_STATES = {"success", "failure", "partial", "mixed", "unknown"}
_ATTEMPT_STATES = _OUTCOME_STATES
_RESOLUTION_STATES = {"not_applicable", "unresolved", "diagnosed",
                      "fix_proposed", "fix_validated", "corrected_with_cost"}

# Selected on the independent 21-case advisory development set (2026-08-30):
# precision 0.909, false-warning rate 0.10, positive recall 0.909, and +0.182
# recall over the lexical-only arm. Recalibrate before changing this value.
FAILURE_ADVISORY_MIN_COS = 0.50


def ledger_path(vault: Path) -> Path:
    return Path(vault) / ".claude" / "kb-experience-ledger.db"


def projection_path(vault: Path) -> Path:
    return Path(vault) / ".claude" / "kb-experience-index.db"


def connect(path=None):
    p = str(path) if path is not None else str(Path.cwd() / "kb-experience.db")
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(p)


def ensure_ledger_schema(conn) -> None:
    """Create canonical append-only tables without retrieval projections."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS experience_events (
        event_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        source_refs_json TEXT NOT NULL,
        schema_version TEXT NOT NULL DEFAULT '1'
    );
    CREATE TABLE IF NOT EXISTS experience_outcomes (
        outcome_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        state TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        attribution_strength TEXT NOT NULL,
        observed_at TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS experience_reviews (
        review_id TEXT PRIMARY KEY,
        experience_id TEXT NOT NULL,
        decision TEXT NOT NULL,
        actor TEXT NOT NULL,
        reviewed_at TEXT NOT NULL,
        reason TEXT NOT NULL DEFAULT '',
        content_hash TEXT NOT NULL,
        schema_version TEXT NOT NULL DEFAULT '1',
        idempotency_key TEXT NOT NULL UNIQUE
    );
    CREATE INDEX IF NOT EXISTS idx_experience_reviews_target
        ON experience_reviews(experience_id, reviewed_at);
    """)
    conn.commit()


def _ensure_experience_rows_schema(conn) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS experiences (
        experience_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        status TEXT NOT NULL,
        situation TEXT NOT NULL,
        goal TEXT NOT NULL DEFAULT '',
        approach TEXT NOT NULL,
        action TEXT NOT NULL DEFAULT '',
        observed_result TEXT NOT NULL,
        lesson TEXT NOT NULL,
        applicability TEXT NOT NULL,
        outcome_state TEXT NOT NULL,
        attempt_state TEXT NOT NULL DEFAULT 'unknown',
        resolution_state TEXT NOT NULL DEFAULT 'not_applicable',
        confidence REAL NOT NULL,
        source_refs_json TEXT NOT NULL,
        outcome_refs_json TEXT NOT NULL,
        exposed_refs_json TEXT NOT NULL DEFAULT '[]',
        procedure_refs_json TEXT NOT NULL DEFAULT '[]',
        skill_refs_json TEXT NOT NULL DEFAULT '[]',
        attribution_limits TEXT NOT NULL DEFAULT '',
        schema_version TEXT NOT NULL DEFAULT '1',
        extractor_version TEXT NOT NULL DEFAULT '1',
        superseded_by TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_experiences_status ON experiences(status);
    CREATE INDEX IF NOT EXISTS idx_experiences_outcome ON experiences(outcome_state);
    CREATE INDEX IF NOT EXISTS idx_experiences_attempt ON experiences(attempt_state);
    """)


def ensure_projection_schema(conn, *, dim: int, embed_id: str) -> None:
    """Create a disposable retrieval projection without canonical history."""
    conn.enable_load_extension(True)
    conn.load_extension(_kbindex.vec0_extension())
    conn.enable_load_extension(False)
    _kbindex.ensure_schema(conn, dim, embed_id)
    _ensure_experience_rows_schema(conn)
    conn.commit()


def projection_upsert(conn, record: dict) -> None:
    """Materialize one already-derived record into a disposable projection."""
    fields = (
        "experience_id", "session_id", "task_id", "status", "situation", "goal",
        "approach", "action", "observed_result", "lesson", "applicability",
        "outcome_state", "attempt_state", "resolution_state", "confidence",
        "source_refs", "outcome_refs", "exposed_refs", "procedure_refs",
        "skill_refs", "attribution_limits", "schema_version", "extractor_version",
        "superseded_by",
    )
    defaults = {
        "goal": "", "action": "", "attempt_state": "unknown",
        "resolution_state": "not_applicable", "confidence": 0.0,
        "source_refs": [], "outcome_refs": [], "exposed_refs": [],
        "procedure_refs": [], "skill_refs": [], "attribution_limits": "",
        "schema_version": "1", "extractor_version": "1", "superseded_by": None,
    }
    values = {field: record.get(field, defaults.get(field, "")) for field in fields}
    for field in ("source_refs", "outcome_refs", "exposed_refs", "procedure_refs", "skill_refs"):
        values[field] = _json(values[field])
    conn.execute(
        "INSERT OR REPLACE INTO experiences(experience_id, session_id, task_id, status, "
        "situation, goal, approach, action, observed_result, lesson, applicability, "
        "outcome_state, attempt_state, resolution_state, confidence, source_refs_json, "
        "outcome_refs_json, exposed_refs_json, procedure_refs_json, skill_refs_json, "
        "attribution_limits, schema_version, extractor_version, superseded_by) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        tuple(values[field] for field in fields))


def index_experience_lexical(conn, experience_id: str) -> int:
    """Index one projected experience for FTS without manufacturing a vector."""
    record = experience(conn, experience_id)
    if record is None:
        raise KeyError(experience_id)
    body = " ".join((record["situation"], record["goal"], record["approach"],
                     record["action"], record["lesson"], record["applicability"]))
    path = f"experience::{experience_id}"
    doc_id = conn.execute(
        "INSERT INTO docs(path, layer, status, hash, title, created) "
        "VALUES (?,?,?,?,?,?)",
        (path, "experience", record["status"], experience_id,
         record["lesson"], "")).lastrowid
    conn.execute("INSERT INTO fts_docs(rowid, body) VALUES (?, ?)", (doc_id, body))
    for source in record["source_refs"]:
        conn.execute("INSERT INTO doc_sources(doc_id, source) VALUES (?, ?)",
                     (doc_id, json.dumps(source, sort_keys=True)
                      if isinstance(source, dict) else str(source)))
    return int(doc_id)


def ensure_schema(conn) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS experience_events (
        event_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        source_refs_json TEXT NOT NULL,
        schema_version TEXT NOT NULL DEFAULT '1'
    );
    CREATE TABLE IF NOT EXISTS experience_outcomes (
        outcome_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        state TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        attribution_strength TEXT NOT NULL,
        observed_at TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS experiences (
        experience_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        status TEXT NOT NULL,
        situation TEXT NOT NULL,
        goal TEXT NOT NULL DEFAULT '',
        approach TEXT NOT NULL,
        action TEXT NOT NULL DEFAULT '',
        observed_result TEXT NOT NULL,
        lesson TEXT NOT NULL,
        applicability TEXT NOT NULL,
        outcome_state TEXT NOT NULL,
        attempt_state TEXT NOT NULL DEFAULT 'unknown',
        resolution_state TEXT NOT NULL DEFAULT 'not_applicable',
        confidence REAL NOT NULL,
        source_refs_json TEXT NOT NULL,
        outcome_refs_json TEXT NOT NULL,
        exposed_refs_json TEXT NOT NULL DEFAULT '[]',
        procedure_refs_json TEXT NOT NULL DEFAULT '[]',
        skill_refs_json TEXT NOT NULL DEFAULT '[]',
        attribution_limits TEXT NOT NULL DEFAULT '',
        schema_version TEXT NOT NULL DEFAULT '1',
        extractor_version TEXT NOT NULL DEFAULT '1',
        superseded_by TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_experiences_status ON experiences(status);
    CREATE INDEX IF NOT EXISTS idx_experiences_outcome ON experiences(outcome_state);
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(experiences)")}
    for name in ("exposed_refs_json", "procedure_refs_json", "skill_refs_json"):
        if name not in columns:
            conn.execute(f"ALTER TABLE experiences ADD COLUMN {name} TEXT NOT NULL DEFAULT '[]'")
    if "attempt_state" not in columns:
        conn.execute("ALTER TABLE experiences ADD COLUMN attempt_state "
                     "TEXT NOT NULL DEFAULT 'unknown'")
    if "resolution_state" not in columns:
        conn.execute("ALTER TABLE experiences ADD COLUMN resolution_state "
                     "TEXT NOT NULL DEFAULT 'not_applicable'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_experiences_attempt "
                 "ON experiences(attempt_state)")
    conn.commit()


def _json(value) -> str:
    return json.dumps(value or [], ensure_ascii=False, sort_keys=True)


def append_event(conn, *, event_id: str, session_id: str, task_id: str,
                 event_type: str, observed_at: str, payload: dict,
                 source_refs=(), schema_version: str = "1") -> bool:
    if event_type not in _EVENT_TYPES:
        raise ValueError(f"invalid event type: {event_type}")
    row = conn.execute("SELECT payload_json, session_id, task_id, event_type, "
                       "observed_at, source_refs_json, schema_version "
                       "FROM experience_events WHERE event_id=?", (event_id,)).fetchone()
    values = (session_id, task_id, event_type, observed_at, _json(payload),
              _json(source_refs), schema_version)
    if row:
        if row != (values[4], values[0], values[1], values[2], values[3],
                   values[5], values[6]):
            raise ValueError(f"event id already contains a different payload: {event_id}")
        return False
    conn.execute(
        "INSERT INTO experience_events(event_id, session_id, task_id, event_type, "
        "observed_at, payload_json, source_refs_json, schema_version) VALUES (?,?,?,?,?,?,?,?)",
        (event_id, *values))
    conn.commit()
    return True


def record_outcome(conn, *, outcome_id: str, session_id: str, task_id: str,
                   state: str, evidence, attribution_strength: str,
                   observed_at: str = "") -> bool:
    if state not in _OUTCOME_STATES:
        raise ValueError("invalid outcome state")
    values = (session_id, task_id, state, _json(evidence), attribution_strength, observed_at)
    row = conn.execute("SELECT session_id, task_id, state, evidence_json, "
                       "attribution_strength, observed_at FROM experience_outcomes "
                       "WHERE outcome_id=?", (outcome_id,)).fetchone()
    if row:
        if row != values:
            raise ValueError(f"outcome id already contains different evidence: {outcome_id}")
        return False
    conn.execute(
        "INSERT INTO experience_outcomes(outcome_id, session_id, task_id, state, "
        "evidence_json, attribution_strength, observed_at) VALUES (?,?,?,?,?,?,?)",
        (outcome_id, *values))
    conn.commit()
    return True


def outcome(conn, outcome_id: str) -> dict | None:
    row = conn.execute("SELECT outcome_id, session_id, task_id, state, evidence_json, "
                       "attribution_strength, observed_at FROM experience_outcomes "
                       "WHERE outcome_id=?", (outcome_id,)).fetchone()
    if not row:
        return None
    keys = ("outcome_id", "session_id", "task_id", "state", "evidence",
            "attribution_strength", "observed_at")
    result = dict(zip(keys, row))
    result["evidence"] = json.loads(result["evidence"] or "[]")
    return result


def save_experience(conn, *, experience_id: str, session_id: str, task_id: str,
                    status: str, situation: str, approach: str,
                    observed_result: str, lesson: str, applicability: str,
                    outcome_state: str, confidence: float, source_refs=(),
                    outcome_refs=(), goal: str = "", action: str = "",
                    attempt_state: str = "unknown",
                    resolution_state: str = "not_applicable",
                    exposed_refs=(), procedure_refs=(), skill_refs=(),
                    attribution_limits: str = "", schema_version: str = "1",
                    extractor_version: str = "1") -> bool:
    if status not in _STATUSES:
        raise ValueError("invalid experience status")
    source_refs, outcome_refs = list(source_refs or []), list(outcome_refs or [])
    exposed_refs = list(exposed_refs or [])
    procedure_refs = list(procedure_refs or [])
    skill_refs = list(skill_refs or [])
    if outcome_state not in _OUTCOME_STATES:
        raise ValueError("invalid experience outcome state")
    if attempt_state not in _ATTEMPT_STATES:
        raise ValueError("invalid experience attempt state")
    if resolution_state not in _RESOLUTION_STATES:
        raise ValueError("invalid experience resolution state")
    if status == "validated":
        if not source_refs or not outcome_refs:
            raise ValueError("validated experience requires source and outcome evidence")
        if any(outcome(conn, ref) is None for ref in outcome_refs):
            raise ValueError("validated experience refers to an unknown outcome")
        if outcome_state == "unknown":
            raise ValueError("unknown outcome cannot be validated")
    row = conn.execute("SELECT status, situation, goal, approach, action, observed_result, "
                       "lesson, applicability, outcome_state, confidence, source_refs_json, "
                       "attempt_state, resolution_state, "
                       "outcome_refs_json, exposed_refs_json, procedure_refs_json, "
                       "skill_refs_json, attribution_limits, schema_version, extractor_version "
                       "FROM experiences WHERE experience_id=?", (experience_id,)).fetchone()
    values = (session_id, task_id, status, situation, goal, approach, action, observed_result,
              lesson, applicability, outcome_state, float(confidence), _json(source_refs),
              attempt_state, resolution_state,
              _json(outcome_refs), _json(exposed_refs), _json(procedure_refs),
              _json(skill_refs), attribution_limits, schema_version, extractor_version)
    if row:
        # Event history remains immutable; a derived record can be re-derived,
        # but an accidental conflicting write must not silently overwrite it.
        if row != values[2:]:
            raise ValueError(f"experience id already contains a different record: {experience_id}")
        return False
    conn.execute(
        "INSERT INTO experiences(experience_id, session_id, task_id, status, situation, goal, "
        "approach, action, observed_result, lesson, applicability, outcome_state, confidence, "
        "source_refs_json, attempt_state, resolution_state, outcome_refs_json, "
        "exposed_refs_json, procedure_refs_json, "
        "skill_refs_json, attribution_limits, schema_version, extractor_version) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (experience_id, *values))
    conn.commit()
    return True


def experience(conn, experience_id: str) -> dict | None:
    row = conn.execute("SELECT experience_id, session_id, task_id, status, situation, goal, "
                       "approach, action, observed_result, lesson, applicability, outcome_state, "
                       "confidence, source_refs_json, attempt_state, resolution_state, "
                       "outcome_refs_json, exposed_refs_json, "
                       "procedure_refs_json, skill_refs_json, attribution_limits, "
                       "schema_version, extractor_version, superseded_by FROM experiences "
                       "WHERE experience_id=?", (experience_id,)).fetchone()
    if not row:
        return None
    keys = ("experience_id", "session_id", "task_id", "status", "situation", "goal",
            "approach", "action", "observed_result", "lesson", "applicability",
            "outcome_state", "confidence", "source_refs", "attempt_state",
            "resolution_state", "outcome_refs",
            "exposed_refs", "procedure_refs", "skill_refs", "attribution_limits",
            "schema_version", "extractor_version", "superseded_by")
    result = dict(zip(keys, row))
    for key in ("source_refs", "outcome_refs", "exposed_refs", "procedure_refs", "skill_refs"):
        result[key] = json.loads(result[key] or "[]")
    return result


def transition(conn, experience_id: str, status: str, *, superseded_by: str | None = None) -> bool:
    if status not in _STATUSES:
        raise ValueError("invalid experience status")
    current = experience(conn, experience_id)
    if current is None:
        raise KeyError(experience_id)
    if status == "validated":
        if not current["source_refs"] or not current["outcome_refs"] or current["outcome_state"] == "unknown":
            raise ValueError("experience lacks validation evidence")
        if any(outcome(conn, ref) is None for ref in current["outcome_refs"]):
            raise ValueError("experience lacks resolvable outcome evidence")
    conn.execute("UPDATE experiences SET status=?, superseded_by=? WHERE experience_id=?",
                 (status, superseded_by, experience_id))
    try:
        conn.execute("UPDATE docs SET status=? WHERE path=?", (status, f"experience::{experience_id}"))
    except sqlite3.OperationalError:
        # The durable store is useful without the optional vector projection.
        pass
    conn.commit()
    return True


def ensure_recall_schema(conn, *, dim: int, embed_id: str) -> None:
    conn.enable_load_extension(True)
    conn.load_extension(_kbindex.vec0_extension())
    conn.enable_load_extension(False)
    _kbindex.ensure_schema(conn, dim, embed_id)


def index_experience(conn, experience_id: str, *, vector) -> int:
    record = experience(conn, experience_id)
    if record is None:
        raise KeyError(experience_id)
    body = " ".join((record["situation"], record["goal"], record["approach"],
                      record["action"], record["lesson"], record["applicability"]))
    return _kbindex.upsert(
        conn, path=f"experience::{experience_id}", layer="experience",
        status=record["status"], body=body, vector=vector,
        file_hash=experience_id, title=record["lesson"], created="",
        sources=record["source_refs"])


def experience_hits(conn, *, query_vector, query_text: str = "", k: int = 8,
                    statuses=("validated",)) -> list[dict]:
    rows = _kbindex.search(conn, query_vector=query_vector, query_text=query_text,
                           k=k, layers=("experience",), statuses=statuses,
                           min_cos=0.2, fusion="rrf")
    result = []
    for row in rows:
        if not row["fts"] and float(row.get("cos") or 0.0) < 0.2:
            continue
        experience_id = row["path"].removeprefix("experience::")
        item = experience(conn, experience_id)
        if item is None:
            continue
        item.update({"score": row["score"], "cos": row["cos"], "fts": row["fts"],
                     "doc_id": row["doc_id"]})
        result.append(item)
    return result


def failure_advisory(conn, *, query_vector, query_text: str = "",
                     min_score: float = FAILURE_ADVISORY_MIN_COS):
    for item in experience_hits(conn, query_vector=query_vector, query_text=query_text,
                                k=8, statuses=("validated",)):
        attempt_state = item.get("attempt_state") or "unknown"
        if attempt_state != "failure" and not (
                attempt_state == "unknown" and item["outcome_state"] == "failure"):
            continue
        if float(item.get("cos") or 0.0) < min_score:
            continue
        item["advisory"] = True
        return item
    return None

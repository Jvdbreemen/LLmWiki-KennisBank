#!/usr/bin/env python3
"""Append-only task experiences plus an evidence-gated retrieval projection."""
from __future__ import annotations

import hashlib
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
_EVIDENCE_STATES = {"unverified", "verified", "stale", "missing", "contradictory", "redacted"}
_REVIEW_STATES = {"unreviewed", "accepted", "rejected"}
_REVIEW_DECISIONS = {"accepted", "rejected"}
_NON_RETRIEVABLE_STATUSES = {"superseded", "retracted"}
_EVIDENCE_PRIORITY = {
    "verified": 0,
    "unverified": 1,
    "missing": 2,
    "stale": 3,
    "contradictory": 4,
    "redacted": 5,
}

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
        evidence_state TEXT NOT NULL DEFAULT 'unverified',
        review_state TEXT NOT NULL DEFAULT 'unreviewed',
        content_hash TEXT NOT NULL DEFAULT '',
        superseded_by TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_experiences_status ON experiences(status);
    CREATE INDEX IF NOT EXISTS idx_experiences_outcome ON experiences(outcome_state);
    CREATE INDEX IF NOT EXISTS idx_experiences_attempt ON experiences(attempt_state);
    """)


def _ensure_lexical_recall_schema(conn, *, embed_id: str = "") -> None:
    """Create the projection tables that remain usable without sqlite-vec."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    CREATE TABLE IF NOT EXISTS docs (
        doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE,
        layer TEXT,
        status TEXT,
        hash TEXT,
        title TEXT,
        created TEXT
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS fts_docs USING fts5(body);
    CREATE TABLE IF NOT EXISTS doc_sources (
        doc_id INTEGER NOT NULL,
        source TEXT NOT NULL,
        PRIMARY KEY (doc_id, source)
    );
    CREATE INDEX IF NOT EXISTS idx_doc_sources_source
        ON doc_sources(source);
    """)
    if embed_id:
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('embed_id', ?)",
            (embed_id,))
    conn.commit()


def enable_recall_vectors(conn) -> None:
    """Load sqlite-vec for an already-built compatible projection."""
    conn.enable_load_extension(True)
    try:
        conn.load_extension(_kbindex.vec0_extension())
    finally:
        conn.enable_load_extension(False)


def ensure_projection_schema(conn, *, dim: int | None, embed_id: str) -> None:
    """Create a disposable lexical or hybrid projection, never canonical history."""
    _ensure_lexical_recall_schema(conn, embed_id=embed_id)
    if dim is not None and int(dim) > 0:
        enable_recall_vectors(conn)
        _kbindex.ensure_schema(conn, int(dim), embed_id)
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
        "evidence_state", "review_state", "content_hash", "superseded_by",
    )
    defaults = {
        "goal": "", "action": "", "attempt_state": "unknown",
        "resolution_state": "not_applicable", "confidence": 0.0,
        "source_refs": [], "outcome_refs": [], "exposed_refs": [],
        "procedure_refs": [], "skill_refs": [], "attribution_limits": "",
        "schema_version": "1", "extractor_version": "1", "superseded_by": None,
        "evidence_state": "unverified", "review_state": "unreviewed",
        "content_hash": "",
    }
    values = {field: record.get(field, defaults.get(field, "")) for field in fields}
    for field in ("source_refs", "outcome_refs", "exposed_refs", "procedure_refs", "skill_refs"):
        values[field] = _json(values[field])
    conn.execute(
        "INSERT OR REPLACE INTO experiences(experience_id, session_id, task_id, status, "
        "situation, goal, approach, action, observed_result, lesson, applicability, "
        "outcome_state, attempt_state, resolution_state, confidence, source_refs_json, "
        "outcome_refs_json, exposed_refs_json, procedure_refs_json, skill_refs_json, "
        "attribution_limits, schema_version, extractor_version, evidence_state, "
        "review_state, content_hash, superseded_by) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        tuple(values[field] for field in fields))


def index_experience_lexical(conn, experience_id: str) -> int:
    """Index one projected experience for FTS without manufacturing a vector."""
    record = experience(conn, experience_id)
    if record is None:
        raise KeyError(experience_id)
    body = " ".join((record["situation"], record["goal"], record["approach"],
                     record["action"], record["lesson"], record["applicability"]))
    path = f"experience::{experience_id}"
    previous = conn.execute("SELECT doc_id FROM docs WHERE path=?", (path,)).fetchone()
    if previous:
        doc_id = int(previous[0])
        conn.execute("DELETE FROM fts_docs WHERE rowid=?", (doc_id,))
        conn.execute("DELETE FROM doc_sources WHERE doc_id=?", (doc_id,))
        conn.execute(
            "UPDATE docs SET layer=?, status=?, hash=?, title=?, created=? "
            "WHERE doc_id=?", ("experience", record["status"], experience_id,
                                record["lesson"], "", doc_id))
    else:
        doc_id = conn.execute(
            "INSERT INTO docs(path, layer, status, hash, title, created) "
            "VALUES (?,?,?,?,?,?)",
            (path, "experience", record["status"], experience_id,
             record["lesson"], "")).lastrowid
    conn.execute("INSERT INTO fts_docs(rowid, body) VALUES (?, ?)", (doc_id, body))
    for source_ref_id_value in _source_ref_ids(record):
        conn.execute("INSERT INTO doc_sources(doc_id, source) VALUES (?, ?)",
                     (doc_id, source_ref_id_value))
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
        evidence_state TEXT NOT NULL DEFAULT 'unverified',
        review_state TEXT NOT NULL DEFAULT 'unreviewed',
        content_hash TEXT NOT NULL DEFAULT '',
        superseded_by TEXT
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
    CREATE INDEX IF NOT EXISTS idx_experiences_status ON experiences(status);
    CREATE INDEX IF NOT EXISTS idx_experiences_outcome ON experiences(outcome_state);
    CREATE INDEX IF NOT EXISTS idx_experience_reviews_target
        ON experience_reviews(experience_id, reviewed_at);
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
    if "evidence_state" not in columns:
        conn.execute("ALTER TABLE experiences ADD COLUMN evidence_state "
                     "TEXT NOT NULL DEFAULT 'unverified'")
    if "review_state" not in columns:
        conn.execute("ALTER TABLE experiences ADD COLUMN review_state "
                     "TEXT NOT NULL DEFAULT 'unreviewed'")
    if "content_hash" not in columns:
        conn.execute("ALTER TABLE experiences ADD COLUMN content_hash "
                     "TEXT NOT NULL DEFAULT ''")
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


_CONTENT_FIELDS = (
    "experience_id", "session_id", "task_id", "situation", "goal", "approach",
    "action", "observed_result", "lesson", "applicability", "outcome_state",
    "attempt_state", "resolution_state", "source_refs", "outcome_refs",
    "exposed_refs", "procedure_refs", "skill_refs", "attribution_limits",
    "schema_version", "extractor_version",
)


def experience_content_hash(record: dict) -> str:
    """Hash review-relevant content; lifecycle/confidence cannot preserve review."""
    payload = {key: record.get(key, "") for key in _CONTENT_FIELDS}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def record_review(conn, *, review_id: str, experience_id: str, decision: str,
                  actor: str, reviewed_at: str, content_hash: str,
                  reason: str = "", schema_version: str = "1",
                  idempotency_key: str = "") -> bool:
    """Append one immutable human review decision, idempotently."""
    if decision not in _REVIEW_DECISIONS:
        raise ValueError("invalid review decision")
    required = {
        "review_id": review_id, "experience_id": experience_id, "actor": actor,
        "reviewed_at": reviewed_at, "reason": reason,
        "schema_version": schema_version,
    }
    missing = [name for name, value in required.items() if not str(value or "").strip()]
    if missing:
        raise ValueError("review requires non-empty " + ", ".join(missing))
    digest = str(content_hash or "")
    if (not digest.startswith("sha256:") or len(digest) != 71
            or any(char not in "0123456789abcdef" for char in digest[7:])):
        raise ValueError("review requires a content hash")
    key = str(idempotency_key or review_id).strip()
    if not key:
        raise ValueError("review requires an idempotency key")
    values = (experience_id, decision, actor, reviewed_at, reason,
              content_hash, schema_version, key)
    row = conn.execute(
        "SELECT experience_id, decision, actor, reviewed_at, reason, content_hash, "
        "schema_version, idempotency_key FROM experience_reviews WHERE review_id=?",
        (review_id,)).fetchone()
    if row:
        if row != values:
            raise ValueError(f"review id already contains a different decision: {review_id}")
        return False
    idempotent = conn.execute(
        "SELECT review_id, experience_id, decision, actor, reviewed_at, reason, "
        "content_hash, schema_version, idempotency_key FROM experience_reviews "
        "WHERE idempotency_key=?", (key,)).fetchone()
    if idempotent:
        if idempotent[1:] != values:
            raise ValueError(f"idempotency key already contains a different review: {key}")
        return False
    conn.execute(
        "INSERT INTO experience_reviews(review_id, experience_id, decision, actor, "
        "reviewed_at, reason, content_hash, schema_version, idempotency_key) "
        "VALUES (?,?,?,?,?,?,?,?,?)", (review_id, *values))
    try:
        state = decision if decision in _REVIEW_STATES else "unreviewed"
        conn.execute(
            "UPDATE experiences SET review_state=? WHERE experience_id=? AND content_hash=?",
            (state, experience_id, content_hash))
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return True


def review_for_content(conn, experience_id: str, content_hash: str) -> dict | None:
    row = conn.execute(
        "SELECT review_id, decision, actor, reviewed_at, reason, content_hash, "
        "schema_version, idempotency_key FROM experience_reviews "
        "WHERE experience_id=? AND content_hash=? ORDER BY rowid DESC LIMIT 1",
        (experience_id, content_hash)).fetchone()
    if not row:
        return None
    keys = ("review_id", "decision", "actor", "reviewed_at", "reason",
            "content_hash", "schema_version", "idempotency_key")
    return dict(zip(keys, row))


def _review_state(review: dict | None) -> str:
    """Return a trusted state only for a complete append-only review record."""
    if review is None:
        return "unreviewed"
    required = ("review_id", "actor", "reviewed_at", "reason", "content_hash",
                "schema_version", "idempotency_key")
    if any(not str(review.get(field) or "").strip() for field in required):
        return "unreviewed"
    decision = str(review.get("decision") or "")
    return decision if decision in _REVIEW_DECISIONS else "unreviewed"


def review_state_for_content(conn, experience_id: str, content_hash: str) -> str:
    """Return the latest complete append-only review state for exact content."""
    return _review_state(review_for_content(conn, experience_id, content_hash))


def _combine_evidence_states(*states: str) -> str:
    return max(states, key=lambda state: _EVIDENCE_PRIORITY[state])


def validate_projection_record(ledger_conn, record: dict, *, vault: Path) -> dict:
    """Derive trusted projection state from exact evidence plus human review."""
    result = dict(record)
    result["content_hash"] = experience_content_hash(result)
    refs = list(result.get("source_refs") or [])
    source_state = "missing" if not refs else "verified"
    if refs:
        from _source_ref import resolve_source_ref
        states = []
        for ref in refs:
            if not isinstance(ref, dict):
                states.append("unverified")
            else:
                states.append(resolve_source_ref(vault, ref).get("status", "invalid"))
        if "redacted" in states:
            source_state = "redacted"
        elif "missing" in states or "unreadable" in states:
            source_state = "missing"
        elif "stale" in states or "invalid" in states:
            source_state = "stale"
        elif "unverified" in states:
            source_state = "unverified"
        elif all(state == "valid" for state in states):
            source_state = "verified"
    outcome_rows = [outcome(ledger_conn, ref)
                    for ref in (result.get("outcome_refs") or [])]
    if not outcome_rows or any(item is None for item in outcome_rows):
        outcome_evidence_state = "missing"
    elif any(item["session_id"] != result.get("session_id")
             or item["task_id"] != result.get("task_id") for item in outcome_rows):
        outcome_evidence_state = "contradictory"
    elif result.get("outcome_state") == "mixed":
        outcome_evidence_state = "contradictory"
    elif result.get("outcome_state") == "unknown":
        outcome_evidence_state = "unverified"
    else:
        outcome_evidence_state = "verified"
    version_state = ("verified" if str(result.get("schema_version") or "").strip()
                     and str(result.get("extractor_version") or "").strip()
                     else "unverified")
    evidence_state = _combine_evidence_states(
        source_state, outcome_evidence_state, version_state)
    review_state = review_state_for_content(
        ledger_conn, str(result.get("experience_id") or ""), result["content_hash"])
    result["evidence_state"] = evidence_state
    result["review_state"] = review_state
    lifecycle_status = str(record.get("status") or "candidate")
    if lifecycle_status in _NON_RETRIEVABLE_STATUSES:
        result["status"] = lifecycle_status
    else:
        result["status"] = (
            "validated" if evidence_state == "verified" and review_state == "accepted"
            else "candidate")
    result["confidence"] = 0.8 if result["status"] == "validated" else 0.2
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
                    extractor_version: str = "1",
                    evidence_state: str = "unverified",
                    review_state: str = "unreviewed",
                    content_hash: str = "", vault: Path | None = None) -> bool:
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
    if evidence_state not in _EVIDENCE_STATES:
        raise ValueError("invalid evidence state")
    if review_state not in _REVIEW_STATES:
        raise ValueError("invalid review state")
    material = {
        "experience_id": experience_id, "session_id": session_id, "task_id": task_id,
        "situation": situation, "goal": goal, "approach": approach, "action": action,
        "observed_result": observed_result, "lesson": lesson,
        "applicability": applicability, "outcome_state": outcome_state,
        "attempt_state": attempt_state, "resolution_state": resolution_state,
        "source_refs": source_refs, "outcome_refs": outcome_refs,
        "exposed_refs": exposed_refs, "procedure_refs": procedure_refs,
        "skill_refs": skill_refs,
        "attribution_limits": attribution_limits, "schema_version": schema_version,
        "extractor_version": extractor_version,
    }
    expected_hash = experience_content_hash(material)
    if content_hash and content_hash != expected_hash:
        raise ValueError("experience content hash mismatch")
    content_hash = expected_hash
    if status == "validated":
        if vault is None:
            raise ValueError("validated experience requires exact vault validation")
        checked = validate_projection_record(
            conn, {**material, "status": "candidate", "confidence": confidence,
                   "content_hash": content_hash}, vault=Path(vault))
        if checked["status"] != "validated":
            raise ValueError(
                "validated experience requires verified evidence and accepted review "
                f"(evidence={checked['evidence_state']}, review={checked['review_state']})")
        evidence_state = checked["evidence_state"]
        review_state = checked["review_state"]
    row = conn.execute("SELECT status, situation, goal, approach, action, observed_result, "
                       "lesson, applicability, outcome_state, confidence, source_refs_json, "
                       "attempt_state, resolution_state, "
                       "outcome_refs_json, exposed_refs_json, procedure_refs_json, "
                       "skill_refs_json, attribution_limits, schema_version, extractor_version, "
                       "evidence_state, review_state, content_hash "
                       "FROM experiences WHERE experience_id=?", (experience_id,)).fetchone()
    values = (session_id, task_id, status, situation, goal, approach, action, observed_result,
              lesson, applicability, outcome_state, float(confidence), _json(source_refs),
              attempt_state, resolution_state,
              _json(outcome_refs), _json(exposed_refs), _json(procedure_refs),
              _json(skill_refs), attribution_limits, schema_version, extractor_version,
              evidence_state, review_state, content_hash)
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
        "skill_refs_json, attribution_limits, schema_version, extractor_version, "
        "evidence_state, review_state, content_hash) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (experience_id, *values))
    conn.commit()
    return True


def experience(conn, experience_id: str) -> dict | None:
    row = conn.execute("SELECT experience_id, session_id, task_id, status, situation, goal, "
                       "approach, action, observed_result, lesson, applicability, outcome_state, "
                       "confidence, source_refs_json, attempt_state, resolution_state, "
                       "outcome_refs_json, exposed_refs_json, "
                       "procedure_refs_json, skill_refs_json, attribution_limits, "
                       "schema_version, extractor_version, evidence_state, review_state, "
                       "content_hash, superseded_by FROM experiences "
                       "WHERE experience_id=?", (experience_id,)).fetchone()
    if not row:
        return None
    keys = ("experience_id", "session_id", "task_id", "status", "situation", "goal",
            "approach", "action", "observed_result", "lesson", "applicability",
            "outcome_state", "confidence", "source_refs", "attempt_state",
            "resolution_state", "outcome_refs",
            "exposed_refs", "procedure_refs", "skill_refs", "attribution_limits",
            "schema_version", "extractor_version", "evidence_state", "review_state",
            "content_hash", "superseded_by")
    result = dict(zip(keys, row))
    for key in ("source_refs", "outcome_refs", "exposed_refs", "procedure_refs", "skill_refs"):
        result[key] = json.loads(result[key] or "[]")
    return result


def transition(conn, experience_id: str, status: str, *,
               superseded_by: str | None = None, vault: Path | None = None) -> bool:
    if status not in _STATUSES:
        raise ValueError("invalid experience status")
    current = experience(conn, experience_id)
    if current is None:
        raise KeyError(experience_id)
    if status == "validated":
        if vault is None:
            raise ValueError("validation transition requires a vault")
        checked = validate_projection_record(conn, current, vault=Path(vault))
        if checked["status"] != "validated":
            raise ValueError(
                "experience failed exact validation "
                f"(evidence={checked['evidence_state']}, review={checked['review_state']})")
        conn.execute(
            "UPDATE experiences SET status=?, evidence_state=?, review_state=?, "
            "content_hash=?, superseded_by=? WHERE experience_id=?",
            (status, checked["evidence_state"], checked["review_state"],
             checked["content_hash"], superseded_by, experience_id))
    else:
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
    enable_recall_vectors(conn)
    _kbindex.ensure_schema(conn, dim, embed_id)


def index_experience(conn, experience_id: str, *, vector) -> int:
    record = experience(conn, experience_id)
    if record is None:
        raise KeyError(experience_id)
    body = " ".join((record["situation"], record["goal"], record["approach"],
                      record["action"], record["lesson"], record["applicability"]))
    sources = [ref.get("source_ref_id", "") if isinstance(ref, dict) else str(ref)
               for ref in record["source_refs"]]
    return _kbindex.upsert(
        conn, path=f"experience::{experience_id}", layer="experience",
        status=record["status"], body=body, vector=vector,
        file_hash=experience_id, title=record["lesson"], created="",
        sources=[source for source in sources if source])


def _source_ref_ids(record: dict) -> list[str]:
    values = []
    for ref in record.get("source_refs") or []:
        if not isinstance(ref, dict):
            return []
        value = ref.get("source_ref_id", "")
        if not value:
            return []
        if value and value not in values:
            values.append(value)
    return values


def _production_eligible(record: dict) -> bool:
    return bool(
        record.get("status") == "validated"
        and record.get("evidence_state") == "verified"
        and record.get("review_state") == "accepted"
        and _source_ref_ids(record)
        and record.get("outcome_refs")
    )


def _decorate_recall_hit(record: dict, *, score: float, cos,
                         fts: bool, doc_id: int, route: str) -> dict:
    item = dict(record)
    item.update({
        "score": float(score), "cos": cos, "fts": bool(fts),
        "doc_id": int(doc_id), "retrieval_route": route,
        "source_ref_ids": _source_ref_ids(record),
        "validation_stamp": {
            "status": record.get("status"),
            "evidence_state": record.get("evidence_state"),
            "review_state": record.get("review_state"),
            "content_hash": record.get("content_hash"),
        },
    })
    return item


def _diversify(hits: list[dict], k: int) -> list[dict]:
    if k <= 0:
        return []
    selected = []
    seen_tasks = set()
    seen_sources = set()
    for item in hits:
        task_key = (item.get("session_id"), item.get("task_id"))
        sources = set(item.get("source_ref_ids") or [])
        if task_key in seen_tasks or sources & seen_sources:
            continue
        selected.append(item)
        seen_tasks.add(task_key)
        seen_sources.update(sources)
        if len(selected) >= min(max(int(k), 0), 3):
            break
    return selected


def vector_projection_compatible(conn, *, embed_id: str, query_dim: int) -> bool:
    """Read-only compatibility check; a recall request must never rewrite meta."""
    try:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        return bool(
            "vec_docs" in tables
            and _kbindex.meta_get(conn, "embed_id") == str(embed_id)
            and int(_kbindex.meta_get(conn, "dim") or 0) == int(query_dim)
        )
    except (sqlite3.Error, TypeError, ValueError):
        return False


def experience_hits(conn, *, query_vector, query_text: str = "", k: int = 3,
                    statuses=("validated",)) -> list[dict]:
    pool = max(12, min(max(int(k), 1) * 4, 100))
    rows = _kbindex.search(conn, query_vector=query_vector, query_text=query_text,
                           k=pool, layers=("experience",), statuses=statuses,
                           min_cos=0.2, fusion="rrf")
    result = []
    for row in rows:
        if not row["fts"] and float(row.get("cos") or 0.0) < 0.2:
            continue
        experience_id = row["path"].removeprefix("experience::")
        item = experience(conn, experience_id)
        if item is None:
            continue
        if tuple(statuses or ()) == ("validated",) and not _production_eligible(item):
            continue
        result.append(_decorate_recall_hit(
            item, score=row["score"], cos=row["cos"], fts=row["fts"],
            doc_id=row["doc_id"], route="hybrid"))
    return _diversify(result, k)


def experience_lexical_hits(conn, *, query_text: str, k: int = 3,
                            statuses=("validated",)) -> list[dict]:
    """Retrieve reviewed lessons through FTS without touching vector tables."""
    expression = _kbindex.fts_expr(query_text)
    if not expression or k <= 0 or not statuses:
        return []
    pool = max(12, min(max(int(k), 1) * 4, 100))
    placeholders = ",".join("?" for _ in statuses)
    try:
        rows = conn.execute(
            "SELECT d.doc_id, d.path, bm25(fts_docs) FROM fts_docs "
            "JOIN docs d ON d.doc_id=fts_docs.rowid "
            f"WHERE fts_docs MATCH ? AND d.layer='experience' "
            f"AND d.status IN ({placeholders}) ORDER BY bm25(fts_docs) LIMIT ?",
            (expression, *statuses, pool)).fetchall()
    except sqlite3.Error:
        return []
    result = []
    for rank, (doc_id, path, bm25_score) in enumerate(rows):
        item = experience(conn, str(path).removeprefix("experience::"))
        if item is None:
            continue
        if tuple(statuses or ()) == ("validated",) and not _production_eligible(item):
            continue
        result.append(_decorate_recall_hit(
            item, score=1.0 / (60 + rank), cos=None, fts=True,
            doc_id=doc_id, route="lexical_fallback"))
        result[-1]["bm25"] = float(bm25_score)
    return _diversify(result, k)


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

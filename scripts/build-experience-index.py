#!/usr/bin/env python3
"""Atomically rebuild the derived experience store from append-only evidence."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import _experience
import _experience_extract as extract

PROJECTION_VERSION = "1"


def experience_id_for(session_id: str, task_id: str) -> str:
    key = f"{session_id}\0{task_id}".encode("utf-8")
    return "experience-" + hashlib.sha256(key).hexdigest()[:20]


def _connect(path: Path):
    conn = _experience.connect(path)
    # A previous recall run may have installed vec0 virtual tables. Load the
    # extension before schema queries; plain experience stores still work when
    # sqlite-vec is not installed.
    try:
        conn.enable_load_extension(True)
        conn.load_extension(_experience._kbindex.vec0_extension())
        conn.enable_load_extension(False)
    except Exception:
        try:
            conn.enable_load_extension(False)
        except Exception:
            pass
    return conn


def _tasks(conn) -> list[tuple[str, str]]:
    rows = conn.execute(
        "SELECT session_id, task_id FROM experience_events "
        "UNION SELECT session_id, task_id FROM experience_outcomes "
        "ORDER BY session_id, task_id").fetchall()
    return [(str(session), str(task)) for session, task in rows]


def _drop_experience_docs(conn) -> None:
    try:
        rows = conn.execute("SELECT doc_id FROM docs WHERE layer='experience'").fetchall()
    except sqlite3.Error:
        return
    for (doc_id,) in rows:
        conn.execute("DELETE FROM docs WHERE doc_id=?", (doc_id,))
        try:
            conn.execute("DELETE FROM fts_docs WHERE rowid=?", (doc_id,))
            conn.execute("DELETE FROM vec_docs WHERE doc_id=?", (doc_id,))
            conn.execute("DELETE FROM doc_sources WHERE doc_id=?", (doc_id,))
        except sqlite3.Error:
            pass


def rebuild_experience_projection(ledger, projection, *, embed_fn=None,
                                  embed_id: str = "", derive_fn=None,
                                  progress_fn=None) -> dict:
    """Atomically rebuild a disposable projection from a canonical ledger."""
    ledger = Path(ledger)
    target = Path(projection)
    if not ledger.is_file():
        return {"status": "failed", "reason": "ledger missing",
                "experiences": 0, "failed_embeddings": []}
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_name(target.name + ".staging")
    if stage.exists():
        stage.unlink()
    ledger_conn = stage_conn = None
    derive = derive_fn or extract.derive_experience_values
    try:
        ledger_conn = _experience.connect(ledger)
        tasks = _tasks(ledger_conn)
        _emit(progress_fn, {"phase": "scan", "current": 0, "total": len(tasks)})
        records = []
        vectors = []
        dimension = None
        failed_embeddings = []
        skipped_candidates = []
        for current, (session_id, task_id) in enumerate(tasks, start=1):
            experience_id = experience_id_for(session_id, task_id)
            record = derive(ledger_conn, session_id, task_id, experience_id)
            record = _experience.validate_projection_record(
                ledger_conn, record, vault=ledger.parent.parent)
            if record["status"] != "validated":
                skipped_candidates.append({
                    "experience_id": experience_id,
                    "evidence_state": record["evidence_state"],
                    "review_state": record["review_state"],
                })
                _emit(progress_fn, {"phase": "derive", "current": current,
                                    "total": len(tasks), "experience_id": experience_id,
                                    "status": "candidate"})
                continue
            records.append(record)
            vector = None
            if embed_fn is not None:
                body = " ".join((record.get("situation", ""), record.get("goal", ""),
                                 record.get("approach", ""), record.get("action", ""),
                                 record.get("lesson", ""), record.get("applicability", "")))
                try:
                    vector = embed_fn(body)
                except Exception:
                    vector = None
                if vector is None or (dimension is not None and len(vector) != dimension):
                    failed_embeddings.append(experience_id)
                elif dimension is None:
                    dimension = len(vector)
            vectors.append(vector)
            _emit(progress_fn, {"phase": "derive", "current": current,
                                "total": len(tasks), "experience_id": experience_id})
        # Publish one honest lexical projection when the optional embedding
        # backend is incomplete, rather than a partial hybrid index.
        if failed_embeddings:
            dimension = None
            vectors = [None for _record in records]
        stage_conn = _experience.connect(stage)
        projection_embed_id = embed_id if dimension is not None else "lexical-only:1"
        _experience.ensure_projection_schema(
            stage_conn, dim=dimension, embed_id=projection_embed_id)
        _experience._kbindex.meta_set(stage_conn, "experience_projection_version",
                                      PROJECTION_VERSION)
        for record, vector in zip(records, vectors):
            _experience.projection_upsert(stage_conn, record)
            if vector is None:
                _experience.index_experience_lexical(stage_conn, record["experience_id"])
            else:
                _experience.index_experience(
                    stage_conn, record["experience_id"], vector=vector)
        stage_conn.commit()
        integrity = stage_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise sqlite3.DatabaseError(f"projection integrity: {integrity}")
        stage_conn.close()
        stage_conn = None
        os.replace(stage, target)
        result = {"status": "ok", "experiences": len(records),
                  "derived_experiences": len(records),
                  "skipped_candidates": skipped_candidates,
                  "vector_status": "ok" if dimension is not None else "lexical_fallback",
                  "failed_embeddings": failed_embeddings,
                  "projection_version": PROJECTION_VERSION}
        _emit(progress_fn, {"phase": "complete", **result})
        return result
    except Exception as exc:
        return {"status": "failed", "reason": str(exc),
                "experiences": 0, "failed_embeddings": []}
    finally:
        if ledger_conn is not None:
            ledger_conn.close()
        if stage_conn is not None:
            stage_conn.close()
        if stage.exists():
            stage.unlink()


def rebuild_experience_store(path, *, rebuild: bool = True, embed_fn=None,
                             embed_id: str = "", derive_fn=None, progress_fn=None) -> dict:
    """Rebuild records and, when supplied, their vector/FTS projection.

    All work happens in ``.staging`` and replaces the target only after every
    derivation and embedding succeeds. The append-only event/outcome tables are
    copied verbatim and are never edited by this operation.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_name(target.name + ".staging")
    if stage.exists():
        stage.unlink()
    source_conn = None
    stage_conn = None
    derive = derive_fn or extract.derive_experience
    try:
        if target.exists():
            source_conn = _connect(target)
            stage_conn = _connect(stage)
            source_conn.backup(stage_conn)
            source_conn.close()
            source_conn = None
        else:
            stage_conn = _connect(stage)
        _experience.ensure_schema(stage_conn)
        tasks = _tasks(stage_conn)
        old_ids = {str(row[0]) for row in stage_conn.execute(
            "SELECT experience_id FROM experiences")}
        if rebuild:
            _drop_experience_docs(stage_conn)
            stage_conn.execute("DELETE FROM experiences")
            stage_conn.commit()
        _emit(progress_fn, {"phase": "scan", "current": 0, "total": len(tasks)})
        generated = []
        for current, (session_id, task_id) in enumerate(tasks, start=1):
            eid = experience_id_for(session_id, task_id)
            if not rebuild and eid in old_ids:
                generated.append(eid)
            else:
                derive(stage_conn, session_id, task_id, eid)
                generated.append(eid)
            _emit(progress_fn, {"phase": "derive", "current": current,
                                "total": len(tasks), "experience_id": eid})
        current_ids = {str(row[0]) for row in stage_conn.execute(
            "SELECT experience_id FROM experiences")}
        orphan_ids = sorted(old_ids - set(generated)) if rebuild else []
        vector_status = "skipped"
        failed_embeddings = []
        if embed_fn and current_ids:
            _drop_experience_docs(stage_conn)
            records = [
                _experience.experience(stage_conn, eid)
                for eid in sorted(current_ids)
            ]
            vectors = []
            dimension = None
            for record in records:
                body = " ".join((record["situation"], record["goal"], record["approach"],
                                  record["action"], record["lesson"], record["applicability"]))
                try:
                    vector = embed_fn(body)
                except Exception:
                    vector = None
                if vector is None or (dimension is not None and len(vector) != dimension):
                    failed_embeddings.append(record["experience_id"])
                elif dimension is None:
                    dimension = len(vector)
                vectors.append(vector)
            if failed_embeddings:
                return {"status": "failed", "reason": "embedding failure",
                        "failed_embeddings": failed_embeddings}
            _experience.ensure_recall_schema(stage_conn, dim=dimension, embed_id=embed_id)
            for record, vector in zip(records, vectors):
                _experience.index_experience(stage_conn, record["experience_id"], vector=vector)
            vector_status = "ok"
        stage_conn.commit()
        stage_conn.close()
        stage_conn = None
        os.replace(stage, target)
        result = {"status": "ok", "experiences": len(current_ids),
                  "derived_experiences": len(generated),
                  "orphan_experiences": orphan_ids,
                  "vector_status": vector_status, "failed_embeddings": []}
        _emit(progress_fn, {"phase": "complete", **result})
        return result
    except Exception as exc:
        return {"status": "failed", "reason": str(exc),
                "failed_embeddings": [], "orphan_experiences": []}
    finally:
        if source_conn is not None:
            source_conn.close()
        if stage_conn is not None:
            stage_conn.close()
        if stage.exists():
            stage.unlink()


def _emit(progress_fn, event):
    if progress_fn is None:
        return
    try:
        progress_fn(dict(event))
    except Exception:
        pass

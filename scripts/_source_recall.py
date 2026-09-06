#!/usr/bin/env python3
"""Lexical source evidence search plus deterministic SourceRef hydration.

The SQLite database is a disposable FTS projection. Raw files and structured
SourceRefs remain authoritative; cached passages are never returned after the
underlying source becomes stale, missing, unreadable, or redacted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _source_ref import (
    APPROVED_ROOTS,
    OFFSET_UNIT,
    SCHEMA_VERSION,
    resolve_source_ref,
    source_ref_id,
)

TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".json", ".jsonl", ".csv", ".rst"}
INDEX_VERSION = "source-fts-v1"
_QUERY_STOPWORDS = {
    "aan", "als", "and", "bij", "de", "did", "die", "een", "en", "for",
    "from", "het", "hoe", "ik", "in", "is", "met", "of", "on", "the",
    "to", "van", "voor", "was", "wat", "what", "where", "which", "who",
    "why", "with", "zou",
}


def hydrate_source_ref(vault: Path, ref: dict) -> dict:
    """Resolve one exact reference without search, ranking, or model access."""
    return resolve_source_ref(vault, ref)


def connect(path=None) -> sqlite3.Connection:
    target = Path(path) if path is not None else Path.cwd() / "kb-source.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    # The source projection is disposable and atomically replaced by the
    # builder. DELETE mode keeps it in one self-contained file.
    conn.execute("PRAGMA journal_mode=DELETE")
    return conn


def ensure_schema(conn, *_unused, **_unused_named) -> None:
    """Create the vector-free source manifest, chunk store, and FTS index."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS source_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS source_manifest (
        source_path TEXT PRIMARY KEY,
        source_hash TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS source_chunks (
        chunk_rowid INTEGER PRIMARY KEY AUTOINCREMENT,
        source_path TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        start INTEGER NOT NULL,
        end INTEGER NOT NULL,
        passage TEXT NOT NULL,
        passage_hash TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(source_path, chunk_index)
    );
    CREATE INDEX IF NOT EXISTS idx_source_chunks_hash
        ON source_chunks(source_hash);
    CREATE INDEX IF NOT EXISTS idx_source_chunks_path
        ON source_chunks(source_path);
    CREATE VIRTUAL TABLE IF NOT EXISTS source_fts USING fts5(
        passage,
        content='source_chunks',
        content_rowid='chunk_rowid',
        tokenize='unicode61'
    );
    CREATE TRIGGER IF NOT EXISTS source_chunks_ai AFTER INSERT ON source_chunks BEGIN
        INSERT INTO source_fts(rowid, passage) VALUES (new.chunk_rowid, new.passage);
    END;
    CREATE TRIGGER IF NOT EXISTS source_chunks_ad AFTER DELETE ON source_chunks BEGIN
        INSERT INTO source_fts(source_fts, rowid, passage)
        VALUES ('delete', old.chunk_rowid, old.passage);
    END;
    CREATE TRIGGER IF NOT EXISTS source_chunks_au AFTER UPDATE ON source_chunks BEGIN
        INSERT INTO source_fts(source_fts, rowid, passage)
        VALUES ('delete', old.chunk_rowid, old.passage);
        INSERT INTO source_fts(rowid, passage) VALUES (new.chunk_rowid, new.passage);
    END;
    """)
    conn.execute(
        "INSERT OR REPLACE INTO source_meta(key, value) VALUES (?, ?)",
        ("index_version", INDEX_VERSION))
    conn.commit()


def chunk_text(text: str, *, size: int = 2000, overlap: int = 200) -> list[dict]:
    """Split text while retaining exact Unicode-codepoint offsets."""
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and smaller than size")
    if not text:
        return []
    step = size - overlap
    chunks = []
    start = 0
    index = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append({"index": index, "start": start, "end": end,
                       "text": text[start:end]})
        if end == len(text):
            break
        start += step
        index += 1
    return chunks


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _delete_source_rows(conn, source_path: str) -> None:
    # External-content FTS triggers remove the lexical rows atomically.
    conn.execute("DELETE FROM source_chunks WHERE source_path=?", (source_path,))


def upsert_source(conn, *, source_path: str, source_hash: str,
                  chunks: list[dict], metadata: dict | None = None,
                  commit: bool = True) -> None:
    """Replace all lexical chunks for one source in one transaction."""
    metadata_json = json.dumps(dict(metadata or {}), ensure_ascii=False,
                               sort_keys=True)
    if commit:
        conn.execute("BEGIN")
    try:
        _delete_source_rows(conn, source_path)
        for chunk in chunks:
            passage = str(chunk["text"])
            start, end = int(chunk["start"]), int(chunk["end"])
            if start < 0 or end <= start or end - start != len(passage):
                raise ValueError(
                    f"invalid exact offsets for {source_path} chunk {chunk['index']}")
            conn.execute(
                "INSERT INTO source_chunks(source_path, source_hash, chunk_index, "
                "start, end, passage, passage_hash, metadata_json) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (source_path, source_hash, int(chunk["index"]), start, end,
                 passage, _sha256_text(passage), metadata_json))
        conn.execute(
            "INSERT OR REPLACE INTO source_manifest(source_path, source_hash) "
            "VALUES (?, ?)", (source_path, source_hash))
        if commit:
            conn.commit()
    except Exception:
        if commit:
            conn.rollback()
        raise


def _fts_expression(query_text: str) -> str:
    tokens = []
    seen = set()
    for token in re.findall(r"[^\W_]+", str(query_text or ""), re.UNICODE):
        normalized = token.casefold()
        if (len(normalized) < 2 or normalized in seen
                or normalized in _QUERY_STOPWORDS):
            continue
        seen.add(normalized)
        tokens.append(normalized)
        if len(tokens) >= 32:
            break
    # Conjunction keeps BM25 bounded on a large corpus and avoids letting one
    # generic question word dominate evidence recall. This route is explicitly
    # best-effort; callers can issue a narrower follow-up when it returns no hit.
    return " AND ".join(f'"{token}"' for token in tokens)


def _stored_ref(row: tuple) -> dict:
    ref = {
        "schema_version": SCHEMA_VERSION,
        "source_path": str(row[1]),
        "source_sha256": str(row[2]),
        "chunk_id": f"chunk-{int(row[3])}",
        "start": int(row[4]),
        "end": int(row[5]),
        "offset_unit": OFFSET_UNIT,
        "passage_sha256": str(row[6]),
        "captured_at": "",
        "redaction_state": "clear",
    }
    ref["source_ref_id"] = source_ref_id(ref)
    return ref


def source_hits(conn, *, query_text: str = "", k: int = 8,
                source_path: str | None = None,
                source_root: str | Path | None = None) -> list[dict]:
    """Return BM25-ranked evidence with exact, freshly resolved provenance."""
    expression = _fts_expression(query_text)
    if not expression or k <= 0:
        return []
    parameters: list[object] = [expression]
    where = "source_fts MATCH ?"
    if source_path:
        where += " AND c.source_path=?"
        parameters.append(str(source_path))
    parameters.append(max(1, min(int(k), 100)))
    rows = conn.execute(
        "SELECT c.chunk_rowid, c.source_path, c.source_hash, c.chunk_index, "
        "c.start, c.end, c.passage_hash, c.metadata_json, "
        "source_fts.rank FROM source_fts "
        "JOIN source_chunks c ON c.chunk_rowid=source_fts.rowid "
        f"WHERE {where} ORDER BY source_fts.rank LIMIT ?",
        tuple(parameters)).fetchall()
    root = Path(source_root) if source_root is not None else None
    hits = []
    for row in rows:
        ref = _stored_ref(row)
        if root is None:
            resolved = {"status": "unverified", "fresh": False,
                        "source_ref_id": ref["source_ref_id"]}
        else:
            resolved = hydrate_source_ref(root, ref)
        resolver_status = str(resolved.get("status") or "invalid")
        source_state = "current" if resolver_status == "valid" else resolver_status
        metadata = json.loads(row[7] or "{}")
        hit = {
            "source_path": row[1], "source_hash": row[2],
            "source_sha256": row[2], "chunk_index": int(row[3]),
            "start": int(row[4]), "end": int(row[5]),
            "offset_unit": OFFSET_UNIT, "passage_sha256": row[6],
            "passage": resolved.get("passage", ""),
            "fresh": bool(resolved.get("fresh")),
            "stale": resolver_status == "stale", "source_state": source_state,
            "score": float(row[8]), "fts": True, "layer": "source",
            "retrieval_route": "lexical_fts", "best_effort": True,
            "source_ref": ref, "source_ref_id": ref["source_ref_id"],
        }
        hit.update({key: value for key, value in metadata.items() if key not in hit})
        hits.append(hit)
    return hits


def should_route(mode: str, primary_hits=None, floor: float = 0.5) -> bool:
    """Only explicit product routes are eligible; automatic fallback is not."""
    del primary_hits, floor
    return str(mode or "normal").lower() in {"explicit", "verify", "reconstruct"}

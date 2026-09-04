#!/usr/bin/env python3
"""Provenance-first retrieval over immutable local source files.

The source database is a disposable projection.  A source path and SHA-256
hash remain the authority; vectors and FTS rows are only an accelerator and a
passage locator.  This module deliberately does not route normal retrieval.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kbindex  # noqa: E402
from _source_ref import APPROVED_ROOTS, resolve_source_ref  # noqa: E402

TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".json", ".jsonl", ".csv", ".rst"}


def hydrate_source_ref(vault: Path, ref: dict) -> dict:
    """Use the canonical exact resolver; this path never performs retrieval."""
    return resolve_source_ref(vault, ref)


def connect(path=None):
    return _kbindex.connect(path)


def ensure_schema(conn, dim: int, embed_id: str) -> None:
    _kbindex.ensure_schema(conn, dim, embed_id)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS source_chunks ("
        "source_path TEXT NOT NULL, source_hash TEXT NOT NULL, "
        "chunk_index INTEGER NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL, "
        "passage TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}', "
        "PRIMARY KEY (source_path, chunk_index))")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_source_chunks_hash "
        "ON source_chunks(source_hash)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_source_chunks_path "
        "ON source_chunks(source_path)")
    # The manifest is part of the source-index contract, not an implementation
    # detail of one builder. It lets doctor and incremental rebuilds distinguish
    # a deleted source from a stale or partially built projection.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS source_manifest ("
        "source_path TEXT PRIMARY KEY, source_hash TEXT NOT NULL)")
    conn.commit()


def chunk_text(text: str, *, size: int = 2000, overlap: int = 200) -> list[dict]:
    """Split text while retaining exact character offsets."""
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


def _doc_path(source_path: str, index: int) -> str:
    return f"source::{source_path}#chunk={int(index)}"


def _delete_source_rows(conn, source_path: str) -> None:
    rows = conn.execute(
        "SELECT doc_id, path FROM docs WHERE path LIKE ?",
        (f"source::{source_path}#chunk=%",)).fetchall()
    for doc_id, _path in rows:
        conn.execute("DELETE FROM docs WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM fts_docs WHERE rowid=?", (doc_id,))
        conn.execute("DELETE FROM vec_docs WHERE doc_id=?", (doc_id,))
        try:
            conn.execute("DELETE FROM doc_sources WHERE doc_id=?", (doc_id,))
        except Exception:
            pass
    conn.execute("DELETE FROM source_chunks WHERE source_path=?", (source_path,))


def upsert_source(conn, *, source_path: str, source_hash: str,
                  chunks: list[dict], vectors: list, metadata: dict | None = None) -> None:
    """Replace every chunk for one source in one transaction."""
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors must have equal length")
    metadata = dict(metadata or {})
    conn.execute("BEGIN")
    try:
        _delete_source_rows(conn, source_path)
        for chunk, vector in zip(chunks, vectors):
            if vector is None:
                raise ValueError(f"missing embedding for {source_path} chunk {chunk['index']}")
            path = _doc_path(source_path, chunk["index"])
            row = conn.execute("SELECT doc_id FROM docs WHERE path=?", (path,)).fetchone()
            if row:
                doc_id = row[0]
                conn.execute(
                    "UPDATE docs SET layer=?, status=?, hash=?, title=?, created=? WHERE doc_id=?",
                    ("source", "current", source_hash, source_path, "", doc_id))
                conn.execute("DELETE FROM fts_docs WHERE rowid=?", (doc_id,))
                conn.execute("DELETE FROM vec_docs WHERE doc_id=?", (doc_id,))
                conn.execute("DELETE FROM doc_sources WHERE doc_id=?", (doc_id,))
            else:
                doc_id = conn.execute(
                    "INSERT INTO docs(path, layer, status, hash, title, created) "
                    "VALUES (?,?,?,?,?,?)",
                    (path, "source", "current", source_hash, source_path, ""),
                ).lastrowid
            conn.execute("INSERT INTO fts_docs(rowid, body) VALUES (?, ?)",
                         (doc_id, chunk["text"]))
            conn.execute("INSERT INTO vec_docs(doc_id, embedding) VALUES (?, ?)",
                         (doc_id, _kbindex._serialize(_kbindex.unit(vector))))
            conn.execute("INSERT INTO doc_sources(doc_id, source) VALUES (?, ?)",
                         (doc_id, source_path))
            conn.execute(
                "INSERT INTO source_chunks(source_path, source_hash, chunk_index, "
                "start, end, passage, metadata_json) VALUES (?,?,?,?,?,?,?)",
                (source_path, source_hash, int(chunk["index"]), int(chunk["start"]),
                 int(chunk["end"]), chunk["text"], json.dumps(metadata, sort_keys=True)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def source_hits(conn, *, query_vector, query_text: str = "", k: int = 8,
                source_path: str | None = None, embed_id: str | None = None,
                source_root: str | Path | None = None, min_cos: float = 0.45) -> list[dict]:
    """Return source passages with exact provenance, optionally freshness-checked."""
    if embed_id and not _kbindex.is_valid_for(conn, embed_id):
        return []
    total = conn.execute("SELECT count(*) FROM docs WHERE layer='source'").fetchone()[0]
    if not total or not query_vector or k <= 0:
        return []
    rows = _kbindex.search(
        conn, query_vector=query_vector, query_text=query_text,
        k=max(k, total), layers=("source",), statuses=("current",), fusion="rrf")
    out = []
    root = Path(source_root) if source_root is not None else None
    for row in rows:
        meta = conn.execute(
            "SELECT source_path, source_hash, chunk_index, start, end, passage, "
            "metadata_json FROM source_chunks WHERE source_path || '#chunk=' || "
            "chunk_index = ?", (row["path"].removeprefix("source::"),)).fetchone()
        if meta is None or (source_path and meta[0] != source_path):
            continue
        if not row["fts"] and float(row.get("cos") or 0.0) < min_cos:
            continue
        source, source_hash, index, start, end, passage, metadata_json = meta
        metadata = json.loads(metadata_json or "{}")
        fresh = True
        if root is not None:
            path = root / Path(source)
            fresh = path.is_file() and sha256_file(path) == source_hash
        item = {"source_path": source, "source_hash": source_hash,
                "chunk_index": int(index), "start": int(start), "end": int(end),
                "passage": passage if fresh else "", "fresh": fresh,
                "stale": not fresh, "score": row["score"], "cos": row["cos"],
                "fts": row["fts"], "doc_id": row["doc_id"], "layer": "source"}
        item.update({key: value for key, value in metadata.items() if key not in item})
        out.append(item)
        if len(out) >= k:
            break
    return out


def should_route(mode: str, primary_hits, floor: float = 0.5) -> bool:
    """Explicit source requests always route; fallback only fills a weak result."""
    mode = (mode or "normal").lower()
    if mode in {"explicit", "verify", "reconstruct"}:
        return True
    if mode != "fallback":
        return False
    return not primary_hits or max(float(hit.get("cos") or 0.0) for hit in primary_hits) < floor

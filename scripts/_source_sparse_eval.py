"""Bounded sparse-first source retrieval for offline evaluation.

The full-corpus FTS database remains read-only. Candidate passages are read
from the authoritative vault files, embedded on demand, and cached by exact
passage hash plus model identity. Queries are deliberately never persisted.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import math
import os
import re
import sqlite3
import struct
import time
from pathlib import Path
from typing import Callable, Iterable

import _kbindex
import _layer_eval

SCHEMA_VERSION = 1
RETRIEVAL_MODE = "sparse_first_vector_rerank"
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_source_snapshot(path: Path) -> dict:
    """Read bytes once and derive both provenance and normalized offset text."""
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8")
    # Match Python's text-mode universal-newline representation used by the
    # reviewed source windows while keeping the authoritative raw-byte hash.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return {
        "text": text,
        "source_hash": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "indexed_body_hash": _hash_text(text),
        "offset_unit": "unicode_codepoint_normalized_newlines",
    }


def _unit(values: Iterable[float]) -> list[float]:
    vector = [float(value) for value in values]
    if not vector or any(not math.isfinite(value) for value in vector):
        raise ValueError("embedding vector must be finite and non-empty")
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0.0:
        raise ValueError("embedding vector must have non-zero norm")
    return [value / norm for value in vector]


def _cosine(left: Iterable[float], right: Iterable[float]) -> float:
    a, b = _unit(left), _unit(right)
    if len(a) != len(b) or not a:
        raise ValueError("embedding dimensions must match and be non-empty")
    return sum(x * y for x, y in zip(a, b))


def _connect_cache(path: Path) -> sqlite3.Connection:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS passage_embeddings ("
        "model_id TEXT NOT NULL, content_hash TEXT NOT NULL, dimension INTEGER NOT NULL, "
        "vector_blob BLOB NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "PRIMARY KEY (model_id, content_hash))")
    columns = {row[1] for row in conn.execute(
        "PRAGMA table_info(passage_embeddings)").fetchall()}
    required = {"model_id", "content_hash", "dimension", "vector_blob", "created_at"}
    if not required.issubset(columns):
        conn.close()
        raise ValueError("incompatible sparse source cache schema")
    conn.commit()
    return conn


def _embed_passages(cache_db: Path, *, passages: list[str], model_id: str,
                    embed_fn: Callable[[list[str]], list[list[float]]]) -> list[list[float]]:
    """Return vectors in input order, filling only content-addressed misses."""
    hashes = [_hash_text(passage) for passage in passages]
    conn = _connect_cache(cache_db)
    try:
        cached: dict[str, list[float]] = {}
        for content_hash in dict.fromkeys(hashes):
            row = conn.execute(
                "SELECT dimension, vector_blob FROM passage_embeddings "
                "WHERE model_id=? AND content_hash=?",
                (model_id, content_hash),
            ).fetchone()
            if row is not None:
                dimension, blob = int(row[0]), bytes(row[1])
                if dimension <= 0 or len(blob) != dimension * 4:
                    raise ValueError("corrupt sparse source cache vector")
                cached[content_hash] = list(struct.unpack(f"<{dimension}f", blob))

        missing_hashes = [value for value in dict.fromkeys(hashes) if value not in cached]
        if missing_hashes:
            text_by_hash = {content_hash: passage for content_hash, passage
                            in zip(hashes, passages)}
            missing_text = [text_by_hash[value] for value in missing_hashes]
            vectors = embed_fn(missing_text)
            if len(vectors) != len(missing_text):
                raise RuntimeError("embedding backend returned an unexpected vector count")
            normalized_vectors = [_unit(vector) for vector in vectors]
            dimensions = {len(vector) for vector in normalized_vectors}
            if len(dimensions) != 1:
                raise ValueError("embedding backend returned mixed dimensions")
            conn.execute("BEGIN")
            try:
                for content_hash, normalized in zip(
                        missing_hashes, normalized_vectors):
                    blob = struct.pack(f"<{len(normalized)}f", *normalized)
                    conn.execute(
                        "INSERT OR IGNORE INTO passage_embeddings("
                        "model_id, content_hash, dimension, vector_blob) VALUES (?,?,?,?)",
                        (model_id, content_hash, len(normalized), blob),
                    )
                    cached[content_hash] = normalized
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return [cached[value] for value in hashes]
    finally:
        conn.close()


def _lexical_docs(source_db: Path, query: str, *, limit: int) -> list[dict]:
    if limit <= 0:
        return []
    expression = _kbindex.fts_expr(query)
    if not expression:
        return []
    uri = Path(source_db).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        try:
            rows = []
            matches = conn.execute(
                "SELECT source_path, body, rank FROM source_fts "
                "WHERE source_fts MATCH ? ORDER BY rank LIMIT ?",
                (expression, int(limit)))
            for lexical_rank, (source_path, body, bm25) in enumerate(matches):
                rows.append({
                    "source_path": str(source_path),
                    "indexed_body_hash": _hash_text(str(body)),
                    "lexical_rank": lexical_rank,
                    "bm25": float(bm25),
                })
            return rows
        except sqlite3.OperationalError:
            return []
    finally:
        conn.close()


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in _TOKEN.findall(text or "")
            if len(token) >= 3}


def _iter_chunks(text: str, *, size: int, overlap: int):
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("invalid sparse source chunk configuration")
    step = size - overlap
    start = index = 0
    while start < len(text):
        end = min(len(text), start + size)
        yield {"index": index, "start": start, "end": end,
               "text": text[start:end]}
        if end == len(text):
            break
        start += step
        index += 1


def _passage_candidates(query: str, documents: list[dict], *, vault: Path,
                        chunk_size: int, overlap: int,
                        max_passages: int) -> list[dict]:
    terms = _tokens(query)
    limit = max(0, int(max_passages))
    if limit == 0:
        return []
    heap = []
    selected_keys = set()
    serial = 0
    root = Path(vault).resolve()
    for document in documents:
        source_path = document["source_path"]
        path = (root / Path(source_path)).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        try:
            snapshot = read_source_snapshot(path)
        except (OSError, UnicodeError):
            continue
        if snapshot["indexed_body_hash"] != document["indexed_body_hash"]:
            continue

        def consider(chunk, lexical_score):
            nonlocal serial
            key = (source_path, int(chunk["index"]))
            if key in selected_keys:
                return
            passage = chunk["text"]
            item = {
                "source_path": source_path.replace("\\", "/"),
                "source_hash": snapshot["source_hash"],
                "indexed_hash": document["indexed_body_hash"],
                "passage_hash": _hash_text(passage),
                "chunk_index": int(chunk["index"]),
                "start": int(chunk["start"]),
                "end": int(chunk["end"]),
                "offset_unit": snapshot["offset_unit"],
                "passage": passage,
                "document_rank": int(document["lexical_rank"]),
                "lexical_rank": int(document["lexical_rank"]),
                "bm25": float(document["bm25"]),
                "lexical_score": int(lexical_score),
            }
            quality = (int(lexical_score), -int(document["lexical_rank"]),
                       -int(chunk["index"]))
            entry = (quality, serial, key, item)
            serial += 1
            if len(heap) < limit:
                heapq.heappush(heap, entry)
                selected_keys.add(key)
            elif quality > heap[0][0]:
                removed = heapq.heapreplace(heap, entry)
                selected_keys.discard(removed[2])
                selected_keys.add(key)

        previous = None
        include_next = False
        for chunk in _iter_chunks(
                snapshot["text"], size=chunk_size, overlap=overlap):
            lowered = chunk["text"].casefold()
            lexical_score = sum(lowered.count(term) for term in terms)
            if lexical_score > 0 or not terms:
                if previous is not None:
                    consider(previous, 0)
                consider(chunk, lexical_score)
                include_next = True
            elif include_next:
                consider(chunk, 0)
                include_next = False
            previous = chunk
    return [entry[3] for entry in sorted(
        heap, key=lambda entry: entry[0], reverse=True)]


def retrieve(*, query: str, vault: Path, source_db: Path, cache_db: Path,
             embed_fn: Callable[[list[str]], list[list[float]]], model_id: str,
             embed_query_fn: Callable[[list[str]], list[list[float]]] | None = None,
             document_model_id: str | None = None,
             query_model_id: str | None = None,
             candidate_docs: int = 50, max_passages: int = 100,
             chunk_size: int = 2000, overlap: int = 200, k: int = 5,
             min_cos: float = 0.50) -> list[dict]:
    """Retrieve bounded passages while preserving exact source provenance."""
    if not str(query or "").strip() or k <= 0:
        return []
    documents = _lexical_docs(source_db, query, limit=candidate_docs)
    passages = _passage_candidates(
        query, documents, vault=Path(vault), chunk_size=chunk_size,
        overlap=overlap, max_passages=max_passages)
    if not passages:
        return []
    document_model_id = str(document_model_id or model_id)
    query_model_id = str(query_model_id or model_id)
    query_rows = (embed_query_fn or embed_fn)([query])
    if len(query_rows) != 1:
        raise RuntimeError("embedding backend did not return one query vector")
    query_vector = query_rows[0]
    vectors = _embed_passages(
        Path(cache_db), passages=[item["passage"] for item in passages],
        model_id=document_model_id, embed_fn=embed_fn)
    ranked = []
    for item, vector in zip(passages, vectors):
        cosine = _cosine(query_vector, vector)
        if cosine < float(min_cos):
            continue
        hit = dict(item)
        hit.update({
            "cos": cosine,
            "model_id": document_model_id,
            "document_model_id": document_model_id,
            "query_model_id": query_model_id,
            "retrieval_mode": RETRIEVAL_MODE,
            "layer": "source",
            "fresh": True,
            "stale": False,
        })
        ranked.append(hit)
    ranked.sort(key=lambda item: (
        -item["cos"], item["document_rank"], -item["lexical_score"],
        item["source_path"], item["start"]))
    return ranked[:int(k)]


def _overlaps(hit: dict, windows: list[dict]) -> bool:
    start, end = int(hit.get("start") or 0), int(hit.get("end") or 0)
    return any(start < int(window["end"]) and end > int(window["start"])
               for window in windows)


def evaluate(cases: list[dict], **retrieve_options) -> dict:
    """Return aggregates only; reviewed queries and source windows stay private."""
    rows = []
    positive = negative = passage_hits = correct_citations = cited = 0
    negative_abstentions = provenance_valid = provenance_total = 0
    latencies = []
    k = int(retrieve_options.get("k", 5))
    for case in cases:
        started = time.perf_counter()
        hits = retrieve(query=str(case.get("query") or ""), **retrieve_options)
        latencies.append((time.perf_counter() - started) * 1000.0)
        expected = case.get("expected_source")
        rows.append({"expected": expected,
                     "hits": [hit["source_path"] for hit in hits]})
        for hit in hits:
            provenance_total += 1
            try:
                snapshot = read_source_snapshot(
                    Path(retrieve_options["vault"]) / hit["source_path"])
                valid = (
                    hit["source_hash"] == snapshot["source_hash"]
                    and hit["offset_unit"] == snapshot["offset_unit"]
                    and hit["passage"] == snapshot["text"][
                        int(hit["start"]):int(hit["end"])]
                    and hit["passage_hash"] == _hash_text(hit["passage"]))
            except (OSError, UnicodeError, KeyError, ValueError):
                valid = False
            provenance_valid += int(valid)
        if expected is None:
            negative += 1
            negative_abstentions += int(not hits)
            continue
        positive += 1
        windows = list(case.get("expected_windows") or [])
        matching = [hit for hit in hits[:k]
                    if hit["source_path"] == expected]
        if matching and any(_overlaps(hit, windows) for hit in matching):
            passage_hits += 1
        if hits:
            cited += 1
            if hits[0]["source_path"] == expected and _overlaps(hits[0], windows):
                correct_citations += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "counts": {"total": len(cases), "positive": positive, "negative": negative},
        "retrieval": _layer_eval.retrieval_metrics(rows, cutoffs=(1, 5)),
        "passage_hit@5": passage_hits / positive if positive else 0.0,
        "citation_precision": correct_citations / cited if cited else 0.0,
        "provenance_precision": (
            provenance_valid / provenance_total if provenance_total else 1.0),
        "no_hit_specificity": (
            negative_abstentions / negative if negative else 0.0),
        "latency_ms": _layer_eval.latency_summary(latencies),
        "configuration": {
            "model_id": str(retrieve_options.get("model_id") or ""),
            "candidate_docs": int(retrieve_options.get("candidate_docs", 50)),
            "max_passages": int(retrieve_options.get("max_passages", 100)),
            "chunk_size": int(retrieve_options.get("chunk_size", 2000)),
            "overlap": int(retrieve_options.get("overlap", 200)),
            "min_cos": float(retrieve_options.get("min_cos", 0.50)),
        },
    }


def write_once_report(path: Path, builder: Callable[[], dict]) -> dict:
    """Claim the result path before work and atomically replace its marker."""
    target = Path(path)
    if target.exists():
        raise FileExistsError(f"report already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            json.dump({"schema_version": SCHEMA_VERSION, "status": "running"}, handle)
            handle.write("\n")
    except FileExistsError:
        raise
    try:
        report = dict(builder())
        report.setdefault("schema_version", SCHEMA_VERSION)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        os.replace(temporary, target)
        return report
    except Exception:
        # Keep the marker as evidence that the one-shot attempt was spent.
        raise

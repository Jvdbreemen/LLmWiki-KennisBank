"""Disposable full-document FTS baseline for reviewed source holdouts."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import _kbindex
import _layer_eval
from _source_recall import APPROVED_ROOTS, TEXT_EXTENSIONS


def _paths(vault: Path):
    for root in APPROVED_ROOTS:
        directory = vault / root
        if directory.is_dir():
            yield from (path for path in directory.rglob("*")
                        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS)


def _redacted(path: Path, text: str) -> bool:
    name = path.name.lower()
    if ".redacted." in name or name.endswith(".redacted"):
        return True
    head = text[:4000].lower()
    return "redacted:" in head and any(
        marker in head for marker in ("redacted: true", "redacted: yes", "redacted: 1"))


def build_index(vault: Path, db_path: Path) -> dict:
    """Atomically index approved UTF-8 source documents without embeddings."""
    started = time.perf_counter()
    vault, target = Path(vault), Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_name(target.name + ".staging")
    stage.unlink(missing_ok=True)
    conn = sqlite3.connect(stage)
    documents = unreadable = redacted = 0
    bytes_indexed = 0
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("CREATE VIRTUAL TABLE source_fts USING fts5(source_path UNINDEXED, body)")
        for path in sorted(set(_paths(vault)), key=lambda item: item.as_posix()):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                unreadable += 1
                continue
            if _redacted(path, text):
                redacted += 1
                continue
            conn.execute("INSERT INTO source_fts(source_path, body) VALUES (?, ?)",
                         (path.relative_to(vault).as_posix(), text))
            documents += 1
            bytes_indexed += path.stat().st_size
        conn.execute("INSERT INTO source_fts(source_fts) VALUES ('optimize')")
        conn.commit()
    finally:
        conn.close()
    os.replace(stage, target)
    return {"documents": documents, "unreadable": unreadable,
            "redacted": redacted, "bytes_indexed": bytes_indexed,
            "build_seconds": round(time.perf_counter() - started, 3),
            "index_bytes": target.stat().st_size}


def evaluate(cases, db_path: Path, *, k: int = 5) -> dict:
    """Measure source-path retrieval and no-hit behavior, returning aggregates."""
    rows = []
    latencies = []
    conn = sqlite3.connect(db_path)
    try:
        for case in cases:
            started = time.perf_counter()
            expr = _kbindex.fts_expr(case.get("query") or "")
            hits = []
            if expr:
                try:
                    hits = [row[0] for row in conn.execute(
                        "SELECT source_path FROM source_fts WHERE source_fts MATCH ? "
                        "ORDER BY rank LIMIT ?", (expr, k)).fetchall()]
                except sqlite3.OperationalError:
                    hits = []
            latencies.append((time.perf_counter() - started) * 1000.0)
            rows.append({"expected": case.get("expected_source"), "hits": hits})
    finally:
        conn.close()
    return {"retrieval": _layer_eval.retrieval_metrics(rows, cutoffs=(1, 5)),
            "latency_ms": _layer_eval.latency_summary(latencies)}

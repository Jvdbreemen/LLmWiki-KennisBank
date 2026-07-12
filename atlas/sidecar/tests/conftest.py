"""Shared fixtures: build a hermetic KennisBank vault in a tmp dir.

Every store is synthesised small and deterministic so endpoint tests assert
exact counts and ordering without touching the maintainer's real vault.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest


def _write_graph(vault: Path, nodes: list[dict], links: list[dict]) -> None:
    out = vault / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "graph.json").write_text(
        json.dumps({"directed": True, "nodes": nodes, "links": links}),
        encoding="utf-8",
    )


def _write_kbindex(vault: Path, docs: list[dict]) -> None:
    db = vault / ".claude"
    db.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db / "kb-index.db")
    conn.execute(
        "CREATE TABLE docs (doc_id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "path TEXT UNIQUE, layer TEXT, status TEXT, hash TEXT, title TEXT, created TEXT)"
    )
    conn.executemany(
        "INSERT INTO docs (path, layer, status, hash, title, created) "
        "VALUES (:path, :layer, :status, :hash, :title, :created)",
        [{"hash": "h", "created": "2026-01-01", **d} for d in docs],
    )
    conn.commit()
    conn.close()


def _write_activity(vault: Path, events: list[dict]) -> None:
    db = vault / ".claude"
    db.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db / "kb-activity.db")
    conn.execute(
        "CREATE TABLE activity_events (id TEXT PRIMARY KEY, source_kind TEXT, "
        "source_path TEXT, event_time TEXT, captured_at TEXT, activity_kind TEXT, "
        "title TEXT)"
    )
    conn.executemany(
        "INSERT INTO activity_events (id, source_kind, source_path, event_time, "
        "captured_at, activity_kind, title) VALUES "
        "(:id, :source_kind, :source_path, :event_time, :captured_at, "
        ":activity_kind, :title)",
        [{"source_kind": "session", "source_path": "", "title": "", **e}
         for e in events],
    )
    conn.commit()
    conn.close()


@pytest.fixture
def vault_factory(tmp_path: Path):
    """Return a builder that materialises a vault and yields its root path."""

    def build(*, nodes=None, links=None, docs=None, events=None) -> Path:
        vault = tmp_path
        if nodes is not None or links is not None:
            _write_graph(vault, nodes or [], links or [])
        if docs is not None:
            _write_kbindex(vault, docs)
        if events is not None:
            _write_activity(vault, events)
        return vault

    return build

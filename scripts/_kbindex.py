#!/usr/bin/env python3
"""_kbindex.py - lokale hybride zoekindex (sqlite-vec vec0 + FTS5).

Afgeleide, herbouwbare index over de vault-markdown. Markdown blijft bron van
waarheid; deze .db is een wegwerp-cache (rm + rebuild). Brute-force vec0 KNN +
FTS5 keyword. Dimensie komt van het live embedmodel (nooit gehardcode); embed_id
wordt opgeslagen zodat een modelwissel de index ongeldig maakt.

Pure functies: vectoren komen als argument binnen (geen embed-call hier), zodat
de module testbaar is zonder embedmodel. sqlite-vec is een pip-dep (gepind).

Stdlib + sqlite-vec.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402


def index_path() -> Path:
    return vault_root() / ".claude" / "kb-index.db"


def connect(path=None) -> sqlite3.Connection:
    import sqlite_vec
    p = str(path) if path is not None else str(index_path())
    if path is None:
        index_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection, dim: int, embed_id: str) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS docs ("
        "doc_id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, "
        "layer TEXT, status TEXT, hash TEXT, title TEXT, created TEXT)")
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_docs USING vec0("
        f"doc_id INTEGER PRIMARY KEY, embedding float[{int(dim)}])")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_docs USING fts5(body)")
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('dim', ?)", (str(int(dim)),))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('embed_id', ?)", (embed_id,))
    conn.commit()


def meta_get(conn: sqlite3.Connection, key: str) -> "str | None":
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def is_valid_for(conn: sqlite3.Connection, embed_id: str) -> bool:
    return meta_get(conn, "embed_id") == embed_id


def _serialize(vector):
    from sqlite_vec import serialize_float32
    return serialize_float32(list(vector))


def indexed_hash(conn: sqlite3.Connection, path: str):
    row = conn.execute("SELECT hash FROM docs WHERE path=?", (path,)).fetchone()
    return row[0] if row else None


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT count(*) FROM docs").fetchone()[0]


def upsert(conn: sqlite3.Connection, *, path: str, layer: str, status: str,
           body: str, vector, file_hash: str, title: str = "",
           created: str = "") -> int:
    """Insert/replace een doc over docs+fts_docs+vec_docs onder één doc_id."""
    row = conn.execute("SELECT doc_id FROM docs WHERE path=?", (path,)).fetchone()
    if row:
        doc_id = row[0]
        conn.execute(
            "UPDATE docs SET layer=?, status=?, hash=?, title=?, created=? WHERE doc_id=?",
            (layer, status, file_hash, title, created, doc_id))
        conn.execute("DELETE FROM fts_docs WHERE rowid=?", (doc_id,))
        conn.execute("DELETE FROM vec_docs WHERE doc_id=?", (doc_id,))
    else:
        cur = conn.execute(
            "INSERT INTO docs(path, layer, status, hash, title, created) "
            "VALUES (?,?,?,?,?,?)", (path, layer, status, file_hash, title, created))
        doc_id = cur.lastrowid
    conn.execute("INSERT INTO fts_docs(rowid, body) VALUES (?, ?)", (doc_id, body))
    conn.execute("INSERT INTO vec_docs(doc_id, embedding) VALUES (?, ?)",
                 (doc_id, _serialize(vector)))
    conn.commit()
    return doc_id


def prune(conn: sqlite3.Connection, keep_paths: set) -> int:
    rows = conn.execute("SELECT doc_id, path FROM docs").fetchall()
    gone = [(d, p) for (d, p) in rows if p not in keep_paths]
    for doc_id, _ in gone:
        conn.execute("DELETE FROM docs WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM fts_docs WHERE rowid=?", (doc_id,))
        conn.execute("DELETE FROM vec_docs WHERE doc_id=?", (doc_id,))
    conn.commit()
    return len(gone)

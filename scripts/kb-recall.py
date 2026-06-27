#!/usr/bin/env python3
"""kb-recall.py - geheugen-recall over kb-index.db (lokaal, fail-soft).

Herbruikbare lib voor de UserPromptSubmit-hook (en later een lokale MCP-server).
Neemt een al-berekende query-vector (de hook embedt de prompt 1×) en geeft de
beste memory(current)-hits terug. Opent de index READ-ONLY (de sweep is een
concurrent writer). Fail-soft: ontbrekende index, model-mismatch of welke fout
dan ook -> lege lijst. Nooit een exceptie naar de hook.

Cross-model-veiligheid: alleen resultaten als de opgeslagen embed_id van de index
gelijk is aan het actieve embedmodel (idem aan de JSON-cache-gate).

Stdlib + sqlite-vec. Hyphen in de naam: importeer via importlib of draai als CLI.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _kbindex  # noqa: E402
import _memory as _mem  # noqa: E402  # live-status hervalidatie (IMPORTANT 1)


def _open_ro(db_path: Path):
    if not db_path.exists():
        return None
    conn = None
    try:
        import sqlite_vec
        uri = f"file:{db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return conn
    except Exception:
        if conn is not None:
            conn.close()
        return None


def memory_hits(query_vector, query_text: str = "", k: int = 3) -> list:
    if not query_vector:
        return []
    db = _kbindex.index_path()
    conn = _open_ro(db)
    if conn is None:
        return []
    try:
        if not _kbindex.is_valid_for(conn, emb.embed_id()):
            return []
        rows = _kbindex.search(conn, query_vector=query_vector, query_text=query_text,
                               k=k, layers=("memory",), statuses=("current",))
        out = []
        for r in rows:
            # Defense-in-depth: hervalideer de live-status van het bestand.
            # Een stale index (build overgeslagen) kan een ingetrokken/vervangen
            # geheugen nog als 'current' serveren. Gooi die treffers weg.
            if _mem.read_status(Path(r["path"])) != "current":
                continue
            snippet = emb.doc_text(Path(r["path"]), cap=280).replace("\n", " ").strip()
            out.append({"path": r["path"], "title": r.get("title", ""),
                        "created": r.get("created", ""), "score": r.get("score", 0.0),
                        "snippet": snippet})
        return out
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass

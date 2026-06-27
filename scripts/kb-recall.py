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


def recall_hits(query_vector, query_text: str = "", k: int = 3,
                layers=("wiki", "memory")) -> list:
    """Recall-hits over de opgegeven lagen (status=current), fail-soft -> [].
    Live-status-hercheck ALLEEN voor de memory-laag (wiki is gecureerd)."""
    if not query_vector:
        return []
    conn = _open_ro(_kbindex.index_path())
    if conn is None:
        return []
    try:
        if not _kbindex.is_valid_for(conn, emb.embed_id()):
            return []
        rows = _kbindex.search(conn, query_vector=query_vector, query_text=query_text,
                               k=k, layers=tuple(layers), statuses=("current",))
        out = []
        for r in rows:
            layer = r.get("layer", "")
            # Stale-index-bescherming alleen voor memory: een ingetrokken memory mag
            # nooit als current geserveerd worden. Wiki vertrouwt de index-status.
            if layer == "memory" and _mem.read_status(Path(r["path"])) != "current":
                continue
            snippet = emb.doc_text(Path(r["path"]), cap=280).replace("\n", " ").strip()
            out.append({"path": r["path"], "layer": layer, "title": r.get("title", ""),
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


def memory_hits(query_vector, query_text: str = "", k: int = 3) -> list:
    """Dunne wrapper: alleen de memory-laag (backward-compat)."""
    return recall_hits(query_vector, query_text=query_text, k=k, layers=("memory",))

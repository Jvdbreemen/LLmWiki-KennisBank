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
import re as _re
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _kbindex  # noqa: E402
import _memory as _mem  # noqa: E402  # live-status hervalidatie (IMPORTANT 1)
import _rank  # noqa: E402  # relevance x recency x importance + graafbuur
from _frontmatter import parse_frontmatter as _parse_fm  # noqa: E402
from _vaultpath import vault_root as _vault_root  # noqa: E402


def _frontmatter_of(path: str) -> dict:
    """Frontmatter-reader voor de re-ranking; fail-soft -> {}."""
    try:
        fm, _ = _parse_fm(Path(path).read_text(encoding="utf-8", errors="replace"))
        return fm
    except Exception:
        return {}


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
                layers=("wiki", "memory"), expand: bool = False) -> list:
    """Recall-hits over de opgegeven lagen (status=current), fail-soft -> [].
    Live-status-hercheck ALLEEN voor de memory-laag (wiki is gecureerd).

    Ranking: de hybride RRF-score wordt voor de memory-laag herwogen met
    recency (halfwaardetijd per memory_type) en importance (judge, 1-5);
    wiki blijft ongewogen (zie _rank).

    ``expand=True`` voegt na de directe hits de meest-verwezen wiki-buur toe
    (wikilink-expansie, één hop) als extra entry met ``neighbor: True`` —
    altijd ACHTERAAN, verdringt nooit een directe hit.
    """
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
        try:
            import _usage
            _lu = _usage.last_used_of
        except Exception:
            _lu = None
        out = _rank.rerank(out, _frontmatter_of, last_used_fn=_lu)
        if expand and out:
            try:
                root = _vault_root()
                stem = _rank.one_hop_neighbor(out, root)
                if stem:
                    p = root / "02-wiki" / f"{stem}.md"
                    snippet = emb.doc_text(p, cap=280).replace("\n", " ").strip()
                    out.append({"path": str(p), "layer": "wiki", "title": stem,
                                "created": "", "score": 0.0, "snippet": snippet,
                                "neighbor": True})
            except Exception:
                pass
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


def has_fts_match(query_text: str, layer: str = "wiki") -> bool:
    """True als een FTS5-keyword-match bestaat in de gegeven laag. Fail-soft.

    Tokeniseert op woorden >= 4 tekens (ge-OR'd) zodat stopwoorden en losse
    leestekens geen vals signaal of FTS5-syntaxfout geven."""
    tokens = [t for t in _re.findall(r"[\w]{4,}", (query_text or "").lower())]
    if not tokens:
        return False
    match_expr = " OR ".join(tokens)
    conn = _open_ro(_kbindex.index_path())
    if conn is None:
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM fts_docs JOIN docs ON docs.doc_id = fts_docs.rowid "
            "WHERE fts_docs MATCH ? AND docs.layer = ? LIMIT 1",
            (match_expr, layer)).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def wiki_hits(query_vector, query_text: str = "", k: int = 3,
              expand: bool = False) -> list:
    """Dunne wrapper: alleen de wiki-laag (hybride, optioneel met graafbuur)."""
    return recall_hits(query_vector, query_text=query_text, k=k,
                       layers=("wiki",), expand=expand)

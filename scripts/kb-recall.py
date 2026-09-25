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

import importlib.util
import os
import re as _re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _kbindex  # noqa: E402
import _memory as _mem  # noqa: E402  # live-status hervalidatie (IMPORTANT 1)
import _rank  # noqa: E402  # relevance x recency x importance + graafbuur
from _common import env_float  # noqa: E402
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


def _open_ro_checked(db_path: Path):
    if not db_path.exists():
        raise _kbindex.IndexUnavailable(
            "missing_index",
            f"indexbestand ontbreekt: {db_path}",
        )
    conn = None
    enabled = False
    try:
        import sqlite_vec
        uri = f"file:{db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        if not hasattr(conn, "enable_load_extension") or not hasattr(conn, "load_extension"):
            raise _kbindex.IndexUnavailable(
                "extension_loading_unsupported",
                "Python sqlite3 heeft geen load_extension/enable_load_extension API",
            )
        conn.enable_load_extension(True)
        enabled = True
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        enabled = False
        return conn
    except _kbindex.IndexUnavailable:
        if conn is not None:
            conn.close()
        raise
    except ImportError as exc:
        if conn is not None:
            conn.close()
        raise _kbindex.IndexUnavailable("sqlite_vec_missing", str(exc)) from exc
    except Exception as exc:
        if conn is not None:
            conn.close()
        message = str(exc)
        low = message.lower()
        if "load_extension" in low or "enable_load_extension" in low:
            code = "extension_loading_unsupported"
        elif "vec0" in low or "no such module" in low:
            code = "vec0_unavailable"
        elif "sqlite_vec" in low or "sqlite-vec" in low:
            code = "sqlite_vec_missing"
        else:
            code = "index_open_failed"
        raise _kbindex.IndexUnavailable(code, message or type(exc).__name__) from exc
    finally:
        if conn is not None and enabled:
            try:
                conn.enable_load_extension(False)
            except Exception:
                pass


def _index_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, _kbindex.IndexUnavailable):
        return exc.code, exc.message
    message = str(exc) or type(exc).__name__
    low = message.lower()
    if "no such module: vec0" in low or "vec0" in low:
        return "vec0_unavailable", message
    if "load_extension" in low or "enable_load_extension" in low:
        return "extension_loading_unsupported", message
    if "sqlite-vec" in low or "sqlite_vec" in low:
        return "sqlite_vec_missing", message
    if isinstance(exc, sqlite3.OperationalError) and "no such table" in low:
        return "schema_error", message
    return "search_error", message


def _load_context_budget():
    spec = importlib.util.spec_from_file_location(
        "context_budget", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "context-budget.py"))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _document_key(hit: dict, index: int) -> str:
    path = str(hit.get("path", ""))
    if not path:
        return f"__hit-{index}"
    try:
        return Path(path).resolve().as_posix()
    except OSError:
        return Path(path).as_posix()


def _fit_hits(hits: list, max_tokens) -> tuple[list, dict | None]:
    try:
        budget = int(max_tokens)
    except (TypeError, ValueError):
        return list(hits), None
    if budget <= 0:
        return list(hits), None
    unique: list[dict] = []
    seen: set[str] = set()
    for index, hit in enumerate(hits):
        key = _document_key(hit, index)
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    module = _load_context_budget()
    if module is None:
        return [], {
            "max_tokens": budget,
            "estimated_tokens": 0,
            "within_budget": True,
            "dropped": {"relevant": len(unique)},
            "unavailable": True,
        }
    fitted, report = module.fit_to_budget({"relevant": unique}, budget)
    retained = []
    for number, hit in enumerate(fitted.get("relevant", []), 1):
        item = dict(hit)
        item["citation"] = f"[{number}]"
        retained.append(item)
    return retained, report


def _open_graph_ro():
    """Read-only open van kb-graph.db; None bij afwezig/fout.

    Bewust NIET _kbindex.graph_connect(): die opent read-write, maakt
    directories aan en zet WAL — allemaal schrijfgedrag dat niet op de leesweg
    thuishoort. Geen sqlite_vec nodig (gewone tabellen zonder vectoren).
    """
    p = _kbindex.graph_index_path()
    if not p.exists():
        return None
    try:
        return sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    except Exception:
        return None


def graph_neighbor(hits) -> "dict | None":
    """Beste graafbuur van de wiki-hits via kb-graph.db (TASK-87).

    Vervangt de legacy regex-expansie (_rank.one_hop_neighbor: N× read_text in
    het promptbudget, 1 hop, ongewogen) door de gewogen, submilliseconde
    adjacency-query die er al was maar nergens op de retrieval-weg werd
    aangeroepen (TASK-67-constatering).

    Semantiek identiek aan de batch-keten: een stale of ontbrekende graaf
    degradeert naar GEEN buur, nooit naar een verkeerde buur. Pariteit met het
    legacy-gedrag: alleen wiki-buren, nooit een stem die al hit is, bestand
    moet bestaan, deterministische tie-break. Fail-open: elke fout -> None.
    """
    conn = _open_graph_ro()
    if conn is None:
        return None
    try:
        gpath = _vault_root() / "graphify-out" / "graph.json"
        if not _kbindex.graph_is_current(conn, gpath):
            return None
        root = _vault_root().resolve()
        hit_stems = {Path(h.get("path", "")).stem for h in hits}
        weights = {}
        for h in hits:
            if h.get("layer") != "wiki":
                continue
            # kb-index bewaart absolute OS-paden; de graaf vault-relatieve
            # POSIX-paden ("02-wiki/x.md"). Reduceer naar dezelfde sleutel.
            try:
                rel = Path(h["path"]).resolve().relative_to(root).as_posix()
            except Exception:
                rel = Path(h.get("path", "")).as_posix().lstrip("/")
            for nb in _kbindex.graph_neighbors(conn, rel, limit=5):
                sf = str(nb.get("source_file") or "")
                if not (sf.startswith("02-wiki/") and sf.endswith(".md")):
                    continue
                if Path(sf).stem in hit_stems:
                    continue
                weights[sf] = weights.get(sf, 0.0) + float(nb.get("weight", 0.0))
        for sf, _w in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0])):
            cand = _vault_root() / sf
            if cand.exists():
                return {"path": str(cand), "stem": cand.stem}
        return None
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _coupling_enabled() -> bool:
    """Knop voor het bibliographic-coupling-signaal (TASK-88, default UIT).

    Zelfde conventie als de andere retrieval-knoppen: env ``KB_RANK_COUPLING``
    wint van ``"rank_coupling"`` in <vault>/.claude/kennisbank-embed.json.
    Fail-soft naar False — activering is een bewuste keuze ná de kb-eval A/B
    op de >=100-vraag-sets (bewijsregel TASK-86), geen sluiproute.
    """
    raw = os.environ.get("KB_RANK_COUPLING")
    if raw is not None:
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    try:
        import json
        cfg_file = _vault_root() / ".claude" / "kennisbank-embed.json"
        cfg = json.loads(cfg_file.read_text(encoding="utf-8")) or {}
        return bool(cfg.get("rank_coupling", 0))
    except Exception:
        return False


def _coupling_sources_fn(conn, rows):
    """Batch-lookup van provenance-sleutels; None als de knop uit staat of
    er niets te wegen valt. Eén extra query op de al-open connectie."""
    if not _coupling_enabled():
        return None
    try:
        ids = [r["doc_id"] for r in rows if r.get("doc_id") is not None]
        smap = _kbindex.sources_for(conn, ids)
        if not smap:
            return None
        by_path = {r["path"]: smap.get(r.get("doc_id"), set()) for r in rows}
        return lambda p: by_path.get(p, set())
    except Exception:
        return None


def _neighbor_entry(out) -> "dict | None":
    """Bouw de (buur)-expansie-entry voor een hits-lijst; None = geen buur.

    TASK-93: de legacy regex-expansie (_rank.one_hop_neighbor) is verwijderd
    nadat vier releases met graph_retrieval default AAN geen regressie
    meldden. ``graph_retrieval`` gaat daarmee van source-select (graaf vs.
    legacy) naar een zuivere aan/uit-schakelaar voor de graafbuur — uit
    betekent geen buur, niet meer een terugval op de oude implementatie.
    ``expand`` blijft de master-switch in recall_hits. Fail-open: elke
    fout -> None.
    """
    try:
        try:
            import _settings
            use_graph = bool(_settings.get("graph_retrieval", True))
        except Exception:
            # _settings unreadable is not "feature off". get() is already
            # fail-open (missing file/key -> default), so this branch only
            # fires when the module itself cannot load; keep the shipped
            # default (ON) instead of silently disabling a default-ON
            # feature (TASK-188).
            use_graph = True
        if not use_graph:
            return None
        nb = graph_neighbor(out)
        stem = nb["stem"] if nb else None
        p = Path(nb["path"]) if nb else None
        if not stem or p is None:
            return None
        snippet = emb.doc_text(p, cap=280).replace("\n", " ").strip()
        return {"path": str(p), "layer": "wiki", "title": stem,
                "created": "", "score": 0.0, "snippet": snippet,
                "neighbor": True}
    except Exception:
        return None


def _recall_hits_impl(query_vector, query_text: str = "", k: int = 3,
                      layers=("wiki", "memory"), expand: bool = False,
                      min_cos: float = 0.0, fusion: str = "rrf",
                      max_tokens=0) -> tuple[list, dict | None]:
    if not query_vector:
        return [], None
    conn = _open_ro_checked(_kbindex.index_path())
    try:
        live_id = emb.embed_id()
        if not _kbindex.is_valid_for(conn, live_id):
            stored = _kbindex.meta_get(conn, "embed_id")
            if not stored:
                raise _kbindex.IndexUnavailable(
                    "index_stamp_missing",
                    "index mist het embed_id-stempel",
                )
            raise _kbindex.IndexUnavailable(
                "embed_mismatch",
                f"index gebruikt {stored}, actueel model is {live_id}",
            )
        rows = _kbindex.search(conn, query_vector=query_vector, query_text=query_text,
                               k=k, layers=tuple(layers), statuses=("current",),
                               min_cos=min_cos, fusion=fusion)
        out = []
        for r in rows:
            layer = r.get("layer", "")
            if layer == "memory" and _mem.read_status(Path(r["path"])) != "current":
                continue
            snippet = emb.doc_text(Path(r["path"]), cap=280).replace("\n", " ").strip()
            out.append({"path": r["path"], "layer": layer, "title": r.get("title", ""),
                        "created": r.get("created", ""), "score": r.get("score", 0.0),
                        "cos": r.get("cos"), "fts": r.get("fts", False),
                        "snippet": snippet})
        try:
            import _usage
            _stats = _usage.stats_for(Path(r["path"]).stem for r in out)
            _lu = lambda stem: _stats.get(stem, {}).get("last_used", "")
            _nf = lambda stem: (_stats.get(stem, {}).get("noise", 0),
                                _stats.get(stem, {}).get("injected", 0))
        except Exception:
            _lu = None
            _nf = None
        out = _rank.rerank(out, _frontmatter_of, last_used_fn=_lu, noise_fn=_nf,
                           sources_fn=_coupling_sources_fn(conn, rows))
        out = out[:k]
        if expand and out:
            try:
                entry = _neighbor_entry(out)
                if entry:
                    out.append(entry)
            except Exception:
                pass
        return _fit_hits(out, max_tokens)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def recall_hits_with_status(query_vector, query_text: str = "", k: int = 3,
                            layers=("wiki", "memory"), expand: bool = False,
                            min_cos: float = 0.0, fusion: str = "rrf",
                            max_tokens=0) -> dict:
    """Return hits plus an explicit ``ok``/``no_hit``/``unusable`` status."""
    try:
        hits, budget_report = _recall_hits_impl(
            query_vector, query_text=query_text, k=k, layers=layers,
            expand=expand, min_cos=min_cos, fusion=fusion,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        code, message = _index_error(exc)
        return {"status": "unusable", "hits": [], "code": code, "message": message}
    return {
        "status": "ok" if hits else "no_hit",
        "hits": hits,
        "code": "",
        "message": "",
        "budget_report": budget_report,
    }


def recall_hits(query_vector, query_text: str = "", k: int = 3,
                layers=("wiki", "memory"), expand: bool = False,
                min_cos: float = 0.0, fusion: str = "rrf", max_tokens=0) -> list:
    """Recall-hits over de opgegeven lagen (status=current), fail-soft -> []."""
    return recall_hits_with_status(
        query_vector, query_text=query_text, k=k, layers=layers,
        expand=expand, min_cos=min_cos, fusion=fusion, max_tokens=max_tokens,
    )["hits"]


# Memories zijn kort en atomair; hun cosinus tegen een prompt ligt structureel
# lager dan die van een wiki-artikel. Daarom een EIGEN drempel, geen overerving
# van retrieve_threshold -- dat zou het memory-blok stilzwijgend dichtzetten.
#
# KB_MEMORY_THRESHOLD overrides the default. Needed to compare embedding models
# fairly: every model has its own cosine scale, so a fixed floor measures "how
# qwen3-like does this model score" instead of how well it ranks. Set it to 0.0
# for a rank-only measurement (see scripts/embed-sweep.py).
#
# 0.45 is measured, not inherited. Across 1224 memory questions the cosine of a
# true hit sits at min 0.340, p10 0.484, p50 0.615 on qwen3-embedding:4b, and at
# min 0.330, p10 0.528, p50 0.638 on qwen3-embedding:8b -- structurally below
# wiki articles (p50 0.761), exactly as the paragraph above predicts. What each
# floor discards of what the index could return:
#
#            4b (806 retrievable)   8b (798 retrievable)
#     0.40      6 lost                 2 lost
#     0.45     42 lost                13 lost
#     0.50    111 lost                45 lost
#     0.60    366 lost (45%)         260 lost (33%)
#
# So 0.60 did NOT become wrong through a model switch: it was already too high
# on the model it was once chosen for, discarding a third of the retrievable
# memories there. The switch merely made it visible. 0.45 keeps the noise band
# of 0.51 (measured on the 8b) out. Recalibrate after a model switch: a single
# pass that records the cosine of the expected hit per question yields the whole
# curve.
MEMORY_MIN_COS = env_float("KB_MEMORY_THRESHOLD", 0.45)


def memory_hits(query_vector, query_text: str = "", k: int = 3,
                min_cos: float = MEMORY_MIN_COS, fusion: str = "rrf",
                max_tokens=0) -> list:
    """Dunne wrapper: alleen de memory-laag (backward-compat)."""
    return recall_hits(query_vector, query_text=query_text, k=k, layers=("memory",),
                       min_cos=min_cos, fusion=fusion, max_tokens=max_tokens)


def index_status() -> dict:
    """Return the index runtime state without hiding a broken sqlite-vec setup."""
    try:
        conn = _open_ro_checked(_kbindex.index_path())
    except Exception as exc:
        code, message = _index_error(exc)
        return {"status": "unusable", "code": code, "message": message}
    try:
        live_id = emb.embed_id()
        stored = _kbindex.meta_get(conn, "embed_id")
        if not stored:
            return {"status": "unusable", "code": "index_stamp_missing",
                    "message": "index mist het embed_id-stempel"}
        if stored != live_id:
            return {"status": "unusable", "code": "embed_mismatch",
                    "message": f"index gebruikt {stored}, actueel model is {live_id}"}
        return {"status": "ok", "code": "", "message": "",
                "unit_norm": _kbindex.meta_get(conn, "unit_norm") == "1"}
    except Exception as exc:
        code, message = _index_error(exc)
        return {"status": "unusable", "code": code, "message": message}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def index_is_gated() -> bool:
    """True only when the live index can enforce its relevance gate."""
    state = index_status()
    return state.get("status") == "ok" and bool(state.get("unit_norm"))


def has_fts_match(query_text: str, layer: str = "wiki") -> bool:
    """True als een FTS5-keyword-match bestaat in de gegeven laag. Fail-soft.

    Tokeniseert op woorden >= 4 tekens (ge-OR'd) zodat stopwoorden en losse
    leestekens geen vals signaal of FTS5-syntaxfout geven."""
    match_expr = _kbindex.fts_expr(query_text)
    if not match_expr:
        return False
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
              expand: bool = False, min_cos: float = 0.0,
              fusion: str = "rrf", max_tokens=0) -> list:
    """Dunne wrapper: alleen de wiki-laag (hybride, optioneel met graafbuur)."""
    return recall_hits(query_vector, query_text=query_text, k=k,
                       layers=("wiki",), expand=expand, min_cos=min_cos,
                       fusion=fusion, max_tokens=max_tokens)

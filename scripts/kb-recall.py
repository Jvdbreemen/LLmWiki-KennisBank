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
        use_graph = False
        try:
            import _settings
            use_graph = bool(_settings.get("graph_retrieval", True))
        except Exception:
            use_graph = False
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


def _scene_path(path) -> str:
    """Path in the form kb-scene.db stores.

    Scene members are written with forward slashes, while the index hands back
    native Windows paths with backslashes. Comparing the two raw forms matches
    nothing and reports nothing -- the same silent mismatch that cost the first
    scene build all 1428 of its members, in the opposite direction. One helper,
    used by both the membership test and the lookup.
    """
    return str(path or "").replace("\\", "/")


def _merge_scene_members(rows_primary, rows_wide, members, boost: float) -> list:
    """Add members of the winning scene to the baseline rows. Additive only.

    A row already present keeps its position AND its score untouched: the
    baseline result stays a strict subset of the treatment, which is what makes
    the parity claim provable instead of hopeful. Re-scoring a primary hit would
    let the prior reorder results it was never meant to touch, and would make a
    recall@1 regression impossible to attribute to admission versus reordering.
    """
    seen = {_scene_path(r.get("path")) for r in rows_primary}
    out = list(rows_primary)
    for r in rows_wide:
        path = _scene_path(r.get("path"))
        if path in seen or path not in members:
            continue
        extra = dict(r)
        extra["score"] = float(extra.get("score", 0.0)) + float(boost)
        extra["scene"] = True
        out.append(extra)
        seen.add(path)
    return out


def _scene_members_for(rows_primary, prior) -> set:
    """Member paths of the scene(s) the strongest baseline hits belong to.

    The scene is chosen by MEMBERSHIP of the top hits, not by similarity to a
    scene centroid. Centroid matching was tried first and is worthless here: a
    centroid over ~19 atomic memories averages into a generic direction, and
    measured on 856 questions the winning centroid contained NONE of the twenty
    nearest memories. It also measured something different from the oracle
    ceiling, which counts a miss as reachable when its gold memory shares a
    scene with a RETRIEVED hit -- so the implementation could not realise the
    bound it was being judged against.

    Routing from the top hit is what the L2 idea actually says: the strongest
    match tells you which working context you are in, and the scene supplies
    its neighbours. It is also cheaper -- one indexed lookup instead of a scan
    over every centroid.

    ``prior["seeds"]`` (default 1) is how many top hits may nominate a scene.

    Fail-open: any failure yields an empty set, which makes
    _merge_scene_members a no-op. There is deliberately no error path in which
    the caller behaves differently from baseline.
    """
    if not rows_primary:
        return set()
    try:
        import _scenes
        path = _scenes.scene_index_path()
        if not path.exists():
            return set()
        conn = _scenes.connect(path)
        try:
            if not _scenes.is_current(conn, _kbindex.index_path()):
                return set()
            seeds = int(prior.get("seeds", 1) or 1)
            members = set()
            for row in rows_primary[:seeds]:
                found = conn.execute(
                    "SELECT scene_id FROM scene_members WHERE path=?",
                    (_scene_path(row.get("path", "")),)).fetchone()
                if found:
                    members.update(_scenes.members_of(conn, found[0]))
            return members
        finally:
            conn.close()
    except Exception:
        return set()


def recall_hits(query_vector, query_text: str = "", k: int = 3,
                layers=("wiki", "memory"), expand: bool = False,
                min_cos: float = 0.0, scene_prior=None) -> list:
    """Recall-hits over de opgegeven lagen (status=current), fail-soft -> [].
    Live-status-hercheck ALLEEN voor de memory-laag (wiki is gecureerd).

    Ranking: de hybride RRF-score wordt voor de memory-laag herwogen met
    recency (halfwaardetijd per memory_type) en importance (judge, 1-5);
    wiki blijft ongewogen (zie _rank).

    ``expand=True`` voegt na de directe hits de gewogen graafbuur toe (via
    ``_neighbor_entry`` / ``graph_neighbor``, TASK-87/93) als extra entry met
    ``neighbor: True`` — altijd ACHTERAAN, verdringt nooit een directe hit.
    ``graph_retrieval`` uit levert dan GEEN buur (TASK-93: de legacy
    wikilink-expansie-terugval is verwijderd, geen source-select meer).
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
                               k=k, layers=tuple(layers), statuses=("current",),
                               min_cos=min_cos)
        # L2 scene prior (TASK-134). scene_prior=None issues no second query and
        # leaves `rows` exactly as the baseline produced them -- the parity path.
        if scene_prior:
            members = _scene_members_for(rows, scene_prior)
            if members:
                wide = _kbindex.search(
                    conn, query_vector=query_vector, query_text=query_text,
                    k=k * 4, layers=tuple(layers), statuses=("current",),
                    min_cos=float(scene_prior.get("floor", 0.35)))
                rows = _merge_scene_members(
                    rows, wide, members, float(scene_prior.get("boost", 0.0)))
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
                        "cos": r.get("cos"), "fts": r.get("fts", False),
                        "snippet": snippet})
        try:
            import _usage
            # Eén batch-query voor alle kandidaten in plaats van twee opens per
            # treffer tijdens het herwegen.
            _stats = _usage.stats_for(Path(r["path"]).stem for r in out)
            _lu = lambda stem: _stats.get(stem, {}).get("last_used", "")
            _nf = lambda stem: (_stats.get(stem, {}).get("noise", 0),
                                _stats.get(stem, {}).get("injected", 0))
        except Exception:
            _lu = None
            _nf = None
        out = _rank.rerank(out, _frontmatter_of, last_used_fn=_lu, noise_fn=_nf,
                           sources_fn=_coupling_sources_fn(conn, rows))
        # The scene prior may have pushed the candidate list past k. Cut here,
        # after reranking, so an admitted member can win a slot but can never
        # inflate the injected block beyond the configured top_n.
        out = out[:k]
        if expand and out:
            try:
                entry = _neighbor_entry(out)
                if entry:
                    out.append(entry)
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
def _memory_min_cos_default() -> float:
    try:
        return float(os.environ.get("KB_MEMORY_THRESHOLD", "").strip() or 0.45)
    except ValueError:
        return 0.45


MEMORY_MIN_COS = _memory_min_cos_default()


def memory_hits(query_vector, query_text: str = "", k: int = 3,
                min_cos: float = MEMORY_MIN_COS, scene_prior=None) -> list:
    """Dunne wrapper: alleen de memory-laag (backward-compat)."""
    return recall_hits(query_vector, query_text=query_text, k=k, layers=("memory",),
                       min_cos=min_cos, scene_prior=scene_prior)


def index_is_gated() -> bool:
    """True als de index zelf een relevantiedrempel kan afdwingen.

    Vereist een geldige index voor het live embedmodel EN de unit_norm-vlag:
    zonder genormaliseerde vectoren klopt de afstand-naar-cosinus-omrekening
    niet en past search() geen drempel toe. De aanroeper kan dan niet op de
    index vertrouwen als poort en moet de oude cosine-cache-weg nemen.

    Eén read-only sqlite-open; ordes goedkoper dan de JSON-cache parsen.
    """
    conn = _open_ro(_kbindex.index_path())
    if conn is None:
        return False
    try:
        return (_kbindex.is_valid_for(conn, emb.embed_id())
                and _kbindex.meta_get(conn, "unit_norm") == "1")
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
              expand: bool = False, min_cos: float = 0.0) -> list:
    """Dunne wrapper: alleen de wiki-laag (hybride, optioneel met graafbuur)."""
    return recall_hits(query_vector, query_text=query_text, k=k,
                       layers=("wiki",), expand=expand, min_cos=min_cos)

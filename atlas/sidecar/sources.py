"""Read-only readers over the local KennisBank stores.

Every SQLite connection is opened with ``?mode=ro`` so the sidecar physically
cannot mutate a source DB (TASK-27.2 DoD #4). All readers fail-open: a missing
store yields an empty-but-valid result, never an exception.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path


def _connect_ro(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _rel_key(vault: Path, path: str) -> str:
    """Normalise a stored doc path to a vault-relative POSIX key.

    kb-index stores absolute OS paths; graphify stores vault-relative POSIX.
    Both are reduced to the same key ("02-wiki/x.md") so the join matches.
    """
    p = Path(path)
    try:
        p = p.relative_to(vault)
    except ValueError:
        pass
    return p.as_posix()


def kbindex_docs(vault: Path) -> dict[str, dict]:
    """Map vault-relative POSIX path -> {layer, status, title, created}."""
    conn = _connect_ro(vault / ".claude" / "kb-index.db")
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT path, layer, status, title, created FROM docs"
        ).fetchall()
        return {_rel_key(vault, r["path"]): dict(r) for r in rows}
    except Exception:
        return {}
    finally:
        conn.close()


def load_graph(vault: Path) -> dict:
    """Raw graphify graph.json ({nodes, links}), or empty on any failure."""
    path = vault / "graphify-out" / "graph.json"
    if not path.exists():
        return {"nodes": [], "links": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"nodes": data.get("nodes", []), "links": data.get("links", [])}
    except Exception:
        return {"nodes": [], "links": []}


_KEPT_PREFIXES = ("02-wiki/", "09-memory/")


def _kind_for(path: str) -> str:
    return "memory" if path.startswith("09-memory/") else "wiki"


def _is_kept(source_file: str | None) -> bool:
    return bool(source_file) and source_file.endswith(".md") and \
        source_file.startswith(_KEPT_PREFIXES)


def usage_warmth(vault: Path) -> dict[str, float]:
    """Map file stem -> warmth (usage `used` count) from kb-usage."""
    conn = _connect_ro(vault / ".claude" / "kb-usage.db")
    if conn is None:
        return {}
    try:
        return {r["stem"]: float(r["used"] or 0)
                for r in conn.execute("SELECT stem, used FROM usage")}
    except Exception:
        return {}
    finally:
        conn.close()


def build_graph(vault: Path, *, include_memory: bool = False) -> dict:
    """Collapse the graphify graph to file-level wiki/memory nodes joined with
    kb-index, with file-level links and degree. See ADR-0004 /graph contract.

    include_memory (opt-in, TASK-27.16) adds 09-memory fragments as nodes with
    their frontmatter (memory_type, importance, status, valid_from/until) and an
    edge to the wiki article each points to (from build_memory_links). The
    default stays wiki-only so the base map stays fast and clean."""
    raw = load_graph(vault)
    docs = kbindex_docs(vault)
    warmth = usage_warmth(vault)

    # slug -> source_file for every node (fragments included), so links that
    # touch a fragment resolve to that fragment's owning file.
    slug_to_file: dict[str, str] = {}
    for n in raw["nodes"]:
        sf = n.get("source_file")
        if sf:
            slug_to_file[n["id"]] = sf

    # one node per kept source_file
    nodes: dict[str, dict] = {}
    for n in raw["nodes"]:
        sf = n.get("source_file")
        if not _is_kept(sf) or sf in nodes:
            continue
        meta = docs.get(sf, {})
        kind = _kind_for(sf)
        nodes[sf] = {
            "id": sf,
            "label": Path(sf).name,
            "kind": kind,
            "layer": meta.get("layer") or kind,
            "node_status": meta.get("status") or "active",
            # community-detection cluster from graphify; drives node colour.
            "community": n.get("community"),
            "community_name": n.get("community_name"),
            "memory_type": None,
            "importance": 0.0,
            "warmth": warmth.get(Path(sf).stem, 0.0),
            # created = capture-time axis for the Time-slider (wiki has no valid
            # time; memory keeps valid_from/valid_until for true validity).
            "created": meta.get("created") or None,
            "valid_from": None,
            "valid_until": None,
            "degree": 0,
        }

    # collapse links to file level, drop self-loops, aggregate weight
    edges: dict[tuple[str, str], dict] = {}
    for l in raw["links"]:
        src = slug_to_file.get(l.get("source"))
        tgt = slug_to_file.get(l.get("target"))
        if not src or not tgt or src not in nodes or tgt not in nodes or src == tgt:
            continue
        key = tuple(sorted((src, tgt)))
        if key in edges:
            edges[key]["weight"] += float(l.get("weight", 1.0))
        else:
            edges[key] = {
                "source": key[0],
                "target": key[1],
                "rel": l.get("relation", ""),
                "weight": float(l.get("weight", 1.0)),
            }

    if include_memory:
        _add_memory_nodes(vault, nodes, edges, warmth)

    for e in edges.values():
        if e["source"] in nodes:
            nodes[e["source"]]["degree"] += 1
        if e["target"] in nodes:
            nodes[e["target"]]["degree"] += 1

    node_list = sorted(nodes.values(), key=lambda n: n["id"])
    link_list = sorted(edges.values(), key=lambda e: (e["source"], e["target"]))
    status = "ok" if node_list else "empty"
    return {"status": status, "nodes": node_list, "links": link_list}


def _add_memory_nodes(vault: Path, nodes: dict, edges: dict, warmth: dict) -> None:
    """Add 09-memory fragments as nodes plus a fragment->article edge each."""
    links = build_memory_links(vault)
    mem_dir = vault / "09-memory"
    if not mem_dir.is_dir():
        return
    for path in sorted(mem_dir.glob("*.md")):
        stem = path.stem
        mem_id = f"09-memory/{stem}.md"
        if mem_id in nodes:
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        nodes[mem_id] = {
            "id": mem_id,
            "label": path.name,
            "kind": "memory",
            "layer": "memory",
            "node_status": fm.get("status", "current"),
            "community": None,
            "community_name": None,
            "memory_type": fm.get("memory_type", "feit"),
            "importance": _coerce_importance(fm.get("importance", 3)),
            "warmth": warmth.get(stem, 0.0),
            "created": fm.get("updated") or fm.get("valid_from") or fm.get("created") or None,
            "valid_from": fm.get("valid_from") or fm.get("created") or None,
            "valid_until": fm.get("valid_until"),
            "degree": 0,
        }
        target = links.get("links", {}).get(stem)
        if target and target in nodes:
            key = (mem_id, target)
            edges[key] = {"source": mem_id, "target": target,
                          "rel": "entry-point", "weight": 1.0}


def _parse_date(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None


def _bucket_start(d: date, bucket: str) -> date:
    if bucket == "week":
        return d - timedelta(days=d.weekday())  # Monday of the ISO week
    return d


def _bucket_end(start: date, bucket: str) -> date:
    return start + timedelta(days=7 if bucket == "week" else 1)


def build_timeline(vault: Path, *, bucket: str = "day",
                   frm: str | None = None, to: str | None = None,
                   dimension: str = "event") -> dict:
    """Aggregate activity_events into day/week buckets, bi-temporally.

    Each bucket carries event_count (rows whose event_time falls in it),
    capture_count (rows whose captured_at falls in it), and by_kind for the
    event-time grouping. ``dimension`` selects the field the [frm, to] range
    filters on. See ADR-0004 /timeline contract."""
    conn = _connect_ro(vault / ".claude" / "kb-activity.db")
    if conn is None:
        return {"status": "empty", "buckets": []}
    try:
        rows = conn.execute(
            "SELECT event_time, captured_at, activity_kind FROM activity_events"
        ).fetchall()
    except Exception:
        return {"status": "empty", "buckets": []}
    finally:
        conn.close()

    frm_d, to_d = _parse_date(frm), _parse_date(to)
    buckets: dict[date, dict] = {}

    def _slot(d: date) -> dict:
        start = _bucket_start(d, bucket)
        b = buckets.get(start)
        if b is None:
            b = {"start": start.isoformat() + "T00:00:00",
                 "end": _bucket_end(start, bucket).isoformat() + "T00:00:00",
                 "event_count": 0, "capture_count": 0, "by_kind": {}}
            buckets[start] = b
        return b

    def _in_range(d: date | None) -> bool:
        if d is None:
            return False
        if frm_d and d < frm_d:
            return False
        if to_d and d > to_d:
            return False
        return True

    for r in rows:
        ev = _parse_date(r["event_time"])
        cap = _parse_date(r["captured_at"])
        dim_d = ev if dimension == "event" else cap
        if (frm_d or to_d) and not _in_range(dim_d):
            continue
        if ev is not None:
            b = _slot(ev)
            b["event_count"] += 1
            kind = r["activity_kind"] or "activity"
            b["by_kind"][kind] = b["by_kind"].get(kind, 0) + 1
        if cap is not None:
            _slot(cap)["capture_count"] += 1

    ordered = [buckets[k] for k in sorted(buckets)]
    return {"status": "ok" if ordered else "empty", "buckets": ordered}


def _parse_frontmatter(text: str) -> dict:
    """Minimal YAML front-matter reader (key: value, simple [a, b] lists).

    Deliberately local and dependency-free so /memory-health stays hermetic;
    the vault's _memory module is not importable in a fixture vault."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm: dict = {}
    for line in text[3:end].splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fm[key] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
        else:
            fm[key] = val.strip("'\"")
    return fm


_ACTIVE_STATUSES = {"current", "active"}


def _coerce_importance(value) -> int:
    try:
        return min(5, max(1, int(value)))
    except (TypeError, ValueError):
        return 3


def _age_of(iso: str, today: date) -> int:
    d = _parse_date(iso)
    return max(0, (today - d).days) if d else 0


# Warm/stale thresholds mirror _rank.usage_factor (recent <= 30d, warm <= 90d).
def _temperature(last_used: str | None, today: date) -> str:
    if not last_used:
        return "stale"
    age = _age_of(last_used, today)
    return "warm" if age <= 30 else "tepid" if age <= 90 else "stale"


def build_memory_health(vault: Path, *, today: date | None = None) -> dict:
    """The Memory Health cockpit (TASK-27.6): lifecycle counts, the unverified
    quarantine queue, supersede chains (with valid_until), an importance x
    recency heatmap of active memories, and warmth/temperature from kb-usage.
    ``today`` is injectable for deterministic tests."""
    today = today or date.today()
    mem_dir = vault / "09-memory"
    empty = {
        "status": "empty",
        "counts": {"active": 0, "quarantined": 0, "superseded": 0, "unverified": 0},
        "queue": [], "supersede_chains": [], "heatmap": [], "warmth": [], "quarantine": [],
    }
    if not mem_dir.is_dir():
        return empty

    records: dict[str, dict] = {}
    for path in sorted(mem_dir.glob("*.md")):
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        ref = fm.get("updated") or fm.get("valid_from") or fm.get("created") or ""
        records[path.stem] = {
            "id": path.stem,
            "status": fm.get("status", "current"),
            "memory_type": fm.get("memory_type", "feit"),
            "importance": _coerce_importance(fm.get("importance", 3)),
            "created": ref,
            "valid_until": fm.get("valid_until"),
            "quarantine_reason": fm.get("quarantine_reason", ""),
            "superseded_by": fm.get("superseded_by", []) or [],
        }
    if not records:
        return empty

    counts = {"active": 0, "quarantined": 0, "superseded": 0, "unverified": 0}
    queue, quarantine, heatmap = [], [], []
    edges: list[tuple[str, str]] = []
    for r in records.values():
        st = r["status"]
        if st in _ACTIVE_STATUSES:
            counts["active"] += 1
            heatmap.append({"id": r["id"], "importance": r["importance"],
                            "age_days": _age_of(r["created"], today)})
        elif st == "quarantined":
            counts["quarantined"] += 1
            quarantine.append({"id": r["id"], "reason": r["quarantine_reason"]})
        elif st == "superseded":
            counts["superseded"] += 1
        elif st == "unverified":
            counts["unverified"] += 1
            queue.append({"id": r["id"], "importance": r["importance"], "created": r["created"]})
        for tgt in r["superseded_by"]:
            edges.append((r["id"], tgt))

    queue.sort(key=lambda q: (-q["importance"], q["created"], q["id"]))

    parent = dict(edges)
    heads = [s for s in parent if s not in parent.values()]
    chains = []
    for head in sorted(heads):
        chain, cur, guard = [head], head, 0
        while cur in parent and guard < 100:
            cur = parent[cur]
            chain.append(cur)
            guard += 1
        chains.append({"head": head, "chain": chain,
                       "valid_until": records.get(head, {}).get("valid_until")})

    warmth = _memory_warmth(vault, today)

    return {
        "status": "ok",
        "counts": counts,
        "queue": queue,
        "supersede_chains": chains,
        "heatmap": heatmap,
        "warmth": warmth,
        "quarantine": quarantine,
    }


def _stem_doc_path(vault: Path, stem: str) -> str:
    """kb-usage stores bare stems (mostly wiki articles, sometimes memory
    fragments). Resolve to the real vault-relative doc path so the UI can open
    it; a bare stem passed through unresolved yields a 404 in the viewer."""
    for prefix in ("02-wiki", "09-memory"):
        if (vault / prefix / f"{stem}.md").exists():
            return f"{prefix}/{stem}.md"
    return stem


def _memory_warmth(vault: Path, today: date | None = None) -> list[dict]:
    today = today or date.today()
    conn = _connect_ro(vault / ".claude" / "kb-usage.db")
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT stem, used, last_used FROM usage"
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()
    warm = [
        {"path": _stem_doc_path(vault, r["stem"]), "warmth": float(r["used"] or 0),
         "last_used": r["last_used"],
         "temperature": _temperature(r["last_used"], today)}
        for r in rows
    ]
    warm.sort(key=lambda w: (-w["warmth"], w["path"]))
    return warm


import re as _re

_WIKILINK_RE = _re.compile(r"\[\[([^\]]+)\]\]")
_HERKOMST_PREFIXES = ("raw-sessie", "05-bronnen/")


def _has_herkomst(text: str) -> bool:
    for raw in _WIKILINK_RE.findall(text):
        target = raw.split("|", 1)[0].strip().lstrip("/")
        if target.startswith(_HERKOMST_PREFIXES):
            return True
    return False


def build_provenance(vault: Path) -> dict:
    """Provenance coverage over 02-wiki. Reuses the vault's kb-lint (data-parity,
    TASK-27.9 DoD #1): an article is at-risk when kb-lint reports a missing,
    dangling, or path-only herkomst. Falls back to a local herkomst-link
    heuristic only when kb-lint cannot be loaded (e.g. a fixture vault)."""
    try:
        kb_lint = _load_vault_module(vault, "kb_lint", "kb-lint.py")
        report = kb_lint.lint_vault(vault.resolve())
        by_file: dict[str, list[dict]] = {}
        for w in report.get("warnings", []):
            by_file.setdefault(w["file"], []).append(w)
        unsourced = [
            {"path": f"02-wiki/{f}",
             "reason": "; ".join(w["detail"] for w in ws),
             "types": [w["type"] for w in ws]}
            for f, ws in sorted(by_file.items())
        ]
        return {
            "status": "ok",
            "coverage": {"sourced": report["clean"], "unsourced": report["warned"],
                         "total": report["articles"]},
            "unsourced": unsourced,
        }
    except Exception:
        return _provenance_heuristic(vault)


def _provenance_heuristic(vault: Path) -> dict:
    """Fallback: a wiki article is sourced when it carries a herkomst wikilink
    ([[raw-sessie-...]] or [[05-bronnen/...]]). Used when kb-lint is absent."""
    wiki_dir = vault / "02-wiki"
    if not wiki_dir.is_dir():
        return {"status": "empty",
                "coverage": {"sourced": 0, "unsourced": 0, "total": 0},
                "unsourced": []}

    sourced = 0
    unsourced: list[dict] = []
    total = 0
    for path in sorted(wiki_dir.glob("*.md")):
        total += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if _has_herkomst(text):
            sourced += 1
        else:
            unsourced.append({
                "path": f"02-wiki/{path.name}",
                "reason": "geen herkomst: geen [[raw-sessie-...]]- of [[05-bronnen/...]]-verwijzing",
            })

    if total == 0:
        return {"status": "empty",
                "coverage": {"sourced": 0, "unsourced": 0, "total": 0},
                "unsourced": []}
    return {
        "status": "ok",
        "coverage": {"sourced": sourced, "unsourced": len(unsourced), "total": total},
        "unsourced": unsourced,
    }


import importlib.util as _ilu
import os as _os
import sys as _sys


def _load_vault_module(vault: Path, name: str, filename: str):
    """Import a vault script by file path (handles hyphenated module names).

    The vault's .claude/scripts dir is added to sys.path so intra-module
    imports (_kbindex, _embeddings, ...) resolve. Reused, not reimplemented,
    so /recall ordering matches kb-recall exactly (TASK-27.2 AC#2)."""
    scripts = (vault / ".claude" / "scripts").resolve()
    _os.environ.setdefault("KENNISBANK_VAULT", str(vault))
    if str(scripts) not in _sys.path:
        _sys.path.insert(0, str(scripts))
    spec = _ilu.spec_from_file_location(name, scripts / filename)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def live_recall(vault: Path, query: str, k: int = 3) -> dict:
    """Run the live recall waterfall by reusing the vault's kb-recall.

    Embeds the query once via _embeddings, then calls kb-recall.recall_hits so
    the `final` ordering is identical to the production hook. `stages` are
    surfaced best-effort; the full per-stage waterfall is the Recall Inspector
    (27.8). Fail-open on any error."""
    empty = {"status": "empty", "query": query,
             "stages": {"vector": [], "fts": [], "rrf": [], "rerank": []},
             "final": []}
    if not query.strip():
        return empty
    try:
        emb = _load_vault_module(vault, "_embeddings", "_embeddings.py")
        kbrecall = _load_vault_module(vault, "kb_recall", "kb-recall.py")
        vector = emb.embed(query)
        if not vector:
            return {**empty, "status": "degraded"}
        hits = kbrecall.recall_hits(vector, query_text=query, k=k)
        final = [
            {"path": h.get("path", ""), "score": float(h.get("score", 0.0)),
             "snippet": h.get("snippet", "")}
            for h in hits
        ]
        return {
            "status": "ok" if final else "empty",
            "query": query,
            "stages": {"vector": [], "fts": [], "rrf": [], "rerank": []},
            "final": final,
        }
    except Exception:
        return {**empty, "status": "degraded"}


class DocError(Exception):
    """Raised by read_doc with an HTTP-ish status code for the route to map."""
    def __init__(self, code: int, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def read_doc(vault: Path, rel_path: str) -> dict:
    """Read a vault markdown file for the inspect panel. Fail-closed:
    reject non-.md and any path that escapes the vault (traversal)."""
    if not rel_path or not rel_path.endswith(".md"):
        raise DocError(400, "alleen .md-bestanden")
    vault_root = vault.resolve()
    target = (vault_root / rel_path).resolve()
    # Containment check: the resolved target must stay inside the vault.
    if vault_root != target and vault_root not in target.parents:
        raise DocError(400, "pad buiten de vault")
    if not target.is_file():
        raise DocError(404, "bestand niet gevonden")
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise DocError(404, str(exc))
    title = target.stem
    for line in content.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return {"status": "ok", "path": target.relative_to(vault_root).as_posix(),
            "title": title, "content": content}


_ASSET_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
}


def resolve_asset(vault: Path, rel_path: str) -> tuple[Path, str]:
    """Validate and locate a vault image for /asset. Fail-closed: only known
    image extensions, and the resolved path must stay inside the vault."""
    ext = Path(rel_path).suffix.lower() if rel_path else ""
    if ext not in _ASSET_TYPES:
        raise DocError(400, "alleen afbeeldingen")
    vault_root = vault.resolve()
    target = (vault_root / rel_path).resolve()
    if vault_root != target and vault_root not in target.parents:
        raise DocError(400, "pad buiten de vault")
    if not target.is_file():
        raise DocError(404, "afbeelding niet gevonden")
    return target, _ASSET_TYPES[ext]


def recall_waterfall(vault: Path, query: str, k: int = 8) -> dict:
    """The live retrieval waterfall for the Recall Inspector (TASK-27.8).

    Reuses the exact building blocks of the production pipeline and surfaces the
    intermediate stages: vector-KNN and FTS candidates, RRF fusion, and the
    per-hit rerank factors (relevance x recency x importance x trust x usage).
    Data-parity holds by construction: the same _kbindex._rrf, the same SQL, and
    the same _rank factor functions are used. Fail-open on any error."""
    empty = {"status": "empty", "query": query,
             "stages": {"vector": [], "fts": [], "rrf": [], "rerank": []},
             "final": []}
    if not query.strip():
        return empty
    try:
        import sqlite3
        from datetime import date as _date

        emb = _load_vault_module(vault, "_embeddings", "_embeddings.py")
        kbindex = _load_vault_module(vault, "_kbindex", "_kbindex.py")
        rank = _load_vault_module(vault, "_rank", "_rank.py")
        kbrecall = _load_vault_module(vault, "kb_recall", "kb-recall.py")
        try:
            usage = _load_vault_module(vault, "_usage", "_usage.py")
            last_used_of = usage.last_used_of
        except Exception:
            last_used_of = None

        vector = emb.embed(query)
        if not vector:
            return {**empty, "status": "degraded"}

        ipath = kbindex.index_path()
        conn = kbrecall._open_ro(ipath)  # opens RO + loads sqlite_vec
        if conn is None or not kbindex.is_valid_for(conn, emb.embed_id()):
            return {**empty, "status": "degraded"}
        try:
            total = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
            pool = min(max(k * 4, 20, total), 5000)
            vec_ids = [r[0] for r in conn.execute(
                "SELECT doc_id FROM vec_docs WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
                (kbindex._serialize(vector), pool)).fetchall()]
            fts_ids: list = []
            try:
                fts_ids = [r[0] for r in conn.execute(
                    "SELECT rowid FROM fts_docs WHERE fts_docs MATCH ? ORDER BY rank LIMIT ?",
                    (query, pool)).fetchall()]
            except sqlite3.OperationalError:
                pass
            fused = kbindex._rrf([lst for lst in (vec_ids, fts_ids) if lst])
            ids = set(vec_ids) | set(fts_ids)
            meta = {}
            if ids:
                ph = ",".join("?" for _ in ids)
                meta = {r[0]: r for r in conn.execute(
                    f"SELECT doc_id, path, layer, status, title, created FROM docs "
                    f"WHERE doc_id IN ({ph})", tuple(ids)).fetchall()}
        finally:
            conn.close()

        def _path(doc_id):
            r = meta.get(doc_id)
            return r[1] if r else str(doc_id)

        vector_stage = [{"path": _path(d), "score": round(1.0 / (i + 1), 4)}
                        for i, d in enumerate(vec_ids[:k])]
        fts_stage = [{"path": _path(d), "score": round(1.0 / (i + 1), 4)}
                     for i, d in enumerate(fts_ids[:k])]

        # top fused hits (wiki+memory, current), relevance = fused RRF score
        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
        hits = []
        for doc_id, fscore in ranked:
            r = meta.get(doc_id)
            if not r:
                continue
            _, path, layer, status, title, created = r
            if status not in ("current",):
                continue
            hits.append({"path": path, "layer": layer, "title": title,
                         "created": created, "relevance": fscore})
            if len(hits) >= k:
                break
        rrf_stage = [{"path": h["path"], "score": round(h["relevance"], 5)} for h in hits]

        # rerank: reuse _rank factor functions; expose factors + final product
        today = _date.today()
        rerank_stage, final = [], []
        for h in hits:
            factors = {"relevance": round(h["relevance"], 5)}
            score = h["relevance"]
            if h["layer"] == "memory":
                fm = kbrecall._frontmatter_of(h["path"]) or {}
                ref = fm.get("updated") or fm.get("valid_from") or fm.get("created") or ""
                rec = rank.recency_factor(rank._age_days(ref, today), fm.get("memory_type", "feit"))
                imp = rank.importance_factor(fm.get("importance", 3))
                tru = rank.trust_factor(fm.get("evidence_basis"))
                factors |= {"recency": round(rec, 4), "importance": round(imp, 4), "trust": round(tru, 4)}
                score *= rec * imp * tru
            if last_used_of is not None:
                try:
                    use = rank.usage_factor(last_used_of(Path(h["path"]).stem), today)
                except Exception:
                    use = 1.0
                factors["usage"] = round(use, 4)
                score *= use
            factors["final"] = round(score, 6)
            rerank_stage.append({"path": h["path"], "score": round(score, 6), "factors": factors})
            snippet = emb.doc_text(Path(h["path"]), cap=200).replace("\n", " ").strip()
            final.append({"path": h["path"], "score": round(score, 6), "snippet": snippet})

        rerank_stage.sort(key=lambda x: x["score"], reverse=True)
        final.sort(key=lambda x: x["score"], reverse=True)

        # graph-neighbour expansion: the most-referenced wiki neighbour of the
        # top hits, appended as an extra entry (reuses _rank.one_hop_neighbor).
        try:
            stem = rank.one_hop_neighbor(hits, vault.resolve())
            if stem and not any(Path(h["path"]).stem == stem for h in final):
                npath = (vault / "02-wiki" / f"{stem}.md")
                snippet = emb.doc_text(npath, cap=200).replace("\n", " ").strip()
                final.append({"path": str(npath), "score": 0.0, "snippet": snippet,
                              "neighbor": True})
                rerank_stage.append({"path": f"02-wiki/{stem}.md", "score": 0.0,
                                     "factors": {"final": 0.0}, "neighbor": True})
        except Exception:
            pass

        status = "ok" if final else "empty"
        return {"status": status, "query": query,
                "stages": {"vector": vector_stage, "fts": fts_stage,
                           "rrf": rrf_stage, "rerank": rerank_stage},
                "final": final}
    except Exception:
        return {**empty, "status": "degraded"}


# In-process cache: linking scans stored embeddings for all memories (~47s on
# the real vault), so compute once per sidecar process, keyed by vault path.
_MEMORY_LINKS_CACHE: dict[str, dict] = {}


def _mem_query_and_type(vault: Path, rel_path: str) -> tuple[str, str]:
    """From a memory fragment: (FTS-safe OR-query of title+opening terms,
    memory_type). One read serves both the linking query and the inspect type."""
    try:
        text = (vault / rel_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", "feit"
    fm = _parse_frontmatter(text)
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body = text[text.find("\n", end + 1) + 1:]
    blob = f"{fm.get('title', '')} {body[:240]}"
    seen, tokens = set(), []
    for tok in _re.findall(r"[A-Za-z0-9]{4,}", blob):
        low = tok.lower()
        if low not in seen:
            seen.add(low)
            tokens.append(low)
        if len(tokens) >= 12:
            break
    return " OR ".join(tokens), fm.get("memory_type", "feit")


def build_memory_links(vault: Path, *, use_cache: bool = True) -> dict:
    """Link each memory fragment to the wiki article it sits closest to, using
    the fragment's stored embedding and a vector-KNN to the wiki layer (the
    vector stage of recall — no Ollama re-embed, reuses the index). Returns
    per-fragment target and per-article entry-point counts (TASK-27.14).

    Design note: full-waterfall linking would re-embed 753 fragments (~12 min);
    stored-embedding vector similarity answers the same "which article would
    this fragment lead an agent to" far cheaper. Cached in-process."""
    key = str(vault.resolve())
    if use_cache and key in _MEMORY_LINKS_CACHE:
        return _MEMORY_LINKS_CACHE[key]

    empty = {"status": "empty", "links": {}, "counts": {}, "types": {}}
    try:
        kbindex = _load_vault_module(vault, "_kbindex", "_kbindex.py")
        kbrecall = _load_vault_module(vault, "kb_recall", "kb-recall.py")
        conn = kbrecall._open_ro(kbindex.index_path())
        if conn is None:
            return empty
        try:
            meta = {r[0]: (_rel_key(vault, r[1]), r[2])
                    for r in conn.execute("SELECT doc_id, path, layer FROM docs")}
            wiki_ids = {d for d, (_, layer) in meta.items() if layer == "wiki"}
            mem_ids = [d for d, (_, layer) in meta.items() if layer == "memory"]
            links: dict[str, str] = {}
            counts: dict[str, int] = {}
            types: dict[str, str] = {}
            for did in mem_ids:
                row = conn.execute(
                    "SELECT embedding FROM vec_docs WHERE doc_id = ?", (did,)).fetchone()
                if not row or row[0] is None:
                    continue
                # Hybrid link (no rerank, no re-embed): vector similarity on the
                # stored embedding fused (RRF) with an FTS match on the fragment
                # text. FTS catches exact terms the embedding blurs; rerank is
                # deliberately excluded — it would bias to popular, not closest.
                vec = [r[0] for r in conn.execute(
                    "SELECT doc_id FROM vec_docs WHERE embedding MATCH ? "
                    "ORDER BY distance LIMIT 20", (row[0],)).fetchall()]
                rankings = [vec]
                text, mtype = _mem_query_and_type(vault, meta[did][0])
                if text:
                    try:
                        fts = [r[0] for r in conn.execute(
                            "SELECT rowid FROM fts_docs WHERE fts_docs MATCH ? "
                            "ORDER BY rank LIMIT 20", (text,)).fetchall()]
                        if fts:
                            rankings.append(fts)
                    except sqlite3.OperationalError:
                        pass
                fused = kbindex._rrf(rankings)
                target = None
                for cid, _score in sorted(fused.items(), key=lambda kv: kv[1], reverse=True):
                    if cid in wiki_ids:
                        target = meta[cid][0]
                        break
                if target:
                    stem = Path(meta[did][0]).stem
                    links[stem] = target
                    types[stem] = mtype
                    counts[target] = counts.get(target, 0) + 1
        finally:
            conn.close()
    except Exception:
        return empty

    result = {"status": "ok" if links else "empty", "links": links,
              "counts": counts, "types": types} if (links or counts) else empty
    if use_cache:
        _MEMORY_LINKS_CACHE[key] = result
    return result


def memory_links_for(vault: Path, article_path: str) -> list[str]:
    """The memory-fragment stems that point to a given wiki article path."""
    data = build_memory_links(vault)
    return sorted(s for s, a in data.get("links", {}).items() if a == article_path)

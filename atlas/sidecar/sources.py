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


def build_graph(vault: Path) -> dict:
    """Collapse the graphify graph to file-level wiki/memory nodes joined with
    kb-index, with file-level links and degree. See ADR-0004 /graph contract."""
    raw = load_graph(vault)
    docs = kbindex_docs(vault)

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
            "memory_type": None,
            "importance": 0.0,
            "warmth": 0.0,
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

    for e in edges.values():
        nodes[e["source"]]["degree"] += 1
        nodes[e["target"]]["degree"] += 1

    node_list = sorted(nodes.values(), key=lambda n: n["id"])
    link_list = sorted(edges.values(), key=lambda e: (e["source"], e["target"]))
    status = "ok" if node_list else "empty"
    return {"status": status, "nodes": node_list, "links": link_list}


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

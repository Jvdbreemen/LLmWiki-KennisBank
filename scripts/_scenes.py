#!/usr/bin/env python3
"""_scenes.py - the derived L2 scene layer (kb-scene.db).

A scene groups atomic memories that belong to the same project or working
context. Scenes are DERIVED: they are rebuilt from kb-index.db and kb-graph.db
and are never written as vault markdown. Two reasons. A markdown scene would
enter the corpus, be indexed, show up in Obsidian, and could be counted as a
correct answer by the eval harness -- the exact circularity this experiment
must avoid. And a derived store can be thrown away and rebuilt, like
kb-graph.db.

Pure stdlib library: no network, no embedding calls, no side effects at import.
Centroids are built from vectors that kb-index.db already holds.

See docs/superpowers/specs/2026-08-05-l2-scene-retrieval-design.md (TASK-134).
"""
from __future__ import annotations

import math
import os
import sqlite3
import struct
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

CLUSTERERS = ("community", "tags", "llm")


def scene_index_path() -> Path:
    """Own database file, beside kb-index.db and kb-graph.db."""
    return vault_root() / ".claude" / "kb-scene.db"


def connect(path=None) -> sqlite3.Connection:
    return sqlite3.connect(str(path or scene_index_path()))


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the scene tables. Idempotent."""
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS scenes ("
        "scene_id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, "
        "clusterer TEXT, size INTEGER, built_at TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS scene_members ("
        "scene_id INTEGER NOT NULL, path TEXT NOT NULL, "
        "PRIMARY KEY (scene_id, path))")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS scene_centroids ("
        "scene_id INTEGER PRIMARY KEY, vector BLOB)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_scene_members_path "
                 "ON scene_members(path)")
    conn.commit()


def serialize(vector) -> bytes:
    """Vector to the float32 blob format, same encoding as _kbindex._serialize."""
    v = [float(x) for x in vector]
    return struct.pack("%sf" % len(v), *v)


def deserialize(blob) -> list:
    n = len(blob) // 4
    return list(struct.unpack("%sf" % n, blob))


def centroid(vectors) -> list:
    """Normalised mean of the member vectors. Empty input -> [].

    Stored normalised for the same reason _kbindex stores unit vectors: with
    unit length on both sides the dot product IS the cosine, so best_scene()
    needs no square roots at query time.
    """
    rows = [list(v) for v in vectors if v]
    if not rows:
        return []
    dim = len(rows[0])
    acc = [0.0] * dim
    for v in rows:
        if len(v) != dim:
            continue
        for i in range(dim):
            acc[i] += float(v[i])
    norm = math.sqrt(sum(x * x for x in acc))
    if norm == 0.0:
        return acc
    return [x / norm for x in acc]


def write_scenes(conn: sqlite3.Connection, clusterer: str, scenes) -> int:
    """Replace every scene with the given set.

    ``scenes``: iterable of (label, member_paths, centroid_vector).
    Returns the number of scenes written.

    A full replace, not a merge: a scene index is a snapshot of one clusterer
    over one index state. Mixing two runs would produce overlapping scenes and
    make the prior fire twice for one query.
    """
    ensure_schema(conn)
    conn.execute("DELETE FROM scene_members")
    conn.execute("DELETE FROM scene_centroids")
    conn.execute("DELETE FROM scenes")
    built = date.today().isoformat()
    count = 0
    for label, members, vec in scenes:
        paths = [str(p).replace("\\", "/") for p in members]
        cur = conn.execute(
            "INSERT INTO scenes(label, clusterer, size, built_at) VALUES (?,?,?,?)",
            (str(label), str(clusterer), len(paths), built))
        sid = cur.lastrowid
        for p in paths:
            conn.execute("INSERT OR IGNORE INTO scene_members(scene_id, path) "
                         "VALUES (?,?)", (sid, p))
        if vec:
            conn.execute("INSERT INTO scene_centroids(scene_id, vector) VALUES (?,?)",
                         (sid, serialize(vec)))
        count += 1
    conn.commit()
    return count


def members_of(conn: sqlite3.Connection, scene_id) -> list:
    rows = conn.execute("SELECT path FROM scene_members WHERE scene_id=?",
                        (scene_id,)).fetchall()
    return [r[0] for r in rows]


def best_scene(conn: sqlite3.Connection, query_vector, min_cos: float):
    """Highest-scoring scene centroid above min_cos, or None.

    Centroids are stored normalised and the query is normalised here, so the
    dot product is the cosine. A few hundred centroids: a full scan is
    sub-millisecond and needs no vector index.
    """
    q = [float(x) for x in (query_vector or [])]
    if not q:
        return None
    norm = math.sqrt(sum(x * x for x in q))
    if norm == 0.0:
        return None
    q = [x / norm for x in q]
    best = None
    for sid, blob in conn.execute("SELECT scene_id, vector FROM scene_centroids"):
        try:
            vec = deserialize(blob)
        except Exception:
            continue
        if len(vec) != len(q):
            continue
        cos = sum(a * b for a, b in zip(q, vec))
        if cos >= min_cos and (best is None or cos > best[1]):
            best = (sid, cos)
    return best


def fingerprint(index_path) -> str:
    """Cheap fingerprint of kb-index.db: mtime + size.

    Same pattern as _kbindex.graph_fingerprint. Cheap beats exact here: a
    stale scene index must degrade to baseline, and a false "stale" costs one
    rebuild while a false "current" would silently measure the wrong corpus.
    """
    try:
        st = Path(index_path).stat()
        return f"{int(st.st_mtime)}:{st.st_size}"
    except Exception:
        return ""


def set_fingerprint(conn: sqlite3.Connection, fp: str) -> None:
    ensure_schema(conn)
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('index_fp', ?)",
                 (str(fp),))
    conn.commit()


def is_current(conn: sqlite3.Connection, index_path) -> bool:
    """True when the scenes were built from this exact kb-index.db state."""
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='index_fp'").fetchone()
    except Exception:
        return False
    if not row or not row[0]:
        return False
    fp = fingerprint(index_path)
    return bool(fp) and row[0] == fp


SCENE_PROMPT = """You group short memory notes into working scenes.

A scene is a project or a recurring working context: the notes someone would
want back together when they resume that work.

Rules:
- Use at most {max_scenes} scenes. If you need more, merge the closest ones.
- Every note must appear in exactly one scene.
- Use only the note ids given below. Never invent one.
- Answer with JSON only: {{"scenes": [{{"label": "...", "members": ["id", ...]}}]}}

Notes:
{notes}
"""


def cluster_llm(path_meta, llm_fn, max_scenes: int = 15) -> dict:
    """Let a model form scenes under a hard capacity cap.

    The cap is the borrowed idea: TencentDB Agent Memory's scene extractor puts
    the ceiling in front of the model and blocks new scenes near the limit, so
    capacity pressure forces merging instead of unbounded growth. When a reply
    exceeds the cap anyway, the two smallest scenes are merged here rather than
    dropped -- losing a note would silently shrink the corpus being measured.

    Fail-open: any parse failure yields {}, which the builder turns into "no
    scenes", which the recall path treats as baseline. A model that answers
    with prose must not take retrieval down with it.
    """
    import json as _json

    notes = "\n".join(f"- {p}: {(meta or {}).get('title', '')}"
                      for p, meta in sorted(path_meta.items()))
    prompt = SCENE_PROMPT.format(max_scenes=int(max_scenes), notes=notes)
    try:
        raw = llm_fn(prompt) or ""
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return {}
        scenes = (_json.loads(raw[start:end + 1]) or {}).get("scenes") or []
    except Exception:
        return {}

    known = set(path_meta)
    assigned: set = set()
    out: dict = {}
    for entry in scenes:
        label = str((entry or {}).get("label", "")).strip()
        members = [str(m) for m in (entry or {}).get("members", [])
                   if str(m) in known and str(m) not in assigned]
        if not label or not members:
            continue
        # A label the model repeats must not silently swallow the earlier group.
        while label in out:
            label += "'"
        out[label] = sorted(members)
        assigned.update(members)

    while len(out) > int(max_scenes) and len(out) > 1:
        smallest = sorted(out.items(), key=lambda kv: (len(kv[1]), kv[0]))[:2]
        (l1, m1), (l2, m2) = smallest
        del out[l1]
        del out[l2]
        out[f"{l1}+{l2}"] = sorted(m1 + m2)
    return out


def cluster_tags(path_meta, window_days: int = 90) -> dict:
    """Group memories by shared tag within a rolling time window.

    A memory can carry several tags, but a scene must be a PARTITION: a path in
    two scenes would let one query apply the prior twice and would make any
    recall change impossible to attribute. Each path therefore lands in exactly
    one scene, chosen by its RAREST tag -- the rarest tag carries the most
    information, while the most common one would collapse half the vault into a
    single scene that acts as a global floor change in disguise.

    Untagged memories are dropped, for the same reason cluster_community drops
    paths absent from the graph.

    ``path_meta``: {path: {"tags": [...], "created": "YYYY-MM-DD"}}.
    """
    def _parse(value):
        try:
            y, m, d = str(value)[:10].split("-")
            return date(int(y), int(m), int(d))
        except Exception:
            return None

    freq: dict = {}
    for meta in path_meta.values():
        for tag in (meta.get("tags") or []):
            freq[tag] = freq.get(tag, 0) + 1

    buckets: dict = {}
    for path, meta in sorted(path_meta.items()):
        tags = [t for t in (meta.get("tags") or []) if t]
        if not tags:
            continue
        tag = sorted(tags, key=lambda t: (freq.get(t, 0), t))[0]
        buckets.setdefault(tag, []).append((_parse(meta.get("created")), path))

    out: dict = {}
    for tag, items in buckets.items():
        dated = sorted((c, p) for c, p in items if c is not None)
        anchor = None
        label = None
        for created, path in dated:
            if anchor is None or (created - anchor).days > window_days:
                anchor = created
                label = f"{tag}@{created.isoformat()}"
            out.setdefault(label, []).append(path)
        for created, path in items:
            if created is None:
                out.setdefault(f"{tag}@undated", []).append(path)
    for label in out:
        out[label].sort()
    return out


def cluster_community(paths, graph_conn) -> dict:
    """Group memory paths by the community partition already in kb-graph.db.

    A source file can contribute several graph nodes, and those nodes need not
    share a community. The file is assigned to the community holding the most
    of its nodes, with a deterministic tie-break on the lowest community id --
    an arbitrary but stable choice beats a run-to-run coin flip in an
    experiment whose whole point is comparability.

    Paths with no node in the graph are DROPPED. Collecting them into one
    residual scene would create a single huge group that acts as a prior on
    everything, which is indistinguishable from lowering the floor globally.
    """
    wanted = {str(p).replace("\\", "/") for p in paths}
    if not wanted:
        return {}
    counts: dict = {}
    try:
        rows = graph_conn.execute(
            "SELECT source_file, community, count(*) FROM graph_nodes "
            "WHERE community IS NOT NULL GROUP BY source_file, community").fetchall()
    except Exception:
        return {}
    for src, comm, n in rows:
        key = str(src or "").replace("\\", "/")
        if key not in wanted:
            continue
        counts.setdefault(key, []).append((int(n), -int(comm), int(comm)))
    out: dict = {}
    for path, cands in counts.items():
        cands.sort(reverse=True)
        comm = cands[0][2]
        out.setdefault(f"community-{comm}", []).append(path)
    for label in out:
        out[label].sort()
    return out

# L2 Scene Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure whether a project-scoped scene tier (L2) between atomic
memories and curated wiki articles improves memory-layer recall, by building
three interchangeable clusterers and comparing them against an unmodified
baseline with the existing `kb-eval` harness.

**Architecture:** Scenes are derived rows in a new `kb-scene.db`, built off the
hot path from embeddings that already live in `kb-index.db`. They are never
vault markdown and are never returned as retrieval hits. At query time the best
scene acts as a prior: its members are admitted at a lower similarity floor
(`scene_floor`) and/or given a score bonus (`scene_boost`), added to — never
replacing — the baseline candidate set, so the feature switched off is provably
identical to baseline.

**Tech Stack:** Python 3 stdlib only (sqlite3, struct, math, json, argparse),
sqlite-vec through the existing `_kbindex` helpers, pytest.

Spec: `docs/superpowers/specs/2026-08-05-l2-scene-retrieval-design.md`
Backlog: TASK-134

## Global Constraints

- **Repo language is English.** Code comments, docstrings, commit messages, and
  every file under `docs/` are English. (Existing scripts have Dutch comments;
  do not translate them, but write new text in English.)
- **Vault root only via `_vaultpath.vault_root()`.** Never hardcode a path such
  as `Path.home() / "KennisBank"`. This is ADR-0002; a hardcoded vault path is
  treated as a regression.
- **Interpreter:** repo scripts and tests use `python3` / `python -m pytest`.
- **The gate is pytest:** `python -m pytest tests -q`. `unittest discover`
  misses the function-style tests in this repo and must not be used.
- **Fail-open everywhere.** Any failure in scene code returns the baseline
  result. A dead model, a missing database, or a corrupt row never blocks a
  prompt and never raises to the caller.
- **No new embedding calls.** Centroids are built from vectors already stored
  in `kb-index.db`. Query vectors are already computed on the hot path and are
  reused.
- **Underscore modules are libraries:** `_scenes.py` has no network access, no
  side effects at import, and is importable after `sys.path.insert`, exactly as
  `_memory.py` and `_kbindex.py`.
- **New retrieval knobs are resolved in `kb-retrieve.retrieve_params()`** and
  nowhere else, so `kb-eval` measures the same values the hook uses.

## File Structure

| File | Responsibility |
| --- | --- |
| `scripts/_scenes.py` (create) | Scene model, `kb-scene.db` schema, fingerprinting, vector (de)serialisation helpers, and the three clusterers behind one `cluster()` entry point. |
| `scripts/build-scene-index.py` (create) | Build CLI: read memory docs + vectors from `kb-index.db`, call a clusterer, write scenes and centroids. Off the hot path. |
| `scripts/scene-report.py` (create) | Diagnostics and the oracle ceiling. Read-only; runs before any retrieval measurement. |
| `scripts/scene-experiment.py` (create) | Experiment driver: runs the arms, writes raw JSON per arm, computes per-question flips. |
| `scripts/kb-recall.py` (modify) | The scene prior inside `recall_hits`. The only change to the read path. |
| `scripts/kb-retrieve.py` (modify) | Three knobs added to `retrieve_params()`. |
| `scripts/_settings.py` (modify) | `scene_retrieval` toggle, default `False`. |
| `tests/test_scenes.py` (create) | Schema, clusterers, fingerprint, and the parity test. |

---

### Task 1: Scene store — schema, fingerprint, vector helpers

**Files:**
- Create: `scripts/_scenes.py`
- Test: `tests/test_scenes.py`

**Interfaces:**
- Consumes: `_vaultpath.vault_root()`, `_kbindex.unit()`, `_kbindex._serialize()`
- Produces:
  - `scene_index_path() -> Path`
  - `connect(path=None) -> sqlite3.Connection`
  - `ensure_schema(conn) -> None`
  - `deserialize(blob) -> list[float]`
  - `serialize(vector) -> bytes`
  - `centroid(vectors) -> list[float]` (normalised mean)
  - `write_scenes(conn, clusterer, scenes) -> int` where `scenes` is
    `list[tuple[str, list[str], list[float]]]` = (label, member_paths, centroid)
  - `members_of(conn, scene_id) -> list[str]`
  - `best_scene(conn, query_vector, min_cos) -> tuple[str, float] | None`
  - `set_fingerprint(conn, fp) -> None`, `is_current(conn, index_path) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scenes.py
import os
import sqlite3
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _scenes  # noqa: E402


def test_roundtrip_scene_and_lookup(tmp_path):
    conn = sqlite3.connect(tmp_path / "kb-scene.db")
    _scenes.ensure_schema(conn)
    n = _scenes.write_scenes(conn, "community", [
        ("alpha", ["09-memory/a.md", "09-memory/b.md"], [1.0, 0.0]),
        ("beta", ["09-memory/c.md"], [0.0, 1.0]),
    ])
    assert n == 2
    hit = _scenes.best_scene(conn, [1.0, 0.0], min_cos=0.5)
    assert hit is not None
    scene_id, cos = hit
    assert cos > 0.99
    assert sorted(_scenes.members_of(conn, scene_id)) == [
        "09-memory/a.md", "09-memory/b.md"]


def test_best_scene_respects_threshold(tmp_path):
    conn = sqlite3.connect(tmp_path / "kb-scene.db")
    _scenes.ensure_schema(conn)
    _scenes.write_scenes(conn, "community", [("alpha", ["x.md"], [1.0, 0.0])])
    assert _scenes.best_scene(conn, [0.0, 1.0], min_cos=0.5) is None


def test_centroid_is_unit_length():
    c = _scenes.centroid([[3.0, 0.0], [0.0, 3.0]])
    assert abs(sum(x * x for x in c) - 1.0) < 1e-9


def test_centroid_of_empty_is_empty():
    assert _scenes.centroid([]) == []


def test_write_scenes_replaces_previous_run(tmp_path):
    conn = sqlite3.connect(tmp_path / "kb-scene.db")
    _scenes.ensure_schema(conn)
    _scenes.write_scenes(conn, "community", [("alpha", ["x.md"], [1.0, 0.0])])
    _scenes.write_scenes(conn, "community", [("beta", ["y.md"], [0.0, 1.0])])
    rows = conn.execute("SELECT label FROM scenes").fetchall()
    assert [r[0] for r in rows] == ["beta"]


def test_is_current_false_when_fingerprint_missing(tmp_path):
    conn = sqlite3.connect(tmp_path / "kb-scene.db")
    _scenes.ensure_schema(conn)
    index = tmp_path / "kb-index.db"
    index.write_bytes(b"x")
    assert _scenes.is_current(conn, index) is False
    _scenes.set_fingerprint(conn, _scenes.fingerprint(index))
    assert _scenes.is_current(conn, index) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named '_scenes'`

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""_scenes.py - the derived L2 scene layer (kb-scene.db).

A scene groups atomic memories that belong to the same project or working
context. Scenes are DERIVED: they are rebuilt from kb-index.db and kb-graph.db
and never written as vault markdown. Two reasons. A markdown scene would enter
the corpus, be indexed, show up in Obsidian, and could be counted as a correct
answer by the eval harness -- the exact circularity this experiment must avoid.
And a derived store can be thrown away and rebuilt, like kb-graph.db.

Pure stdlib library: no network, no embedding calls, no side effects at import.
Centroids are built from vectors that kb-index.db already holds.
"""
from __future__ import annotations

import math
import os
import sqlite3
import struct
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
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
    v = [float(x) for x in vector]
    return struct.pack("%sf" % len(v), *v)


def deserialize(blob) -> list:
    n = len(blob) // 4
    return list(struct.unpack("%sf" % n, blob))


def centroid(vectors) -> list:
    """Normalised mean of the member vectors. Empty input -> []."""
    rows = [list(v) for v in vectors if v]
    if not rows:
        return []
    dim = len(rows[0])
    acc = [0.0] * dim
    for v in rows:
        for i in range(dim):
            acc[i] += float(v[i])
    norm = math.sqrt(sum(x * x for x in acc))
    if norm == 0.0:
        return acc
    return [x / norm for x in acc]


def write_scenes(conn: sqlite3.Connection, clusterer: str, scenes) -> int:
    """Replace every scene for this clusterer with the given set.

    ``scenes``: iterable of (label, member_paths, centroid_vector).
    Returns the number of scenes written.
    """
    from datetime import date
    ensure_schema(conn)
    old = [r[0] for r in conn.execute("SELECT scene_id FROM scenes").fetchall()]
    for sid in old:
        conn.execute("DELETE FROM scene_members WHERE scene_id=?", (sid,))
        conn.execute("DELETE FROM scene_centroids WHERE scene_id=?", (sid,))
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

    The query vector is assumed unit length (the hot path normalises before
    searching); centroids are stored normalised, so the dot product IS the
    cosine. A few hundred centroids: a full scan is sub-millisecond and needs
    no index.
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
        vec = deserialize(blob)
        if len(vec) != len(q):
            continue
        cos = sum(a * b for a, b in zip(q, vec))
        if cos >= min_cos and (best is None or cos > best[1]):
            best = (sid, cos)
    return best


def fingerprint(index_path) -> str:
    """Cheap fingerprint of kb-index.db: mtime + size. Same pattern as
    _kbindex.graph_fingerprint."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/_scenes.py tests/test_scenes.py
git commit -m "feat(scenes): add the derived kb-scene.db store"
```

---

### Task 2: Community clusterer

**Files:**
- Modify: `scripts/_scenes.py` (append)
- Test: `tests/test_scenes.py` (append)

**Interfaces:**
- Consumes: `_kbindex.graph_connect()`, `graph_nodes(source_file, community)`
- Produces: `cluster_community(paths, graph_conn) -> dict[str, list[str]]`
  mapping label -> member paths. Paths not present in the graph are dropped
  (they form no scene rather than one giant "unknown" scene).

- [ ] **Step 1: Write the failing test**

```python
def _graph_db(tmp_path, rows):
    conn = sqlite3.connect(tmp_path / "kb-graph.db")
    conn.execute("CREATE TABLE graph_nodes (id TEXT PRIMARY KEY, label TEXT, "
                 "source_file TEXT, file_type TEXT, community INTEGER)")
    for i, (src, comm) in enumerate(rows):
        conn.execute("INSERT INTO graph_nodes VALUES (?,?,?,?,?)",
                     (f"n{i}", f"n{i}", src, "md", comm))
    conn.commit()
    return conn


def test_community_groups_by_partition(tmp_path):
    g = _graph_db(tmp_path, [("09-memory/a.md", 1), ("09-memory/b.md", 1),
                             ("09-memory/c.md", 2)])
    out = _scenes.cluster_community(
        ["09-memory/a.md", "09-memory/b.md", "09-memory/c.md"], g)
    groups = sorted(sorted(v) for v in out.values())
    assert groups == [["09-memory/a.md", "09-memory/b.md"], ["09-memory/c.md"]]


def test_community_drops_paths_absent_from_graph(tmp_path):
    g = _graph_db(tmp_path, [("09-memory/a.md", 1)])
    out = _scenes.cluster_community(["09-memory/a.md", "09-memory/zz.md"], g)
    assert [p for v in out.values() for p in v] == ["09-memory/a.md"]


def test_community_uses_majority_when_file_spans_communities(tmp_path):
    g = _graph_db(tmp_path, [("09-memory/a.md", 1), ("09-memory/a.md", 1),
                             ("09-memory/a.md", 7)])
    out = _scenes.cluster_community(["09-memory/a.md"], g)
    assert list(out.keys()) == ["community-1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: FAIL with `AttributeError: module '_scenes' has no attribute 'cluster_community'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: PASS, 9 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/_scenes.py tests/test_scenes.py
git commit -m "feat(scenes): group memories by the existing graph community partition"
```

---

### Task 3: Build CLI

**Files:**
- Create: `scripts/build-scene-index.py`
- Test: `tests/test_scenes.py` (append)

**Interfaces:**
- Consumes: `_kbindex.index_path()`, `_scenes.cluster_community()`,
  `_scenes.write_scenes()`, `_scenes.centroid()`
- Produces: `build(clusterer, index_conn, graph_conn, scene_conn) -> dict`
  returning `{"scenes": int, "members": int, "skipped": int}`

- [ ] **Step 1: Write the failing test**

```python
import importlib.util


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_scene_index", str(SCRIPTS / "build-scene-index.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _index_db(tmp_path, docs):
    """docs: list of (path, layer, status, vector)."""
    conn = sqlite3.connect(tmp_path / "kb-index.db")
    conn.execute("CREATE TABLE docs (doc_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                 "path TEXT UNIQUE, layer TEXT, status TEXT, hash TEXT, "
                 "title TEXT, created TEXT)")
    conn.execute("CREATE TABLE vec_docs (doc_id INTEGER PRIMARY KEY, embedding BLOB)")
    for path, layer, status, vec in docs:
        cur = conn.execute("INSERT INTO docs(path, layer, status) VALUES (?,?,?)",
                           (path, layer, status))
        conn.execute("INSERT INTO vec_docs(doc_id, embedding) VALUES (?,?)",
                     (cur.lastrowid, _scenes.serialize(vec)))
    conn.commit()
    return conn


def test_build_writes_scenes_with_centroids(tmp_path):
    builder = _load_builder()
    idx = _index_db(tmp_path, [
        ("09-memory/a.md", "memory", "current", [1.0, 0.0]),
        ("09-memory/b.md", "memory", "current", [0.0, 1.0]),
        ("02-wiki/w.md", "wiki", "current", [1.0, 1.0]),
    ])
    g = _graph_db(tmp_path, [("09-memory/a.md", 1), ("09-memory/b.md", 1)])
    scene = sqlite3.connect(tmp_path / "kb-scene.db")
    stats = builder.build("community", idx, g, scene)
    assert stats["scenes"] == 1
    assert stats["members"] == 2
    row = scene.execute("SELECT vector FROM scene_centroids").fetchone()
    vec = _scenes.deserialize(row[0])
    assert abs(vec[0] - vec[1]) < 1e-6      # mean of the two unit axes


def test_build_ignores_wiki_and_non_current(tmp_path):
    builder = _load_builder()
    idx = _index_db(tmp_path, [
        ("09-memory/a.md", "memory", "current", [1.0, 0.0]),
        ("09-memory/old.md", "memory", "superseded", [1.0, 0.0]),
        ("02-wiki/w.md", "wiki", "current", [1.0, 0.0]),
    ])
    g = _graph_db(tmp_path, [("09-memory/a.md", 1), ("09-memory/old.md", 1),
                             ("02-wiki/w.md", 1)])
    scene = sqlite3.connect(tmp_path / "kb-scene.db")
    stats = builder.build("community", idx, g, scene)
    assert stats["members"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: FAIL with `FileNotFoundError` for `build-scene-index.py`

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""build-scene-index.py - build the derived L2 scene layer.

Reads current memory documents and their stored embeddings from kb-index.db,
groups them with the selected clusterer, and writes scenes plus normalised
centroids to kb-scene.db. Off the hot path; issues NO embedding calls.

Usage:
    python3 build-scene-index.py [--clusterer community|tags|llm] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kbindex  # noqa: E402
import _scenes  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


def memory_vectors(index_conn) -> dict:
    """{path: vector} for every current memory doc in the index."""
    out = {}
    rows = index_conn.execute(
        "SELECT d.path, v.embedding FROM docs d JOIN vec_docs v ON v.doc_id = d.doc_id "
        "WHERE d.layer='memory' AND d.status='current'").fetchall()
    for path, blob in rows:
        try:
            out[str(path).replace("\\", "/")] = _scenes.deserialize(blob)
        except Exception:
            continue
    return out


def build(clusterer: str, index_conn, graph_conn, scene_conn) -> dict:
    """Cluster the memory layer and write scenes + centroids. Returns stats."""
    vectors = memory_vectors(index_conn)
    if clusterer == "community":
        groups = _scenes.cluster_community(list(vectors), graph_conn)
    else:
        raise SystemExit(f"unknown clusterer: {clusterer}")
    scenes = []
    members = 0
    skipped = 0
    for label, paths in sorted(groups.items()):
        vecs = [vectors[p] for p in paths if p in vectors]
        if not vecs:
            skipped += 1
            continue
        scenes.append((label, paths, _scenes.centroid(vecs)))
        members += len(paths)
    n = _scenes.write_scenes(scene_conn, clusterer, scenes)
    return {"scenes": n, "members": members, "skipped": skipped}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="build kb-scene.db")
    ap.add_argument("--clusterer", default="community", choices=_scenes.CLUSTERERS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    index_path = _kbindex.index_path()
    index_conn = _kbindex.connect(index_path)
    graph_conn = _kbindex.graph_connect()
    scene_conn = _scenes.connect()
    stats = build(args.clusterer, index_conn, graph_conn, scene_conn)
    _scenes.set_fingerprint(scene_conn, _scenes.fingerprint(index_path))
    stats["clusterer"] = args.clusterer
    if args.json:
        print(json.dumps(stats, ensure_ascii=False))
    else:
        print(f"scenes: {stats['scenes']}  members: {stats['members']}  "
              f"clusterer: {args.clusterer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: PASS, 11 tests

- [ ] **Step 5: Build against the real vault and record the numbers**

Run: `python3 scripts/build-scene-index.py --clusterer community --json`
Expected: JSON on stdout with a scene count. Note it — Task 6 turns it into
diagnostics.

- [ ] **Step 6: Commit**

```bash
git add scripts/build-scene-index.py tests/test_scenes.py
git commit -m "feat(scenes): build scene centroids from indexed memory vectors"
```

---

### Task 4: Knobs and toggle

**Files:**
- Modify: `scripts/kb-retrieve.py` (`retrieve_params`, around line 190)
- Modify: `scripts/_settings.py` (`DEFAULTS`, around line 36)
- Test: `tests/test_scenes.py` (append)

**Interfaces:**
- Produces: `retrieve_params(cfg)` gains three keys: `scene_clusterer` (str),
  `scene_floor` (float), `scene_boost` (float). `_settings.DEFAULTS` gains
  `scene_retrieval: False`.

Environment overrides follow the existing `_num` convention:
`KB_SCENE_FLOOR`, `KB_SCENE_BOOST`, and `KB_SCENE_CLUSTERER` (a string, read
directly from the environment because `_num` coerces to numbers).

- [ ] **Step 1: Write the failing test**

```python
def _load_retrieve():
    spec = importlib.util.spec_from_file_location(
        "kb_retrieve", str(SCRIPTS / "kb-retrieve.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scene_knobs_have_conservative_defaults():
    kr = _load_retrieve()
    p = kr.retrieve_params({})
    assert p["scene_floor"] == 0.35
    assert p["scene_boost"] == 0.0
    assert p["scene_clusterer"] == "community"


def test_scene_knobs_read_env(monkeypatch):
    monkeypatch.setenv("KB_SCENE_FLOOR", "0.4")
    monkeypatch.setenv("KB_SCENE_BOOST", "0.05")
    monkeypatch.setenv("KB_SCENE_CLUSTERER", "tags")
    kr = _load_retrieve()
    p = kr.retrieve_params({})
    assert p["scene_floor"] == 0.4
    assert p["scene_boost"] == 0.05
    assert p["scene_clusterer"] == "tags"


def test_scene_retrieval_toggle_defaults_off():
    import _settings
    assert _settings.DEFAULTS["scene_retrieval"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: FAIL with `KeyError: 'scene_floor'`

- [ ] **Step 3: Write minimal implementation**

In `scripts/kb-retrieve.py`, extend the returned dict in `retrieve_params`:

```python
    return {
        "top_n": int(_num("KB_RETRIEVE_TOP_N", cfg, "retrieve_top_n", 3)),
        "min_cos": _num("KB_RETRIEVE_THRESHOLD", cfg, "retrieve_threshold", 0.50),
        "expand": bool(int(_num("KB_RETRIEVE_EXPAND", cfg, "retrieve_expand", 1))),
        # L2 scene prior (TASK-134). Members of the winning scene are admitted
        # at scene_floor instead of the memory floor, and may receive
        # scene_boost on their score. Both are inert until the scene_retrieval
        # toggle is on; the defaults are the neutral arm of the experiment.
        "scene_clusterer": os.environ.get("KB_SCENE_CLUSTERER")
                           or str(cfg.get("scene_clusterer", "community")),
        "scene_floor": _num("KB_SCENE_FLOOR", cfg, "scene_floor", 0.35),
        "scene_boost": _num("KB_SCENE_BOOST", cfg, "scene_boost", 0.0),
    }
```

In `scripts/_settings.py`, add to `DEFAULTS` before the closing brace:

```python
    # L2 scene prior (TASK-134): members of the winning scene are admitted at a
    # lower similarity floor. Experimental and unproven -> opt-in, default off.
    # It only ships if the pre-registered winner rule in the design spec is met.
    "scene_retrieval": False,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scenes.py tests/test_settings.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/kb-retrieve.py scripts/_settings.py tests/test_scenes.py
git commit -m "feat(scenes): add scene knobs to retrieve_params and an opt-in toggle"
```

---

### Task 5: The scene prior in recall — and the parity test

This is the task the whole experiment rests on. If `off` is not byte-identical
to baseline, every later measurement is meaningless.

**Files:**
- Modify: `scripts/kb-recall.py` (`recall_hits`, lines 198-264)
- Test: `tests/test_scenes.py` (append)

**Interfaces:**
- Consumes: `_scenes.best_scene()`, `_scenes.members_of()`, `_scenes.is_current()`
- Produces: `recall_hits(..., scene_prior=None)` where `scene_prior` is
  `None` (off, baseline behaviour) or a dict
  `{"floor": float, "boost": float}`. Hits gain a `scene: True` key when the
  prior admitted them.

**Design of the change:** the baseline candidate set is computed exactly as
before. Scene members are then fetched with a SECOND search at the lower floor
and merged in — additively, never replacing. The baseline result is therefore a
strict subset of the treatment result, which is what makes the parity claim
provable rather than hopeful.

- [ ] **Step 1: Write the failing parity test**

```python
def test_recall_hits_without_prior_is_unchanged(monkeypatch):
    """Parity: scene_prior=None must not alter the baseline code path.

    The gate for the whole experiment. If this fails, something other than
    clustering changed and no later number means anything.
    """
    kb = _load_recall()
    calls = []
    original = kb._kbindex.search

    def spy(conn, **kw):
        calls.append(kw)
        return original(conn, **kw)

    monkeypatch.setattr(kb._kbindex, "search", spy)
    kb.recall_hits([0.1] * 8, query_text="x", k=3, layers=("memory",),
                   scene_prior=None)
    assert len(calls) == 1, "scene_prior=None must issue exactly one search"
    assert "min_cos" in calls[0]


def test_scene_prior_admits_member_below_floor():
    kb = _load_recall()
    rows_primary = [{"path": "09-memory/a.md", "layer": "memory", "score": 0.8,
                     "cos": 0.8, "title": "", "created": "", "fts": False}]
    rows_wide = rows_primary + [
        {"path": "09-memory/b.md", "layer": "memory", "score": 0.38,
         "cos": 0.38, "title": "", "created": "", "fts": False},
        {"path": "09-memory/z.md", "layer": "memory", "score": 0.37,
         "cos": 0.37, "title": "", "created": "", "fts": False}]
    merged = kb._merge_scene_members(
        rows_primary, rows_wide, members={"09-memory/b.md"}, boost=0.05)
    paths = [r["path"] for r in merged]
    assert paths == ["09-memory/a.md", "09-memory/b.md"]
    assert merged[1]["scene"] is True
    assert abs(merged[1]["score"] - 0.43) < 1e-9


def test_scene_prior_never_reorders_primary_hits():
    kb = _load_recall()
    rows_primary = [{"path": "09-memory/a.md", "layer": "memory", "score": 0.8,
                     "cos": 0.8, "title": "", "created": "", "fts": False}]
    rows_wide = rows_primary + [
        {"path": "09-memory/b.md", "layer": "memory", "score": 0.39,
         "cos": 0.39, "title": "", "created": "", "fts": False}]
    merged = kb._merge_scene_members(rows_primary, rows_wide,
                                     members={"09-memory/a.md"}, boost=0.5)
    assert merged[0]["path"] == "09-memory/a.md"
    assert merged[0]["score"] == 0.8, "a primary hit is never re-scored"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: FAIL with `TypeError: recall_hits() got an unexpected keyword argument 'scene_prior'`

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/kb-recall.py`, above `recall_hits`:

```python
def _merge_scene_members(rows_primary, rows_wide, members, boost: float) -> list:
    """Add scene members from the widened search to the baseline rows.

    Additive only: a row already in rows_primary keeps its position and its
    score untouched. That is what makes the baseline a strict subset of the
    treatment, and what the parity test proves.

    The boost applies ONLY to newly admitted members. Re-scoring a primary hit
    would let the prior reorder results it was never meant to touch, and would
    make a recall@1 regression impossible to attribute.
    """
    seen = {r.get("path") for r in rows_primary}
    out = list(rows_primary)
    for r in rows_wide:
        path = r.get("path")
        if path in seen or path not in members:
            continue
        extra = dict(r)
        extra["score"] = float(extra.get("score", 0.0)) + float(boost)
        extra["scene"] = True
        out.append(extra)
        seen.add(path)
    return out


def _scene_members_for(query_vector, prior) -> set:
    """Member paths of the best-matching scene. Fail-open -> empty set.

    Any failure -- no database, a stale one, a corrupt row -- yields an empty
    set, and an empty set makes _merge_scene_members a no-op. There is no
    error path in which the caller behaves differently from baseline.
    """
    try:
        import _scenes
        path = _scenes.scene_index_path()
        if not path.exists():
            return set()
        conn = _scenes.connect(path)
        try:
            if not _scenes.is_current(conn, _kbindex.index_path()):
                return set()
            hit = _scenes.best_scene(conn, query_vector,
                                     min_cos=float(prior.get("floor", 0.35)))
            if not hit:
                return set()
            return set(_scenes.members_of(conn, hit[0]))
        finally:
            conn.close()
    except Exception:
        return set()
```

Then in `recall_hits`, change the signature and insert the widened search
directly after the existing `rows = _kbindex.search(...)` call:

```python
def recall_hits(query_vector, query_text: str = "", k: int = 3,
                layers=("wiki", "memory"), expand: bool = False,
                min_cos: float = 0.0, scene_prior=None) -> list:
```

```python
        rows = _kbindex.search(conn, query_vector=query_vector, query_text=query_text,
                               k=k, layers=tuple(layers), statuses=("current",),
                               min_cos=min_cos)
        # L2 scene prior (TASK-134). Off by default: scene_prior=None issues no
        # second query and leaves `rows` exactly as the baseline produced them.
        if scene_prior:
            members = _scene_members_for(query_vector, scene_prior)
            if members:
                wide = _kbindex.search(
                    conn, query_vector=query_vector, query_text=query_text,
                    k=k * 4, layers=tuple(layers), statuses=("current",),
                    min_cos=float(scene_prior.get("floor", 0.35)))
                rows = _merge_scene_members(
                    rows, wide, members, float(scene_prior.get("boost", 0.0)))
```

Then extend `memory_hits` to pass it through:

```python
def memory_hits(query_vector, query_text: str = "", k: int = 3,
                min_cos: float = MEMORY_MIN_COS, scene_prior=None) -> list:
    """Thin wrapper: the memory layer only (backward compatible)."""
    return recall_hits(query_vector, query_text=query_text, k=k, layers=("memory",),
                       min_cos=min_cos, scene_prior=scene_prior)
```

Note: the final `out = out[:k]` cut already happens in the caller via `k`;
after merging, truncate to `k` after reranking by adding `out = out[:k]`
immediately before the `if expand and out:` block, so an admitted member can
never inflate the block size beyond the configured `top_n`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: PASS

- [ ] **Step 5: Prove parity against the pinned baseline**

Run both, on the same vault, and diff:

```bash
python3 scripts/kb-eval.py --set <scratch>/mem-eval-dev.json --layer memory --json > /tmp/arm-off.json
diff <(python3 -c "import json;print(json.dumps(json.load(open('/tmp/arm-off.json'))['recall'],sort_keys=True))") \
     <(python3 -c "import json;print(json.dumps(json.load(open('<scratch>/baseline-dev.json'))['recall'],sort_keys=True))")
```

Expected: no output. Any difference stops the experiment.

- [ ] **Step 6: Commit**

```bash
git add scripts/kb-recall.py tests/test_scenes.py
git commit -m "feat(scenes): admit scene members below the memory floor, additively"
```

---

### Task 6: Diagnostics and the oracle ceiling

The cheap answer to "can this ever work", computed without running retrieval.

**Files:**
- Create: `scripts/scene-report.py`
- Test: `tests/test_scenes.py` (append)

**Interfaces:**
- Produces:
  - `diagnostics(scene_conn, total_memories) -> dict` with keys `scenes`,
    `median_size`, `p95_size`, `largest`, `coverage`, `singletons`
  - `oracle_ceiling(scene_conn, questions, best_hit_fn) -> dict` with keys
    `n`, `same_scene`, `ceiling`

- [ ] **Step 1: Write the failing test**

```python
def _load_report():
    spec = importlib.util.spec_from_file_location(
        "scene_report", str(SCRIPTS / "scene-report.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_diagnostics_reports_shape(tmp_path):
    rep = _load_report()
    conn = sqlite3.connect(tmp_path / "kb-scene.db")
    _scenes.ensure_schema(conn)
    _scenes.write_scenes(conn, "community", [
        ("a", ["1.md", "2.md", "3.md"], [1.0, 0.0]),
        ("b", ["4.md"], [0.0, 1.0]),
    ])
    d = rep.diagnostics(conn, total_memories=8)
    assert d["scenes"] == 2
    assert d["largest"] == 3
    assert d["singletons"] == 1
    assert abs(d["coverage"] - 0.5) < 1e-9


def test_oracle_ceiling_counts_shared_scenes(tmp_path):
    rep = _load_report()
    conn = sqlite3.connect(tmp_path / "kb-scene.db")
    _scenes.ensure_schema(conn)
    _scenes.write_scenes(conn, "community", [("a", ["gold.md", "top.md"], [1.0, 0.0])])
    questions = [{"q": "x", "expect": ["gold"]}, {"q": "y", "expect": ["absent"]}]
    out = rep.oracle_ceiling(conn, questions, best_hit_fn=lambda q: "top.md")
    assert out["n"] == 2
    assert out["same_scene"] == 1
    assert abs(out["ceiling"] - 0.5) < 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: FAIL, `scene-report.py` not found

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""scene-report.py - diagnostics and the oracle ceiling for the L2 scene layer.

Two read-only measurements that run BEFORE any retrieval experiment:

  diagnostics    -- the shape of the clustering. A clusterer that produces one
                    900-member scene is hopeless by construction, and that is
                    visible here without spending a retrieval run.
  oracle_ceiling -- for each eval question, does the gold memory share a scene
                    with the strongest candidate? That is the upper bound on
                    what the prior can ever deliver. A ceiling of 3% means the
                    expensive run is unnecessary.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scenes  # noqa: E402


def diagnostics(scene_conn, total_memories: int) -> dict:
    sizes = [r[0] for r in scene_conn.execute("SELECT size FROM scenes").fetchall()]
    covered = scene_conn.execute(
        "SELECT count(DISTINCT path) FROM scene_members").fetchone()[0]
    if not sizes:
        return {"scenes": 0, "median_size": 0, "p95_size": 0, "largest": 0,
                "coverage": 0.0, "singletons": 0}
    ordered = sorted(sizes)
    p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
    return {
        "scenes": len(sizes),
        "median_size": statistics.median(ordered),
        "p95_size": p95,
        "largest": ordered[-1],
        "coverage": (covered / total_memories) if total_memories else 0.0,
        "singletons": sum(1 for s in sizes if s == 1),
    }


def scene_of(scene_conn, path: str):
    row = scene_conn.execute(
        "SELECT scene_id FROM scene_members WHERE path=?", (path,)).fetchone()
    return row[0] if row else None


def oracle_ceiling(scene_conn, questions, best_hit_fn) -> dict:
    """Share of questions whose gold memory shares a scene with the top hit.

    ``best_hit_fn(question) -> path or None`` supplies the strongest candidate;
    the caller decides whether that comes from a live search or a cached run.
    Matching is on the file stem, the same key the eval sets use in ``expect``.
    """
    by_stem = {}
    for path, in scene_conn.execute("SELECT path FROM scene_members"):
        by_stem[Path(path).stem] = path
    same = 0
    for item in questions:
        top = best_hit_fn(item)
        if not top:
            continue
        top_scene = scene_of(scene_conn, top)
        if top_scene is None:
            continue
        for stem in item.get("expect", []):
            gold = by_stem.get(stem)
            if gold and scene_of(scene_conn, gold) == top_scene:
                same += 1
                break
    n = len(questions)
    return {"n": n, "same_scene": same, "ceiling": (same / n) if n else 0.0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="scene diagnostics")
    ap.add_argument("--total", type=int, required=True,
                    help="number of current memory documents")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    conn = _scenes.connect()
    d = diagnostics(conn, args.total)
    print(json.dumps(d, ensure_ascii=False) if args.json else d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: PASS

- [ ] **Step 5: Run diagnostics and the ceiling for `community`, and decide**

Run `scene-report.py --total <n> --json` and compute the ceiling on the dev
split. **Record both numbers in the report before running any arm.** If the
ceiling is below the +0.02 winner threshold, say so and do not spend the
retrieval run on this clusterer.

- [ ] **Step 6: Commit**

```bash
git add scripts/scene-report.py tests/test_scenes.py
git commit -m "feat(scenes): report cluster shape and the oracle recall ceiling"
```

---

### Task 7: Tags clusterer

**Files:**
- Modify: `scripts/_scenes.py` (append), `scripts/build-scene-index.py`
- Test: `tests/test_scenes.py` (append)

**Interfaces:**
- Produces: `cluster_tags(path_meta, window_days=90) -> dict[str, list[str]]`
  where `path_meta` is `{path: {"tags": [...], "created": "YYYY-MM-DD"}}`

- [ ] **Step 1: Write the failing test**

```python
def test_tags_groups_by_shared_tag_within_window():
    meta = {
        "a.md": {"tags": ["otgw"], "created": "2026-01-01"},
        "b.md": {"tags": ["otgw"], "created": "2026-02-01"},
        "c.md": {"tags": ["otgw"], "created": "2025-01-01"},
    }
    out = _scenes.cluster_tags(meta, window_days=90)
    groups = sorted(sorted(v) for v in out.values())
    assert ["a.md", "b.md"] in groups
    assert ["c.md"] in groups


def test_tags_assigns_each_path_once():
    meta = {"a.md": {"tags": ["x", "y"], "created": "2026-01-01"},
            "b.md": {"tags": ["y"], "created": "2026-01-02"}}
    out = _scenes.cluster_tags(meta, window_days=90)
    assigned = [p for v in out.values() for p in v]
    assert sorted(assigned) == ["a.md", "b.md"]
    assert len(assigned) == len(set(assigned)), "no path in two scenes"


def test_tags_drops_untagged_paths():
    meta = {"a.md": {"tags": [], "created": "2026-01-01"}}
    assert _scenes.cluster_tags(meta, window_days=90) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: FAIL, `cluster_tags` not defined

- [ ] **Step 3: Write minimal implementation**

```python
def cluster_tags(path_meta, window_days: int = 90) -> dict:
    """Group memories by shared tag within a rolling time window.

    A memory can carry several tags, but a scene must be a partition: a path in
    two scenes would let one query apply the prior twice and would make a
    recall change impossible to attribute. Each path is therefore assigned to
    exactly one scene, chosen by its RAREST tag -- the rarest tag carries the
    most information, and using the most common one would collapse half the
    vault into a single scene.

    Untagged memories are dropped, for the same reason cluster_community drops
    paths absent from the graph: a residual catch-all scene is a global floor
    change in disguise.
    """
    from datetime import date

    def _parse(d):
        try:
            y, m, dd = str(d)[:10].split("-")
            return date(int(y), int(m), int(dd))
        except Exception:
            return None

    freq: dict = {}
    for meta in path_meta.values():
        for t in meta.get("tags") or []:
            freq[t] = freq.get(t, 0) + 1

    buckets: dict = {}
    for path, meta in sorted(path_meta.items()):
        tags = [t for t in (meta.get("tags") or []) if t]
        if not tags:
            continue
        tag = sorted(tags, key=lambda t: (freq.get(t, 0), t))[0]
        created = _parse(meta.get("created"))
        buckets.setdefault(tag, []).append((created, path))

    out: dict = {}
    for tag, items in buckets.items():
        dated = sorted((c, p) for c, p in items if c is not None)
        undated = [p for c, p in items if c is None]
        window = None
        anchor = None
        for created, path in dated:
            if anchor is None or (created - anchor).days > window_days:
                anchor = created
                window = f"{tag}@{created.isoformat()}"
            out.setdefault(window, []).append(path)
        for path in undated:
            out.setdefault(f"{tag}@undated", []).append(path)
    for label in out:
        out[label].sort()
    return out
```

In `build-scene-index.py`, add a metadata reader and wire the branch:

```python
def memory_meta(paths) -> dict:
    """{path: {"tags": [...], "created": "..."}} read from the frontmatter."""
    from _frontmatter import parse_frontmatter
    out = {}
    root = vault_root()
    for p in paths:
        try:
            text = (root / p).read_text(encoding="utf-8", errors="replace")
            fm, _ = parse_frontmatter(text)
            tags = fm.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]
            out[p] = {"tags": list(tags), "created": str(fm.get("created", ""))}
        except Exception:
            out[p] = {"tags": [], "created": ""}
    return out
```

```python
    if clusterer == "community":
        groups = _scenes.cluster_community(list(vectors), graph_conn)
    elif clusterer == "tags":
        groups = _scenes.cluster_tags(memory_meta(list(vectors)))
    else:
        raise SystemExit(f"unknown clusterer: {clusterer}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: PASS

- [ ] **Step 5: Build, diagnose, and record**

```bash
python3 scripts/build-scene-index.py --clusterer tags --json
python3 scripts/scene-report.py --total <n> --json
```

- [ ] **Step 6: Commit**

```bash
git add scripts/_scenes.py scripts/build-scene-index.py tests/test_scenes.py
git commit -m "feat(scenes): add the tag-and-time-window clusterer"
```

---

### Task 8: LLM clusterer with a capacity cap

Mirrors their `scene-extractor.ts`, where a hard `max_scenes` ceiling forces
merging instead of unlimited growth.

**Files:**
- Modify: `scripts/_scenes.py` (append), `scripts/build-scene-index.py`
- Test: `tests/test_scenes.py` (append)

**Interfaces:**
- Consumes: `_llm.complete(prompt)` (the existing local-LLM wrapper)
- Produces: `cluster_llm(path_meta, llm_fn, max_scenes=15) -> dict[str, list[str]]`
  `llm_fn(prompt: str) -> str` is injected, so the test never needs a model.

- [ ] **Step 1: Write the failing test**

```python
def test_llm_clusterer_parses_assignment():
    meta = {"a.md": {"title": "OTGW flash"}, "b.md": {"title": "OTGW wifi"}}
    reply = '{"scenes": [{"label": "otgw", "members": ["a.md", "b.md"]}]}'
    out = _scenes.cluster_llm(meta, llm_fn=lambda p: reply, max_scenes=15)
    assert out == {"otgw": ["a.md", "b.md"]}


def test_llm_clusterer_enforces_cap():
    meta = {f"{i}.md": {"title": str(i)} for i in range(4)}
    reply = json.dumps({"scenes": [
        {"label": f"s{i}", "members": [f"{i}.md"]} for i in range(4)]})
    out = _scenes.cluster_llm(meta, llm_fn=lambda p: reply, max_scenes=2)
    assert len(out) <= 2
    assert sorted(p for v in out.values() for p in v) == \
        ["0.md", "1.md", "2.md", "3.md"], "capping merges, never drops"


def test_llm_clusterer_fails_open_on_garbage():
    out = _scenes.cluster_llm({"a.md": {"title": "x"}},
                              llm_fn=lambda p: "not json", max_scenes=15)
    assert out == {}


def test_llm_clusterer_ignores_hallucinated_paths():
    out = _scenes.cluster_llm(
        {"a.md": {"title": "x"}},
        llm_fn=lambda p: '{"scenes":[{"label":"s","members":["a.md","ghost.md"]}]}',
        max_scenes=15)
    assert out == {"s": ["a.md"]}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: FAIL, `cluster_llm` not defined

- [ ] **Step 3: Write minimal implementation**

```python
SCENE_PROMPT = """You group short memory notes into working scenes.

A scene is a project or recurring working context: the notes someone would want
back together when they resume that work.

Rules:
- Use at most {max_scenes} scenes. If you need more, merge the closest ones.
- Every note must appear in exactly one scene.
- Use only the note ids given below. Never invent one.
- Answer with JSON only: {{"scenes": [{{"label": "...", "members": ["id", ...]}}]}}

Notes:
{notes}
"""


def cluster_llm(path_meta, llm_fn, max_scenes: int = 15) -> dict:
    """Let a local model form scenes under a hard capacity cap.

    The cap is the interesting part, borrowed from TencentDB Agent Memory's
    scene extractor: the model is told the ceiling and must merge to stay under
    it, so scene count cannot grow without bound. When the reply exceeds the cap
    anyway, the smallest scenes are merged here rather than dropped -- losing a
    note would silently shrink the corpus the experiment measures.

    Fail-open: any parse failure yields {}, which the builder turns into "no
    scenes", which the recall path treats as baseline.
    """
    import json as _json

    notes = "\n".join(f"- {p}: {(m or {}).get('title', '')}"
                      for p, m in sorted(path_meta.items()))
    prompt = SCENE_PROMPT.format(max_scenes=int(max_scenes), notes=notes)
    try:
        raw = llm_fn(prompt) or ""
        start, end = raw.find("{"), raw.rfind("}")
        data = _json.loads(raw[start:end + 1]) if start >= 0 < end else {}
        scenes = data.get("scenes") or []
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
        out[label] = sorted(members)
        assigned.update(members)

    while len(out) > int(max_scenes):
        smallest = sorted(out.items(), key=lambda kv: (len(kv[1]), kv[0]))[:2]
        (l1, m1), (l2, m2) = smallest
        del out[l1]
        del out[l2]
        out[f"{l1}+{l2}"] = sorted(m1 + m2)
    return out
```

In `build-scene-index.py`, wire the third branch:

```python
    elif clusterer == "llm":
        import _llm
        meta = memory_meta(list(vectors))
        for path in meta:
            meta[path]["title"] = Path(path).stem
        groups = _scenes.cluster_llm(meta, llm_fn=_llm.complete, max_scenes=15)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/_scenes.py scripts/build-scene-index.py tests/test_scenes.py
git commit -m "feat(scenes): add the LLM clusterer with a hard capacity cap"
```

---

### Task 9: Experiment driver and report

**Files:**
- Create: `scripts/scene-experiment.py`
- Create: `docs/research/l2-scene-retrieval-2026-08.md`

**Interfaces:**
- Consumes: `kb-eval.py --json`, `build-scene-index.py`, `scene-report.py`
- Produces: one JSON file per arm plus `flips(baseline_json, arm_json) -> dict`
  with `gained` and `lost` question lists.

- [ ] **Step 1: Write the failing test**

```python
def test_flips_reports_both_directions():
    exp = _load_experiment()
    base = {"per_question": [{"q": "a", "hit": True}, {"q": "b", "hit": False}]}
    arm = {"per_question": [{"q": "a", "hit": False}, {"q": "b", "hit": True}]}
    out = exp.flips(base, arm)
    assert [x["q"] for x in out["gained"]] == ["b"]
    assert [x["q"] for x in out["lost"]] == ["a"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenes.py -q`
Expected: FAIL, `scene-experiment.py` not found

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""scene-experiment.py - run the L2 scene arms and diff them against baseline.

Each arm is (clusterer, floor, boost). The driver rebuilds kb-scene.db for the
clusterer, runs kb-eval with the arm's knobs in the environment, and stores the
raw JSON. Nothing here decides a winner: the winner rule lives in the design
spec and is applied by a human reading the tables.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def flips(baseline: dict, arm: dict) -> dict:
    """Questions that changed outcome, both directions.

    An average hides displacement: an arm can gain five answers and lose four
    and still look like a win. Both lists go in the report.
    """
    base = {q["q"]: bool(q.get("hit")) for q in baseline.get("per_question", [])}
    gained, lost = [], []
    for q in arm.get("per_question", []):
        was = base.get(q["q"])
        now = bool(q.get("hit"))
        if was is None or was == now:
            continue
        (gained if now else lost).append(q)
    return {"gained": gained, "lost": lost}


def run_arm(clusterer: str, floor: float, boost: float, set_path: str,
            out_path: str) -> dict:
    subprocess.run([sys.executable, str(SCRIPTS / "build-scene-index.py"),
                    "--clusterer", clusterer], check=True)
    env = dict(os.environ)
    env["KB_SCENE_CLUSTERER"] = clusterer
    env["KB_SCENE_FLOOR"] = str(floor)
    env["KB_SCENE_BOOST"] = str(boost)
    env["KB_SCENE_RETRIEVAL"] = "1"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "kb-eval.py"), "--set", set_path,
         "--layer", "memory", "--latency", "--json"],
        env=env, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="run one scene arm")
    ap.add_argument("--clusterer", required=True)
    ap.add_argument("--floor", type=float, default=0.35)
    ap.add_argument("--boost", type=float, default=0.0)
    ap.add_argument("--set", dest="set_path", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    data = run_arm(args.clusterer, args.floor, args.boost, args.set_path, args.out)
    print(json.dumps(data.get("recall", {}), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: `kb-eval.py --json` must include a `per_question` list with `q` and `hit`
for `flips` to work. If it does not, add it in this task — it is a reporting
field, not a behaviour change, and the parity test in Task 5 still holds
because it compares the `recall` block.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests -q`
Expected: PASS, whole suite green

- [ ] **Step 5: Run stage 1 — all three clusterers, neutral prior, dev split**

```bash
for c in community tags llm; do
  python3 scripts/scene-experiment.py --clusterer $c --floor 0.35 --boost 0.0 \
    --set <scratch>/mem-eval-dev.json --out <scratch>/arm-$c.json
done
```

Run `llm` three times (`--out arm-llm-1.json` … `-3`) to expose its variance.

- [ ] **Step 6: Run stage 2 — prior sweep on the two best clusterers**

Six runs: `floor-only` (0.35 / 0.0), `boost-only` (0.45 / 0.05), `both`
(0.35 / 0.05), for each of the two winners from stage 1.

- [ ] **Step 7: Apply the winner rule and write the report**

Winner rule, from the design spec, all four required on dev:
recall@5 ≥ +0.02; recall@1 not lower; p50 latency +<5 ms; the gain present in
at least two of the four `memory_type` groups.

Write `docs/research/l2-scene-retrieval-2026-08.md`: method, scene diagnostics
and oracle ceiling per clusterer, per-arm tables, twenty flip examples in each
direction with the scene that caused them, and an explicit conclusion —
including "no arm qualified" if that is the outcome.

- [ ] **Step 8: Confirmation runs, exactly once**

Only for the winning configuration: the holdout split and
`kb-memory-eval-set-v2.json`. A gain that does not hold on both was
overfitting; record that and do not enable the toggle.

- [ ] **Step 9: Commit**

```bash
git add scripts/scene-experiment.py docs/research/l2-scene-retrieval-2026-08.md
git commit -m "docs(research): report the L2 scene retrieval experiment"
```

---

## Self-review notes

- **Spec coverage:** derived store (T1), three clusterers (T2/T7/T8), build off
  the hot path (T3), knobs in `retrieve_params` (T4), prior + parity (T5),
  diagnostics + oracle ceiling (T6), staged arms + splits + winner rule +
  report (T9). Fail-open is covered by `_scene_members_for` (T5) and
  `cluster_llm` (T8).
- **Eval-set privacy:** the dev/holdout splits are derived from the personal
  eval set and stay in the scratchpad. They must never be committed —
  `test_eval_privacy.py` guards this.
- **Known gap, deliberate:** `kb-eval.py` may not yet emit `per_question`;
  Task 9 Step 3 adds it as a reporting field only.

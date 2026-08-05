"""Tests for the derived L2 scene layer (TASK-134).

Covers the store (schema, centroids, fingerprint) and the clusterers. The
parity test that guards the whole experiment lives in test_scene_recall.py.
"""
import sqlite3
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _scenes  # noqa: E402


def _graph_db(tmp_path, rows):
    """Minimal kb-graph.db stand-in: (source_file, community) node rows."""
    conn = sqlite3.connect(tmp_path / "kb-graph.db")
    conn.execute("CREATE TABLE graph_nodes (id TEXT PRIMARY KEY, label TEXT, "
                 "source_file TEXT, file_type TEXT, community INTEGER)")
    for i, (src, comm) in enumerate(rows):
        conn.execute("INSERT INTO graph_nodes VALUES (?,?,?,?,?)",
                     (f"n{i}", f"n{i}", src, "md", comm))
    conn.commit()
    return conn


# --- store ------------------------------------------------------------------

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


def test_best_scene_on_empty_store_is_none(tmp_path):
    conn = sqlite3.connect(tmp_path / "kb-scene.db")
    _scenes.ensure_schema(conn)
    assert _scenes.best_scene(conn, [1.0, 0.0], min_cos=0.0) is None


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
    # members and centroids of the previous run must go with it
    assert conn.execute("SELECT count(*) FROM scene_members").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM scene_centroids").fetchone()[0] == 1


def test_is_current_tracks_the_index_fingerprint(tmp_path):
    conn = sqlite3.connect(tmp_path / "kb-scene.db")
    _scenes.ensure_schema(conn)
    index = tmp_path / "kb-index.db"
    index.write_bytes(b"x")
    assert _scenes.is_current(conn, index) is False
    _scenes.set_fingerprint(conn, _scenes.fingerprint(index))
    assert _scenes.is_current(conn, index) is True


def test_is_current_false_after_index_changes(tmp_path):
    conn = sqlite3.connect(tmp_path / "kb-scene.db")
    _scenes.ensure_schema(conn)
    index = tmp_path / "kb-index.db"
    index.write_bytes(b"x")
    _scenes.set_fingerprint(conn, _scenes.fingerprint(index))
    index.write_bytes(b"xxxxxxxxxxxx")
    assert _scenes.is_current(conn, index) is False


# --- community clusterer ----------------------------------------------------

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


def test_community_tie_breaks_on_the_lowest_community_id(tmp_path):
    """A genuine tie: equal node counts in two communities.

    The direction of the tie-break is arbitrary but must be STABLE, or the
    same vault produces different scenes on two runs and the experiment
    compares noise. Without this case a majority vote hides the tie-break
    entirely.
    """
    g = _graph_db(tmp_path, [("09-memory/a.md", 7), ("09-memory/a.md", 2)])
    out = _scenes.cluster_community(["09-memory/a.md"], g)
    assert list(out.keys()) == ["community-2"]


def test_community_empty_input_is_empty(tmp_path):
    g = _graph_db(tmp_path, [("09-memory/a.md", 1)])
    assert _scenes.cluster_community([], g) == {}

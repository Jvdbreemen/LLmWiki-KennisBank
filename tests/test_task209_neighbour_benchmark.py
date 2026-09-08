"""TASK-209 measurements must distinguish evidence from repeated observations."""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "task209_benchmark", SCRIPTS / "task209-neighbour-benchmark.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def note(vault, name="private-title", body="A stable fact.", status="current"):
    path = vault / "09-memory" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nstatus: {status}\ntitle: private title\n---\n{body}\n",
                    encoding="utf-8")
    return path


def test_text_hash_ignores_frontmatter_but_file_hash_does_not(tmp_path):
    note(tmp_path)
    before = benchmark.snapshot(tmp_path)
    note(tmp_path, status="unverified")
    delta = benchmark.compare(before, benchmark.snapshot(tmp_path))
    assert delta["text_hash_changed"] == 0
    assert delta["file_only_changed"] == 1
    assert delta["status_changed"] == 1


def test_text_hash_matches_embedding_input_including_cap_and_newlines(tmp_path):
    import _embeddings as emb
    path = note(tmp_path, body="x" * 4100)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    first = benchmark.snapshot(tmp_path)
    record = next(iter(first["records"].values()))
    assert record["text_hash"] == emb.bytes_hash(emb.doc_text(path).encode("utf-8"))
    note(tmp_path, body="x" * 4000 + "changed beyond cap")
    assert benchmark.compare(first, benchmark.snapshot(tmp_path))["text_hash_changed"] == 0


def test_changed_added_and_removed_are_separate_counts(tmp_path):
    gone = note(tmp_path, name="gone")
    note(tmp_path)
    before = benchmark.snapshot(tmp_path)
    gone.unlink()
    note(tmp_path, body="A different fact.")
    note(tmp_path, name="new")
    delta = benchmark.compare(before, benchmark.snapshot(tmp_path))
    assert (delta["text_hash_changed"], delta["added"], delta["removed"]) == (1, 1, 1)


def test_snapshot_has_no_titles_bodies_or_memory_paths(tmp_path):
    note(tmp_path, body="sensitive body")
    serialized = json.dumps(benchmark.snapshot(tmp_path))
    for private in (str(tmp_path), "private-title", "private title", "sensitive body"):
        assert private not in serialized


def test_duplicate_observation_is_never_called_a_natural_sweep(tmp_path):
    note(tmp_path)
    observed = benchmark.snapshot(tmp_path)
    delta = benchmark.compare(observed, observed)
    assert delta["same_observation"] is True
    assert delta["natural_sweep_runs_proven"] == 0
    assert delta["text_hash_changed"] == 0


def test_new_heartbeat_does_not_prove_sweep_attribution(tmp_path):
    note(tmp_path)
    before = benchmark.snapshot(tmp_path)
    after = dict(before, captured_at="later", heartbeat_last_run="another run")
    delta = benchmark.compare(before, after)
    assert delta["heartbeat_changed"] is True
    assert delta["natural_sweep_runs_proven"] == 0


def test_incompatible_hash_contract_is_rejected(tmp_path):
    note(tmp_path)
    first = benchmark.snapshot(tmp_path)
    with pytest.raises(ValueError, match="contract"):
        benchmark.compare(first, dict(first, text_contract="different cap"))


def test_missing_memory_directory_cannot_look_like_zero_changes(tmp_path):
    with pytest.raises(ValueError, match="09-memory"):
        benchmark.snapshot(tmp_path)


def test_hash_migration_and_model_change_are_not_body_edits():
    old = {"a": {"text_hash": "a" * 8, "id": "model", "dim": 2},
           "b": {"text_hash": "b" * 16, "id": "old", "dim": 2},
           "c": {"text_hash": "c" * 16, "id": "model", "dim": 2},
           "d": {"hash": "file hash", "id": "model", "dim": 2}}
    new = {"a": dict(old["a"], text_hash="a" * 16),
           "b": dict(old["b"], id="new"),
           "c": dict(old["c"], text_hash="d" * 16), "d": old["d"]}
    delta = benchmark.compare_cache_records(old, new)
    assert delta["text_hash_changed"] == 1
    assert delta["incomparable_hash"] == 2
    assert delta["embedding_space_changed"] == 1
    assert delta["natural_sweep_runs_proven"] == 0


def test_database_is_only_read_and_mutations_target_memory(tmp_path):
    db = tmp_path / "test.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE sample (value INTEGER)")
        conn.execute("INSERT INTO sample VALUES (1)")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with benchmark.index_image(db, load_vec=False) as conn:
        assert conn.execute("SELECT value FROM sample").fetchone() == (1,)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM sample")
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_active_wal_is_refused_without_opening_database(tmp_path):
    db = tmp_path / "test.db"
    db.write_bytes(b"not a database")
    Path(str(db) + "-wal").write_bytes(b"active")
    with pytest.raises(ValueError, match="WAL"):
        with benchmark.index_image(db):
            pytest.fail("must not open")


def test_missing_database_is_not_created(tmp_path):
    db = tmp_path / "absent.db"
    with pytest.raises(FileNotFoundError):
        with benchmark.index_image(db):
            pytest.fail("must not open")
    assert not db.exists()


@pytest.fixture
def indexed(tmp_path):
    pytest.importorskip("sqlite_vec")
    import _embeddings as emb
    import _kbindex as index
    db = tmp_path / "test.db"
    conn = index.connect(db)
    index.ensure_schema(conn, dim=3, embed_id=emb.embed_id())
    index.set_unit_norm(conn, True)
    for name, vector in (("a", [1, 0, 0]), ("b", [1, 0.01, 0]),
                         ("far", [0, 1, 0])):
        path = note(tmp_path, name=name)
        index.upsert(conn, path=str(path), layer="memory", status="current",
                     body=name, vector=vector, file_hash=emb.file_hash(path))
    conn.commit()
    conn.close()
    return tmp_path, db


def test_benchmark_uses_production_index_arm_and_never_embeds(indexed, monkeypatch):
    import _embeddings as emb
    import _maintenance as maintenance
    vault, db = indexed
    def forbidden(*args, **kwargs):
        pytest.fail("measurement must not embed or open the live index")
    monkeypatch.setattr(emb, "embed", forbidden)
    monkeypatch.setattr(emb, "get_cached", forbidden)
    monkeypatch.setattr(maintenance, "_index_conn", forbidden)
    monkeypatch.setenv("KB_NO_PROGRESS", "1")
    with benchmark.index_image(db) as conn:
        result = benchmark.measure(conn, vault=vault, max_seconds=10)
    assert result["completed"] is True
    assert result["current_index_items"] == 3
    assert result["knn_queries"] == 3
    assert result["undirected_pairs"] == 1
    assert result["live_file_hash_matches"] == 3
    assert result["natural_sweep_runs_proven"] == 0


def test_unormalized_index_fails_closed(indexed):
    vault, db = indexed
    with benchmark.index_image(db) as conn:
        conn.execute("PRAGMA query_only=OFF")
        conn.execute("UPDATE meta SET value='0' WHERE key='unit_norm'")
        conn.execute("PRAGMA query_only=ON")
        with pytest.raises(ValueError, match="unit_norm"):
            benchmark.measure(conn, vault=vault, max_seconds=10)


def test_time_budget_cannot_fall_back_to_quadratic_work(indexed, monkeypatch):
    import _embeddings as emb
    vault, db = indexed
    monkeypatch.setattr(emb, "cosine", lambda *args: pytest.fail("no brute fallback"))
    with benchmark.index_image(db) as conn:
        result = benchmark.measure(conn, vault=vault, max_seconds=0)
    assert result["completed"] is False
    assert result["knn_queries"] == 0
    assert result["undirected_pairs"] is None


def test_stale_index_is_reported_without_claiming_live_equivalence(indexed):
    vault, db = indexed
    note(vault, name="a", body="new body")
    with benchmark.index_image(db) as conn:
        result = benchmark.measure(conn, vault=vault, max_seconds=10)
    assert result["live_file_hash_matches"] == 2
    assert result["live_file_hash_mismatches"] == 1
    assert result["scope"] == "index snapshot; not a live sweep"


def test_legacy_file_hash_width_is_incomparable_not_a_body_change(indexed):
    vault, db = indexed
    with benchmark.index_image(db) as conn:
        conn.execute("PRAGMA query_only=OFF")
        conn.execute("UPDATE docs SET hash='12345678'")
        conn.execute("PRAGMA query_only=ON")
        result = benchmark.measure(conn, vault=vault, max_seconds=0)
    assert result["live_file_hash_incomparable"] == 3
    assert result["live_file_hash_matches"] == 0
    assert result["live_file_hash_mismatches"] == 0

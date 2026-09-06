"""Builder contracts for the disposable lexical raw-source projection."""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_source_index", SCRIPTS / "build-source-index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class SourceBuilderContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        for rel in ("01-raw/transcripts", "05-bronnen", "08-archive", ".claude"):
            (self.vault / rel).mkdir(parents=True, exist_ok=True)
        (self.vault / "01-raw/transcripts/a.md").write_text(
            "A bounded timeout fixed the child process.", encoding="utf-8")
        (self.vault / "05-bronnen/b.txt").write_text(
            "SQLite keeps source evidence local.", encoding="utf-8")
        (self.vault / "08-archive/ignored.bin").write_bytes(b"not text")
        self.saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.addCleanup(self._restore)

    def _restore(self):
        if self.saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self.saved

    @property
    def db(self) -> Path:
        return self.vault / ".claude" / "kb-source.db"

    def connect(self):
        return closing(sqlite3.connect(self.db))

    def test_collect_uses_only_approved_roots_and_text_types(self):
        builder = _load_builder()
        paths = {p.relative_to(self.vault).as_posix()
                 for p in builder.collect_sources(self.vault)}
        self.assertEqual(paths, {
            "01-raw/transcripts/a.md", "05-bronnen/b.txt",
        })

    def test_builder_api_and_source_have_no_embedding_or_vector_path(self):
        builder = _load_builder()
        parameters = inspect.signature(builder.build_source_index).parameters
        self.assertNotIn("embed_fn", parameters)
        self.assertNotIn("embed_id", parameters)
        text = (SCRIPTS / "build-source-index.py").read_text(encoding="utf-8")
        for forbidden in ("_embeddings", "embed_fn", "query_vector", "vec_docs"):
            self.assertNotIn(forbidden, text)

    def test_schema_is_fts_only_and_contains_no_vector_table(self):
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True)
        with self.connect() as conn:
            schema = conn.execute(
                "SELECT name, type, sql FROM sqlite_master ORDER BY name"
            ).fetchall()
            names = {name for name, _kind, _sql in schema}
            self.assertIn("source_chunks", names)
            self.assertIn("source_manifest", names)
            self.assertIn("source_fts", names)
            fts_sql = next(sql for name, _kind, sql in schema
                           if name == "source_fts")
            self.assertIn("fts5", fts_sql.lower())
            self.assertIn("content='source_chunks'", fts_sql.lower())
            forbidden = [name for name in names
                         if "vector" in name.lower() or name.lower().startswith("vec")]
            self.assertEqual(forbidden, [], schema)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_build_is_rebuildable_and_incremental(self):
        builder = _load_builder()
        first = builder.build_source_index(self.vault, rebuild=True)
        second = builder.build_source_index(self.vault, rebuild=False)
        self.assertEqual(first["sources"], 2)
        self.assertGreaterEqual(first["indexed_chunks"], 2)
        self.assertEqual(second["indexed_chunks"], 0)
        self.assertEqual(second["unchanged_sources"], 2)

    def test_build_records_source_index_version_and_lexical_backend(self):
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True)
        with self.connect() as conn:
            meta = dict(conn.execute("SELECT key, value FROM source_meta"))
        self.assertEqual(meta["source_index_version"], builder.INDEX_VERSION)
        self.assertEqual(meta["retrieval_backend"], "sqlite_fts5")

    def test_build_persists_safe_source_frontmatter_metadata(self):
        metadata_source = self.vault / "01-raw" / "transcripts" / "metadata.md"
        metadata_source.write_text(
            "---\nsession_id: session-42\ndate: 2026-08-26\n"
            "project: local-brain\nclient: Codex\nrole: assistant\n---\n"
            "A source fact.", encoding="utf-8")
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True)
        with self.connect() as conn:
            metadata = conn.execute(
                "SELECT metadata_json FROM source_chunks "
                "WHERE source_path='01-raw/transcripts/metadata.md'"
            ).fetchone()[0]
        self.assertEqual(json.loads(metadata), {
            "client": "Codex", "date": "2026-08-26", "project": "local-brain",
            "role": "assistant", "session_id": "session-42", "source_root": "01-raw",
        })

    def test_full_rebuild_preserves_rows_for_unchanged_sources(self):
        builder = _load_builder()

        def snapshot():
            with self.connect() as conn:
                return conn.execute(
                    "SELECT source_path, source_hash, chunk_index, start, end, "
                    "passage, passage_hash, metadata_json FROM source_chunks "
                    "ORDER BY source_path, chunk_index"
                ).fetchall()

        builder.build_source_index(self.vault, rebuild=True)
        first = snapshot()
        builder.build_source_index(self.vault, rebuild=True)
        self.assertEqual(first, snapshot())

    def test_chunks_have_exact_offsets_and_source_and_passage_hashes(self):
        source_path = self.vault / "05-bronnen" / "b.txt"
        text = "alpha beta gamma delta epsilon"
        source_path.write_text(text, encoding="utf-8")
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True, chunk_size=12, overlap=3)
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT source_hash, start, end, passage, passage_hash "
                "FROM source_chunks WHERE source_path='05-bronnen/b.txt' "
                "ORDER BY chunk_index"
            ).fetchall()
        self.assertGreater(len(rows), 1)
        expected_source_hash = builder.sha256_file(source_path)
        for source_hash, start, end, passage, passage_hash in rows:
            self.assertEqual(source_hash, expected_source_hash)
            self.assertEqual(passage, text[start:end])
            self.assertEqual(passage_hash, _sha256_text(passage))

    def test_fts_finds_source_text_and_returns_exact_provenance_fields(self):
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True)
        with self.connect() as conn:
            row = conn.execute(
                "SELECT c.source_path, c.source_hash, c.chunk_index, c.start, c.end, "
                "c.passage_hash, c.passage FROM source_fts "
                "JOIN source_chunks c ON c.chunk_rowid=source_fts.rowid "
                "WHERE source_fts MATCH 'SQLite' "
                "ORDER BY bm25(source_fts) LIMIT 1"
            ).fetchone()
        self.assertEqual(row[0], "05-bronnen/b.txt")
        self.assertTrue(row[1].startswith("sha256:"))
        self.assertEqual(row[2], 0)
        self.assertEqual(row[3], 0)
        self.assertEqual(row[4], len(row[6]))
        self.assertEqual(row[5], _sha256_text(row[6]))

    def test_published_index_is_readable_by_the_runtime_gateway_schema(self):
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True)
        import _source_recall as runtime
        with closing(runtime.connect(self.db)) as conn:
            hits = runtime.source_hits(
                conn, query_text="SQLite", source_root=self.vault, k=1)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["passage"], "SQLite keeps source evidence local.")
        self.assertEqual(hits[0]["source_state"], "current")

    def test_changed_source_is_reindexed_and_gets_a_new_hash(self):
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True)
        source_path = self.vault / "05-bronnen" / "b.txt"
        source_path.write_text("SQLite changed source evidence.", encoding="utf-8")
        report = builder.build_source_index(self.vault, rebuild=False)
        self.assertGreater(report["indexed_chunks"], 0)
        with self.connect() as conn:
            stored = conn.execute(
                "SELECT source_hash FROM source_manifest "
                "WHERE source_path='05-bronnen/b.txt'"
            ).fetchone()[0]
        self.assertEqual(stored, builder.sha256_file(source_path))

    def test_build_emits_bounded_progress_events_when_requested(self):
        builder = _load_builder()
        events = []
        builder.build_source_index(self.vault, rebuild=True, progress_fn=events.append)
        self.assertTrue(events)
        self.assertEqual(events[0]["phase"], "scan")
        self.assertEqual(events[-1]["phase"], "complete")
        self.assertEqual(events[-1]["sources"], 2)
        events.clear()
        builder.build_source_index(self.vault, rebuild=False, progress_fn=events.append)
        self.assertEqual(events[-1]["phase"], "complete")
        self.assertEqual(events[-1]["status"], "unchanged")

    def test_failed_rebuild_keeps_the_previous_index(self):
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True)
        before = self.db.read_bytes()
        original = builder._insert_source
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected build failure")
            return original(*args, **kwargs)

        with mock.patch.object(builder, "_insert_source", side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, "injected build failure"):
                builder.build_source_index(self.vault, rebuild=True)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertFalse(self.db.with_name(self.db.name + ".staging").exists())

    def test_builder_streams_sources_instead_of_retaining_the_corpus(self):
        builder = _load_builder()
        original = builder._read_source
        reads = []

        def observed(path):
            reads.append(Path(path).name)
            return original(path)

        with mock.patch.object(builder, "_read_source", side_effect=observed):
            builder.build_source_index(self.vault, rebuild=True)
        # One bounded read during manifest scan and one during staged indexing;
        # retaining all decoded texts would only read once and grow with corpus size.
        self.assertEqual(reads.count("a.md"), 2)
        self.assertEqual(reads.count("b.txt"), 2)

    def test_deleted_source_is_removed_and_redacted_source_is_reported(self):
        builder = _load_builder()
        redacted = self.vault / "05-bronnen" / "private.redacted.txt"
        redacted.write_text("do not index", encoding="utf-8")
        builder.build_source_index(self.vault, rebuild=True)
        (self.vault / "05-bronnen" / "b.txt").unlink()
        report = builder.build_source_index(self.vault, rebuild=True)
        self.assertEqual(report["sources"], 1)
        self.assertIn("05-bronnen/private.redacted.txt", report["redacted_sources"])
        with self.connect() as conn:
            indexed = {row[0] for row in conn.execute(
                "SELECT source_path FROM source_manifest")}
        self.assertEqual(indexed, {"01-raw/transcripts/a.md"})

    def test_empty_rebuild_removes_deleted_sources(self):
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True)
        (self.vault / "01-raw/transcripts/a.md").unlink()
        (self.vault / "05-bronnen/b.txt").unlink()
        report = builder.build_source_index(self.vault, rebuild=True)
        self.assertEqual(report["sources"], 0)
        with self.connect() as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM source_chunks").fetchone()[0], 0)
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM source_fts").fetchone()[0], 0)

    def test_unreadable_source_preserves_previous_index_and_reports_it(self):
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True)
        before = self.db.read_bytes()
        bad = self.vault / "01-raw" / "transcripts" / "bad.txt"
        bad.write_bytes(b"\xff\xfe")
        report = builder.build_source_index(self.vault, rebuild=True)
        self.assertIn("01-raw/transcripts/bad.txt", report["failed_sources"])
        self.assertEqual(self.db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

"""Builder contracts for the disposable raw-source index."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_source_index", SCRIPTS / "build-source-index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_embed(text: str):
    lower = text.lower()
    return [float("timeout" in lower), float("sqlite" in lower),
            float("source" in lower), 0.25]


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

    def test_collect_uses_only_approved_roots_and_text_types(self):
        builder = _load_builder()
        paths = {p.relative_to(self.vault).as_posix() for p in builder.collect_sources(self.vault)}
        self.assertEqual(paths, {"01-raw/transcripts/a.md", "05-bronnen/b.txt"})

    def test_build_is_rebuildable_and_incremental(self):
        builder = _load_builder()
        first = builder.build_source_index(
            self.vault, rebuild=True, embed_fn=_fake_embed, embed_id="fake:4")
        second = builder.build_source_index(
            self.vault, rebuild=False, embed_fn=_fake_embed, embed_id="fake:4")
        self.assertEqual(first["sources"], 2)
        self.assertGreaterEqual(first["indexed_chunks"], 2)
        self.assertEqual(second["indexed_chunks"], 0)
        self.assertEqual(second["unchanged_sources"], 2)

    def test_build_records_source_index_version(self):
        builder = _load_builder()
        builder.build_source_index(
            self.vault, rebuild=True, embed_fn=_fake_embed, embed_id="fake:4")
        conn = builder.source.connect(self.vault / ".claude" / "kb-source.db")
        try:
            self.assertEqual(
                builder.source._kbindex.meta_get(conn, "source_index_version"),
                builder.INDEX_VERSION,
            )
        finally:
            conn.close()

    def test_build_persists_safe_source_frontmatter_metadata(self):
        metadata_source = self.vault / "01-raw" / "transcripts" / "metadata.md"
        metadata_source.write_text(
            "---\nsession_id: session-42\ndate: 2026-08-26\n"
            "project: local-brain\nclient: Codex\nrole: assistant\n---\n"
            "A source fact.", encoding="utf-8")
        builder = _load_builder()
        builder.build_source_index(
            self.vault, rebuild=True, embed_fn=_fake_embed, embed_id="fake:4")
        conn = builder.source.connect(self.vault / ".claude" / "kb-source.db")
        try:
            metadata = conn.execute(
                "SELECT metadata_json FROM source_chunks "
                "WHERE source_path='01-raw/transcripts/metadata.md'"
            ).fetchone()[0]
            self.assertEqual(json.loads(metadata), {
                "client": "Codex", "date": "2026-08-26", "project": "local-brain",
                "role": "assistant", "session_id": "session-42", "source_root": "01-raw",
            })
        finally:
            conn.close()

    def test_full_rebuild_preserves_ids_and_metadata_for_unchanged_sources(self):
        builder = _load_builder()

        def snapshot():
            conn = builder.source.connect(self.vault / ".claude" / "kb-source.db")
            try:
                docs = conn.execute(
                    "SELECT doc_id, path, hash, layer, status, title FROM docs "
                    "ORDER BY path"
                ).fetchall()
                chunks = conn.execute(
                    "SELECT source_path, source_hash, chunk_index, start, end, metadata_json "
                    "FROM source_chunks ORDER BY source_path, chunk_index"
                ).fetchall()
                return docs, chunks
            finally:
                conn.close()

        builder.build_source_index(
            self.vault, rebuild=True, embed_fn=_fake_embed, embed_id="fake:4")
        first = snapshot()
        builder.build_source_index(
            self.vault, rebuild=True, embed_fn=_fake_embed, embed_id="fake:4")
        self.assertEqual(first, snapshot())

    def test_changed_source_is_reindexed_and_gets_a_new_hash(self):
        builder = _load_builder()
        builder.build_source_index(
            self.vault, rebuild=True, embed_fn=_fake_embed, embed_id="fake:4")
        source = self.vault / "05-bronnen" / "b.txt"
        source.write_text("SQLite changed source evidence.", encoding="utf-8")
        report = builder.build_source_index(
            self.vault, rebuild=False, embed_fn=_fake_embed, embed_id="fake:4")
        self.assertGreater(report["indexed_chunks"], 0)
        conn = builder.source.connect(self.vault / ".claude" / "kb-source.db")
        try:
            stored = conn.execute(
                "SELECT source_hash FROM source_manifest WHERE source_path='05-bronnen/b.txt'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(stored, builder.source.sha256_file(source))

    def test_build_emits_bounded_progress_events_when_requested(self):
        builder = _load_builder()
        events = []
        builder.build_source_index(
            self.vault, rebuild=True, embed_fn=_fake_embed, embed_id="fake:4",
            progress_fn=events.append,
        )
        self.assertTrue(events)
        self.assertEqual(events[0]["phase"], "scan")
        self.assertEqual(events[-1]["phase"], "complete")
        self.assertEqual(events[-1]["sources"], 2)
        events.clear()
        builder.build_source_index(
            self.vault, rebuild=False, embed_fn=_fake_embed, embed_id="fake:4",
            progress_fn=events.append,
        )
        self.assertEqual(events[-1]["phase"], "complete")
        self.assertEqual(events[-1]["status"], "unchanged")

    def test_failed_rebuild_keeps_the_previous_index(self):
        builder = _load_builder()
        builder.build_source_index(
            self.vault, rebuild=True, embed_fn=_fake_embed, embed_id="fake:4")
        db = self.vault / ".claude" / "kb-source.db"
        before = db.read_bytes()
        failed = builder.build_source_index(
            self.vault, rebuild=True, embed_fn=lambda _text: None, embed_id="fake:4")
        self.assertGreater(failed["failed_chunks"], 0)
        self.assertEqual(db.read_bytes(), before)

    def test_model_change_forces_rebuild_instead_of_false_unchanged(self):
        builder = _load_builder()
        calls = []
        def embed(text):
            calls.append(text)
            return _fake_embed(text)
        builder.build_source_index(self.vault, rebuild=True, embed_fn=embed, embed_id="fake:4")
        calls.clear()
        report = builder.build_source_index(self.vault, rebuild=False,
                                            embed_fn=embed, embed_id="other:4")
        self.assertGreater(report["indexed_chunks"], 0)
        self.assertTrue(calls)

    def test_deleted_source_is_removed_and_redacted_source_is_reported(self):
        builder = _load_builder()
        redacted = self.vault / "05-bronnen" / "private.redacted.txt"
        redacted.write_text("do not index", encoding="utf-8")
        builder.build_source_index(self.vault, rebuild=True,
                                   embed_fn=_fake_embed, embed_id="fake:4")
        (self.vault / "05-bronnen" / "b.txt").unlink()
        report = builder.build_source_index(self.vault, rebuild=True,
                                             embed_fn=_fake_embed, embed_id="fake:4")
        self.assertEqual(report["sources"], 1)
        self.assertIn("05-bronnen/private.redacted.txt", report["redacted_sources"])

    def test_unreadable_source_preserves_previous_index_and_reports_it(self):
        builder = _load_builder()
        builder.build_source_index(self.vault, rebuild=True,
                                   embed_fn=_fake_embed, embed_id="fake:4")
        db = self.vault / ".claude" / "kb-source.db"
        before = db.read_bytes()
        bad = self.vault / "01-raw" / "transcripts" / "bad.txt"
        bad.write_bytes(b"\xff\xfe")
        report = builder.build_source_index(self.vault, rebuild=True,
                                            embed_fn=_fake_embed, embed_id="fake:4")
        self.assertIn("01-raw/transcripts/bad.txt", report["failed_sources"])
        self.assertEqual(db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

"""Contract tests for the provenance-first raw-source retrieval projection.

These tests intentionally precede the implementation. Synthetic text verifies
mechanics only; product-value evidence belongs to the frozen live-vault holdout.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _source_recall as sr  # noqa: E402


class SourceChunkContractTest(unittest.TestCase):
    def test_chunks_preserve_exact_offsets_and_overlap(self):
        text = "0123456789abcdefghijklmnopqrstuvwxyz"
        chunks = sr.chunk_text(text, size=14, overlap=4)
        self.assertGreater(len(chunks), 1)
        for idx, chunk in enumerate(chunks):
            self.assertEqual(chunk["index"], idx)
            self.assertEqual(text[chunk["start"]:chunk["end"]], chunk["text"])
        for left, right in zip(chunks, chunks[1:]):
            self.assertEqual(left["end"] - right["start"], 4)

    def test_invalid_chunk_parameters_fail_loudly(self):
        with self.assertRaises(ValueError):
            sr.chunk_text("text", size=10, overlap=10)


class SourceIndexContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        self.db = self.vault / ".claude" / "source.db"
        self.conn = sr.connect(self.db)
        self.addCleanup(self.conn.close)
        sr.ensure_schema(self.conn)

    def _write(self, relative: str, text: str) -> tuple[str, list[dict]]:
        path = self.vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return sr.sha256_file(path), sr.chunk_text(text, size=2000, overlap=200)

    def test_upsert_returns_exact_provenance_and_context(self):
        source = "01-raw/transcripts/session-a.md"
        text = "prefix evidence phrase suffix"
        source_hash, chunks = self._write(source, text)
        sr.upsert_source(
            self.conn,
            source_path=source,
            source_hash=source_hash,
            chunks=chunks,
            metadata={"session_id": "s-a", "project": "repo-a", "role": "assistant"},
        )
        hits = sr.source_hits(
            self.conn, query_text="evidence phrase", k=3, source_root=self.vault
        )
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual(hit["source_path"], source)
        self.assertEqual(hit["source_hash"], source_hash)
        self.assertEqual(hit["start"], 0)
        self.assertEqual(hit["end"], len(text))
        self.assertEqual(hit["passage"], text)
        self.assertEqual(hit["session_id"], "s-a")
        self.assertEqual(hit["project"], "repo-a")
        self.assertEqual(hit["layer"], "source")
        self.assertTrue(hit["fresh"])
        self.assertEqual(hit["source_state"], "current")
        self.assertEqual(hit["retrieval_route"], "lexical_fts")
        self.assertTrue(hit["best_effort"])
        self.assertRegex(hit["passage_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(hit["source_ref"]["source_ref_id"], r"^sr_[0-9a-f]{64}$")

    def test_source_filter_cannot_leak_a_different_document(self):
        for idx, path in enumerate(("01-raw/transcripts/a.md",
                                    "01-raw/transcripts/b.md")):
            source_hash, chunks = self._write(path, "evidence")
            sr.upsert_source(
                self.conn,
                source_path=path,
                source_hash=source_hash,
                chunks=chunks,
                metadata={},
            )
        hits = sr.source_hits(
            self.conn,
            query_text="evidence",
            k=5,
            source_path="01-raw/transcripts/b.md",
            source_root=self.vault,
        )
        self.assertEqual(
            [h["source_path"] for h in hits], ["01-raw/transcripts/b.md"])

    def test_replacing_source_removes_stale_chunks(self):
        old = [
            {"index": 0, "start": 0, "end": 3, "text": "one"},
            {"index": 1, "start": 2, "end": 5, "text": "net"},
        ]
        sr.upsert_source(self.conn, source_path="a.md", source_hash="old",
                         chunks=old, metadata={})
        new = [{"index": 0, "start": 0, "end": 3, "text": "new"}]
        sr.upsert_source(self.conn, source_path="a.md", source_hash="new",
                         chunks=new, metadata={})
        rows = self.conn.execute(
            "SELECT source_hash, chunk_index FROM source_chunks WHERE source_path='a.md'"
        ).fetchall()
        self.assertEqual(rows, [("new", 0)])

    def test_schema_contains_fts_but_no_vector_table(self):
        tables = {row[0] for row in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        self.assertIn("source_fts", tables)
        self.assertFalse(any("vec" in name.lower() for name in tables))

    def test_unrelated_lexical_query_is_a_no_hit(self):
        source_hash, chunks = self._write(
            "01-raw/transcripts/timeout.md", "timeout")
        sr.upsert_source(
            self.conn, source_path="01-raw/transcripts/timeout.md",
            source_hash=source_hash, chunks=chunks, metadata={})
        self.assertEqual(
            sr.source_hits(self.conn, query_text="unrelated phrase", k=3,
                           source_root=self.vault), [])

    def test_stale_source_is_labeled_and_never_returns_cached_passage(self):
        relative = "01-raw/transcripts/stale.md"
        source_hash, chunks = self._write(relative, "exact old evidence")
        sr.upsert_source(self.conn, source_path=relative,
                         source_hash=source_hash, chunks=chunks, metadata={})
        (self.vault / relative).write_text("changed evidence", encoding="utf-8")

        hit = sr.source_hits(
            self.conn, query_text="exact old", k=1,
            source_root=self.vault)[0]

        self.assertFalse(hit["fresh"])
        self.assertEqual(hit["source_state"], "stale")
        self.assertEqual(hit["passage"], "")


class SourceRouteContractTest(unittest.TestCase):
    def test_explicit_verify_and_reconstruct_always_route(self):
        for mode in ("explicit", "verify", "reconstruct"):
            self.assertTrue(sr.should_route(mode, primary_hits=[]))

    def test_fallback_never_routes(self):
        self.assertFalse(sr.should_route("fallback", primary_hits=[]))
        self.assertFalse(sr.should_route("fallback", primary_hits=[{"score": 0.2}]))

    def test_normal_mode_never_routes(self):
        self.assertFalse(sr.should_route("normal", primary_hits=[]))


class ContractFixtureTest(unittest.TestCase):
    def test_fixture_has_positive_and_negative_cases(self):
        rows = [json.loads(line) for line in
                (FIXTURES / "source_recall_contract.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertGreaterEqual(len([r for r in rows if r["expected_source"]]), 2)
        self.assertGreaterEqual(len([r for r in rows if not r["expected_source"]]), 1)


if __name__ == "__main__":
    unittest.main()

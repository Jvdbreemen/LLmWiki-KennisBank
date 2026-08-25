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


def _vec(*values: float) -> list[float]:
    return list(values)


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
        self.db = Path(self.tmp.name) / "source.db"
        self.conn = sr.connect(self.db)
        self.addCleanup(self.conn.close)
        sr.ensure_schema(self.conn, dim=4, embed_id="fake:4")

    def test_upsert_returns_exact_provenance_and_context(self):
        source = "01-raw/transcripts/session-a.md"
        text = "prefix evidence phrase suffix"
        chunks = [{"index": 0, "start": 0, "end": len(text), "text": text}]
        sr.upsert_source(
            self.conn,
            source_path=source,
            source_hash="sha256:a",
            chunks=chunks,
            vectors=[_vec(1, 0, 0, 0)],
            metadata={"session_id": "s-a", "project": "repo-a", "role": "assistant"},
        )
        hits = sr.source_hits(
            self.conn, query_vector=_vec(1, 0, 0, 0), query_text="evidence phrase", k=3
        )
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual(hit["source_path"], source)
        self.assertEqual(hit["source_hash"], "sha256:a")
        self.assertEqual(hit["start"], 0)
        self.assertEqual(hit["end"], len(text))
        self.assertEqual(hit["passage"], text)
        self.assertEqual(hit["session_id"], "s-a")
        self.assertEqual(hit["project"], "repo-a")
        self.assertEqual(hit["layer"], "source")

    def test_source_filter_cannot_leak_a_different_document(self):
        for idx, path in enumerate(("01-raw/a.md", "01-raw/b.md")):
            sr.upsert_source(
                self.conn,
                source_path=path,
                source_hash=f"h{idx}",
                chunks=[{"index": 0, "start": 0, "end": 7, "text": "evidence"}],
                vectors=[_vec(1, 0, 0, 0)],
                metadata={},
            )
        hits = sr.source_hits(
            self.conn,
            query_vector=_vec(1, 0, 0, 0),
            query_text="evidence",
            k=5,
            source_path="01-raw/b.md",
        )
        self.assertEqual([h["source_path"] for h in hits], ["01-raw/b.md"])

    def test_replacing_source_removes_stale_chunks(self):
        old = [
            {"index": 0, "start": 0, "end": 3, "text": "one"},
            {"index": 1, "start": 2, "end": 5, "text": "net"},
        ]
        sr.upsert_source(self.conn, source_path="a.md", source_hash="old",
                         chunks=old, vectors=[_vec(1, 0, 0, 0)] * 2, metadata={})
        new = [{"index": 0, "start": 0, "end": 3, "text": "new"}]
        sr.upsert_source(self.conn, source_path="a.md", source_hash="new",
                         chunks=new, vectors=[_vec(0, 1, 0, 0)], metadata={})
        rows = self.conn.execute(
            "SELECT source_hash, chunk_index FROM source_chunks WHERE source_path='a.md'"
        ).fetchall()
        self.assertEqual(rows, [("new", 0)])

    def test_model_identity_mismatch_disables_hits(self):
        sr.upsert_source(
            self.conn, source_path="a.md", source_hash="h",
            chunks=[{"index": 0, "start": 0, "end": 1, "text": "x"}],
            vectors=[_vec(1, 0, 0, 0)], metadata={})
        self.assertEqual(
            sr.source_hits(self.conn, query_vector=_vec(1, 0, 0, 0),
                           query_text="x", k=1, embed_id="other:model"),
            [],
        )


class SourceRouteContractTest(unittest.TestCase):
    def test_explicit_verify_and_reconstruct_always_route(self):
        for mode in ("explicit", "verify", "reconstruct"):
            self.assertTrue(sr.should_route(mode, primary_hits=[]))

    def test_fallback_requires_an_insufficient_primary_result(self):
        self.assertTrue(sr.should_route("fallback", primary_hits=[]))
        self.assertTrue(sr.should_route("fallback", primary_hits=[{"cos": 0.2}], floor=0.5))
        self.assertFalse(sr.should_route("fallback", primary_hits=[{"cos": 0.8}], floor=0.5))

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


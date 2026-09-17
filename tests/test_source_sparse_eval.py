"""Contracts for bounded sparse-first source evaluation (TASK-223).

These tests intentionally precede the implementation. They use a synthetic
vault and deterministic embeddings; live product value belongs to separately
calibrated private data and a write-once frozen holdout.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

    sys.path.insert(0, str(SCRIPTS / "dev"))
import _source_lexical_eval as lexical  # noqa: E402
import _source_sparse_eval as sparse  # noqa: E402


def _vector(text: str) -> list[float]:
    lowered = text.lower()
    return [
        float(lowered.count("grandchild") + lowered.count("pipe")),
        float(lowered.count("boiler") + lowered.count("telemetry")),
        float(lowered.count("weather") + lowered.count("forecast")),
        0.25,
    ]


class CountingEmbedder:
    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [_vector(text) for text in texts]


class SourceSparseEvalTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.first = self.vault / "01-raw" / "transcripts" / "first.md"
        self.second = self.vault / "05-bronnen" / "second.md"
        self.first.parent.mkdir(parents=True)
        self.second.parent.mkdir(parents=True)
        self.first.write_text(
            "prefix " + ("ordinary text " * 20) +
            "rare grandchild pipe timeout evidence" + (" suffix" * 20),
            encoding="utf-8",
        )
        self.second.write_text(
            "boiler telemetry pressure and temperature", encoding="utf-8")
        self.source_db = self.root / "source-fts.db"
        self.cache_db = self.root / "source-passages.db"
        lexical.build_index(self.vault, self.source_db)

    def _retrieve(self, embedder, **overrides):
        options = {
            "query": "grandchild pipe timeout",
            "vault": self.vault,
            "source_db": self.source_db,
            "cache_db": self.cache_db,
            "embed_fn": embedder,
            "model_id": "fake:model-a",
            "candidate_docs": 2,
            "max_passages": 4,
            "chunk_size": 120,
            "overlap": 20,
            "k": 3,
            "min_cos": 0.60,
        }
        options.update(overrides)
        return sparse.retrieve(**options)

    def test_retrieval_preserves_exact_provenance_and_offsets(self):
        hits = self._retrieve(CountingEmbedder())
        self.assertTrue(hits)
        hit = hits[0]
        relative = "01-raw/transcripts/first.md"
        text = self.first.read_text(encoding="utf-8")
        self.assertEqual(hit["source_path"], relative)
        self.assertEqual(hit["passage"], text[hit["start"]:hit["end"]])
        self.assertEqual(
            hit["source_hash"],
            "sha256:" + hashlib.sha256(self.first.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            hit["passage_hash"],
            "sha256:" + hashlib.sha256(hit["passage"].encode("utf-8")).hexdigest(),
        )
        self.assertEqual(hit["model_id"], "fake:model-a")
        self.assertEqual(hit["document_model_id"], "fake:model-a")
        self.assertEqual(hit["query_model_id"], "fake:model-a")
        self.assertEqual(hit["offset_unit"], "unicode_codepoint_normalized_newlines")
        self.assertEqual(hit["retrieval_mode"], "sparse_first_vector_rerank")

    def test_snapshot_hashes_original_bytes_but_offsets_slice_one_normalized_text(self):
        path = self.first.parent / "crlf.md"
        raw = "prefix\r\nrare grandchild pijp évidence\r\nsuffix".encode("utf-8")
        path.write_bytes(raw)
        snapshot = sparse.read_source_snapshot(path)
        self.assertEqual(snapshot["source_hash"],
                         "sha256:" + hashlib.sha256(raw).hexdigest())
        self.assertNotIn("\r", snapshot["text"])
        start = snapshot["text"].index("rare")
        end = snapshot["text"].index("\n", start)
        self.assertEqual(snapshot["text"][start:end],
                         "rare grandchild pijp évidence")
        self.assertEqual(snapshot["offset_unit"],
                         "unicode_codepoint_normalized_newlines")

    def test_cache_is_content_addressed_model_stamped_and_query_private(self):
        first_embedder = CountingEmbedder()
        first_hits = self._retrieve(first_embedder)
        self.assertTrue(first_hits)
        self.assertEqual(len(first_embedder.calls), 2)  # query, then cache misses

        warm_embedder = CountingEmbedder()
        warm_hits = self._retrieve(warm_embedder)
        self.assertEqual(warm_hits[0]["passage_hash"], first_hits[0]["passage_hash"])
        self.assertEqual(warm_embedder.calls, [["grandchild pipe timeout"]])

        with closing(sqlite3.connect(self.cache_db)) as conn:
            columns = {row[1] for row in conn.execute(
                "PRAGMA table_info(passage_embeddings)").fetchall()}
            rows = conn.execute(
                "SELECT model_id, content_hash, dimension, length(vector_blob) "
                "FROM passage_embeddings"
            ).fetchall()
        self.assertTrue(rows)
        self.assertTrue(all(row[0] == "fake:model-a" for row in rows))
        self.assertNotIn("passage", columns)
        self.assertNotIn("vector_json", columns)
        self.assertTrue(all(row[2] == 4 and row[3] == 16 for row in rows))

        other_model = CountingEmbedder()
        self._retrieve(other_model, model_id="fake:model-b")
        self.assertEqual(len(other_model.calls), 2)

        query_only = CountingEmbedder()
        documents = CountingEmbedder()
        self._retrieve(
            documents, embed_query_fn=query_only,
            query_model_id="fake:query-prefix-b")
        self.assertEqual(documents.calls, [])
        self.assertEqual(query_only.calls, [["grandchild pipe timeout"]])

    def test_changed_source_content_gets_a_new_cache_identity(self):
        self._retrieve(CountingEmbedder())
        with closing(sqlite3.connect(self.cache_db)) as conn:
            before = conn.execute(
                "SELECT count(*) FROM passage_embeddings").fetchone()[0]

        self.first.write_text(
            self.first.read_text(encoding="utf-8").replace(
                "rare grandchild", "rare corrected grandchild"),
            encoding="utf-8",
        )
        lexical.build_index(self.vault, self.source_db)
        changed = CountingEmbedder()
        self._retrieve(changed)
        self.assertEqual(len(changed.calls), 2)
        with closing(sqlite3.connect(self.cache_db)) as conn:
            after = conn.execute(
                "SELECT count(*) FROM passage_embeddings").fetchone()[0]
        self.assertGreater(after, before)

    def test_candidate_work_is_bounded_and_source_index_is_read_only(self):
        before = hashlib.sha256(self.source_db.read_bytes()).hexdigest()
        embedder = CountingEmbedder()
        self._retrieve(embedder, max_passages=1)
        after = hashlib.sha256(self.source_db.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertEqual(len(embedder.calls[1]), 1)

    def test_stale_fts_candidate_is_rejected_after_source_mutation(self):
        self.first.write_text(
            self.first.read_text(encoding="utf-8") + " changed after index",
            encoding="utf-8")
        self.assertEqual(self._retrieve(CountingEmbedder()), [])

    def test_duplicate_passage_text_reuses_one_cache_row_with_two_provenances(self):
        self.second.write_text(self.first.read_text(encoding="utf-8"), encoding="utf-8")
        lexical.build_index(self.vault, self.source_db)
        hits = self._retrieve(
            CountingEmbedder(), candidate_docs=2, max_passages=2, k=2)
        self.assertEqual(len({hit["source_path"] for hit in hits}), 2)
        with closing(sqlite3.connect(self.cache_db)) as conn:
            rows = conn.execute(
                "SELECT count(*) FROM passage_embeddings").fetchone()[0]
        self.assertEqual(rows, 1)

    def test_invalid_vectors_leave_no_cache_rows(self):
        class BadDocuments:
            def __call__(self, texts):
                return [[math.nan, 0.0, 0.0, 0.0] for _ in texts]

        with self.assertRaises(ValueError):
            self._retrieve(
                BadDocuments(), embed_query_fn=CountingEmbedder())
        with closing(sqlite3.connect(self.cache_db)) as conn:
            rows = conn.execute(
                "SELECT count(*) FROM passage_embeddings").fetchone()[0]
        self.assertEqual(rows, 0)

    def test_no_hit_threshold_abstains(self):
        hits = self._retrieve(
            CountingEmbedder(), query="weather forecast", min_cos=0.99)
        self.assertEqual(hits, [])

    def test_evaluation_reports_retrieval_citations_and_no_hit_specificity(self):
        text = self.first.read_text(encoding="utf-8")
        start = text.index("rare grandchild")
        cases = [
            {
                "id": "S1",
                "query": "grandchild pipe timeout",
                "expected_source": "01-raw/transcripts/first.md",
                "expected_windows": [{"start": start, "end": start + 37}],
            },
            {
                "id": "S2", "query": "weather forecast",
                "expected_source": None, "expected_windows": [],
            },
        ]
        report = sparse.evaluate(
            cases,
            vault=self.vault,
            source_db=self.source_db,
            cache_db=self.cache_db,
            embed_fn=CountingEmbedder(),
            model_id="fake:model-a",
            candidate_docs=2,
            max_passages=4,
            chunk_size=120,
            overlap=20,
            k=5,
            min_cos=0.99,
        )
        self.assertEqual(report["counts"], {"total": 2, "positive": 1, "negative": 1})
        self.assertEqual(report["retrieval"]["hit@5"], 1.0)
        self.assertEqual(report["passage_hit@5"], 1.0)
        self.assertEqual(report["no_hit_specificity"], 1.0)
        self.assertEqual(report["citation_precision"], 1.0)
        self.assertEqual(report["provenance_precision"], 1.0)
        self.assertIn("p95_ms", report["latency_ms"])
        self.assertNotIn("grandchild", json.dumps(report))

    def test_write_once_report_checks_before_running_builder(self):
        report_path = self.root / "final-report.json"
        calls = []
        sparse.write_once_report(report_path, lambda: calls.append(1) or {"n": 60})
        self.assertEqual(calls, [1])
        with self.assertRaises(FileExistsError):
            sparse.write_once_report(report_path, lambda: calls.append(2) or {})
        self.assertEqual(calls, [1])
        self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["n"], 60)


if __name__ == "__main__":
    unittest.main()

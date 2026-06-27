from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _kbindex  # noqa: E402

DIM = 4


class KbIndexSearchTest(unittest.TestCase):
    def setUp(self):
        self.conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(self.conn, dim=DIM, embed_id="ollama:test")
        # twee dichtbij, één ver weg
        _kbindex.upsert(self.conn, path="near.md", layer="memory", status="current",
                        body="hook gedreven retrieval bug", vector=[0.10, 0.20, 0.30, 0.40],
                        file_hash="h1", created="2026-06-01")
        _kbindex.upsert(self.conn, path="far.md", layer="wiki", status="current",
                        body="sqlite vector index", vector=[0.90, 0.80, 0.70, 0.60],
                        file_hash="h2", created="2026-06-02")
        _kbindex.upsert(self.conn, path="hidden.md", layer="memory", status="unverified",
                        body="hook geheim", vector=[0.11, 0.21, 0.31, 0.41],
                        file_hash="h3", created="2026-06-03")

    def tearDown(self):
        self.conn.close()

    def test_vector_only_orders_by_proximity(self):
        res = _kbindex.search(self.conn, query_vector=[0.10, 0.20, 0.30, 0.40], k=5)
        paths = [r["path"] for r in res]
        self.assertEqual(paths[0], "near.md")  # exact match bovenaan
        self.assertIn("far.md", paths)

    def test_status_filter_excludes_unverified(self):
        res = _kbindex.search(self.conn, query_vector=[0.11, 0.21, 0.31, 0.41], k=5,
                              statuses=("current",))
        self.assertNotIn("hidden.md", [r["path"] for r in res])

    def test_layer_filter(self):
        res = _kbindex.search(self.conn, query_vector=[0.10, 0.20, 0.30, 0.40], k=5,
                              layers=("wiki",))
        self.assertEqual([r["path"] for r in res], ["far.md"])

    def test_hybrid_uses_keyword(self):
        # vector wijst naar far, maar keyword 'bug' staat alleen in near
        res = _kbindex.search(self.conn, query_vector=[0.90, 0.80, 0.70, 0.60],
                              query_text="bug", k=5)
        self.assertIn("near.md", [r["path"] for r in res])

    def test_statuses_none_returns_unverified(self):
        """statuses=None mag onverifieerde docs doorlaten."""
        res = _kbindex.search(self.conn, query_vector=[0.11, 0.21, 0.31, 0.41], k=5,
                              statuses=None)
        paths = [r["path"] for r in res]
        self.assertIn("hidden.md", paths, "statuses=None moet ook unverified docs retourneren")

    def test_result_count_bounded_by_k(self):
        """len(result) mag k nooit overschrijden."""
        res = _kbindex.search(self.conn, query_vector=[0.50, 0.50, 0.50, 0.50], k=2)
        self.assertLessEqual(len(res), 2)


class LayerStarvationRegressionTest(unittest.TestCase):
    """Regression: memory doc mag niet uit de pool vallen door wiki-concurrenten.

    Scenario: 25 wiki docs liggen dichter bij de probe-vector dan 1 memory doc.
    Oud gedrag (pool=max(k*4,20)=20): top-20 zijn allemaal wiki; memory doc
    heeft rank 26 en valt eraf vóór de layer-filter → zoekresultaat leeg.
    Nieuw gedrag (pool dekt het gehele corpus): alle 26 docs in pool → memory
    doc overleeft de layer-filter.
    """

    def test_memory_doc_not_starved_by_wiki_docs(self):
        conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(conn, dim=DIM, embed_id="ollama:test")

        probe = [1.0, 0.0, 0.0, 0.0]
        # 25 wiki-vectors dicht bij probe (L2-afstand 0.005..0.125 van probe)
        for i in range(25):
            _kbindex.upsert(conn,
                path=f"wiki_{i:02d}.md", layer="wiki", status="current",
                body=f"wiki doc {i}",
                vector=[1.0 - (i + 1) * 0.005, 0.0, 0.0, 0.0],
                file_hash=f"hw{i}", created="2026-06-27")
        # 1 memory-vector veraf (L2-afstand ≈ 1.414), dus rank 26 van 26
        _kbindex.upsert(conn,
            path="mem_key.md", layer="memory", status="current",
            body="memory key doc",
            vector=[0.0, 0.0, 0.0, 1.0],
            file_hash="hmem", created="2026-06-27")

        res = _kbindex.search(conn, query_vector=probe, layers=("memory",), k=5)
        conn.close()
        paths = [r["path"] for r in res]
        self.assertIn(
            "mem_key.md", paths,
            "memory doc was starved out of the candidate pool by closer wiki docs "
            "(pool te klein — pool-fix ontbreekt?)")


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

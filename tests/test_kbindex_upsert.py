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


def _vec(seed: float):
    return [seed, seed + 0.1, seed + 0.2, seed + 0.3]


class KbIndexUpsertTest(unittest.TestCase):
    def setUp(self):
        self.conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(self.conn, dim=DIM, embed_id="ollama:test")

    def tearDown(self):
        self.conn.close()

    def test_upsert_inserts_one_doc_across_tables(self):
        _kbindex.upsert(self.conn, path="a.md", layer="wiki", status="current",
                        body="hook gedreven retrieval", vector=_vec(0.1),
                        file_hash="h1", title="A", created="2026-06-27")
        self.assertEqual(_kbindex.count(self.conn), 1)
        n_vec = self.conn.execute("SELECT count(*) FROM vec_docs").fetchone()[0]
        n_fts = self.conn.execute("SELECT count(*) FROM fts_docs").fetchone()[0]
        self.assertEqual((n_vec, n_fts), (1, 1))

    def test_upsert_same_path_replaces_not_duplicates(self):
        _kbindex.upsert(self.conn, path="a.md", layer="wiki", status="current",
                        body="oud", vector=_vec(0.1), file_hash="h1")
        _kbindex.upsert(self.conn, path="a.md", layer="wiki", status="current",
                        body="nieuw", vector=_vec(0.2), file_hash="h2")
        self.assertEqual(_kbindex.count(self.conn), 1)
        self.assertEqual(_kbindex.indexed_hash(self.conn, "a.md"), "h2")
        body = self.conn.execute("SELECT body FROM fts_docs").fetchone()[0]
        self.assertEqual(body, "nieuw")

    def test_indexed_hash_missing_is_none(self):
        self.assertIsNone(_kbindex.indexed_hash(self.conn, "ontbreekt.md"))

    def test_prune_removes_absent_paths(self):
        _kbindex.upsert(self.conn, path="a.md", layer="wiki", status="current",
                        body="a", vector=_vec(0.1), file_hash="h1")
        _kbindex.upsert(self.conn, path="b.md", layer="memory", status="current",
                        body="b", vector=_vec(0.2), file_hash="h2")
        removed = _kbindex.prune(self.conn, keep_paths={"a.md"})
        self.assertEqual(removed, 1)
        self.assertEqual(_kbindex.count(self.conn), 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM vec_docs").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()

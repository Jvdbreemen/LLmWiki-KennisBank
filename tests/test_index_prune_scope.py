"""Pausing a layer must not delete it from the index.

The settings toggles are documented as pausing background work. They also gate
which layers `_collect()` reads, and `prune()` used to treat everything outside
the keep-set as deleted — so turning a toggle off emptied that layer out of the
index on the very next run.

Measured when it happened: `embed_index=false` removed 199 wiki documents,
`memory_capture=false` the remaining 1508, leaving a 23 MB file with zero rows.
Retrieval then returned nothing relevant, silently, and three eval arms scored
0.016 / 0.000 / 0.000 before anyone suspected the index instead of the
experiment (TASK-136).

"Do not index new or changed files" and "consider these files deleted" are
different instructions. These tests hold them apart.
"""
from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _kbindex  # noqa: E402


def _schema(conn):
    conn.execute("CREATE TABLE docs (doc_id INTEGER PRIMARY KEY, path TEXT, "
                 "layer TEXT, status TEXT, hash TEXT, title TEXT, created TEXT)")
    conn.execute("CREATE TABLE fts_docs (rowid INTEGER PRIMARY KEY, body TEXT)")
    conn.execute("CREATE TABLE vec_docs (doc_id INTEGER PRIMARY KEY, embedding BLOB)")
    conn.execute("CREATE TABLE doc_sources (doc_id INTEGER, source TEXT)")


def _seed(conn, rows):
    for i, (path, layer) in enumerate(rows, 1):
        conn.execute("INSERT INTO docs(doc_id, path, layer, status, hash, title, created) "
                     "VALUES (?,?,?,?,?,?,?)", (i, path, layer, "current", "h", "t", "2026-01-01"))
        conn.execute("INSERT INTO fts_docs(rowid, body) VALUES (?,?)", (i, "body"))
        conn.execute("INSERT INTO vec_docs(doc_id, embedding) VALUES (?,?)", (i, b"\x00"))
        conn.execute("INSERT INTO doc_sources(doc_id, source) VALUES (?,?)", (i, "s"))
    conn.commit()


def _paths(conn, layer=None):
    sql = "SELECT path FROM docs" + (" WHERE layer=?" if layer else "")
    return {r[0] for r in conn.execute(sql, (layer,) if layer else ())}


class PruneScopeTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        _schema(self.conn)
        _seed(self.conn, [("/v/02-wiki/a.md", "wiki"), ("/v/02-wiki/b.md", "wiki"),
                          ("/v/09-memory/x.md", "memory"), ("/v/09-memory/y.md", "memory")])

    def tearDown(self):
        self.conn.close()

    def test_a_paused_wiki_layer_keeps_its_documents(self):
        """embed_index=false means only the memory layer is collected."""
        removed = _kbindex.prune(self.conn, keep_paths={"/v/09-memory/x.md",
                                                        "/v/09-memory/y.md"},
                                 layers={"memory"})
        self.assertEqual(removed, 0)
        self.assertEqual(len(_paths(self.conn, "wiki")), 2,
                         "een gepauzeerde laag is niet hetzelfde als een verwijderde laag")

    def test_a_paused_memory_layer_keeps_its_documents(self):
        removed = _kbindex.prune(self.conn, keep_paths={"/v/02-wiki/a.md",
                                                        "/v/02-wiki/b.md"},
                                 layers={"wiki"})
        self.assertEqual(removed, 0)
        self.assertEqual(len(_paths(self.conn, "memory")), 2)

    def test_a_genuinely_deleted_file_is_still_removed(self):
        """The scope narrows the judgement; it does not switch pruning off."""
        removed = _kbindex.prune(self.conn, keep_paths={"/v/02-wiki/a.md"},
                                 layers={"wiki"})
        self.assertEqual(removed, 1)
        self.assertEqual(_paths(self.conn, "wiki"), {"/v/02-wiki/a.md"})
        self.assertEqual(len(_paths(self.conn, "memory")), 2)

    def test_every_table_is_cleaned_for_a_removed_document(self):
        _kbindex.prune(self.conn, keep_paths={"/v/02-wiki/a.md"}, layers={"wiki"})
        for table, col in (("fts_docs", "rowid"), ("vec_docs", "doc_id"),
                           ("doc_sources", "doc_id")):
            left = {r[0] for r in self.conn.execute(f"SELECT {col} FROM {table}")}
            self.assertNotIn(2, left, f"{table} houdt een wees over")

    def test_without_a_layer_argument_nothing_changes(self):
        """Callers that do not gate by layer keep the old behaviour."""
        removed = _kbindex.prune(self.conn, keep_paths={"/v/02-wiki/a.md"})
        self.assertEqual(removed, 3)


class CollectAndLayersTest(unittest.TestCase):
    """_active_layers must agree with what _collect actually reads."""

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_kb_index_scope", str(SCRIPTS / "build-kb-index.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_a_toggle_off_drops_the_layer_from_the_active_set(self):
        m = self._load()
        saved = m._settings.get
        try:
            m._settings.get = lambda key, default=None: (
                False if key == "embed_index" else True)
            self.assertNotIn("wiki", m._active_layers())
            m._settings.get = lambda key, default=None: (
                False if key == "memory_capture" else True)
            self.assertNotIn("memory", m._active_layers())
        finally:
            m._settings.get = saved



class PruneNoticeTest(unittest.TestCase):
    """A tenth of the index disappearing is an event, not a column in a summary.

    The removal count was always printed -- as one number among five on the
    closing line. That is how 199 wiki documents and then 1508 memory documents
    went unnoticed: the line reported it, and reported it as routine.
    """

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_kb_index_notice", str(SCRIPTS / "build-kb-index.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_a_large_removal_is_called_out(self):
        m = self._load()
        notice = m.prune_notice(removed=199, total_before=1707, layers={"memory"})
        self.assertIn("199", notice)
        self.assertIn("1707", notice)
        self.assertIn("memory", notice, "welke lagen deze run las hoort erbij")

    def test_the_catastrophic_case_is_called_out(self):
        m = self._load()
        self.assertTrue(m.prune_notice(1508, 1508, set()))

    def test_ordinary_housekeeping_stays_quiet(self):
        """A handful of genuinely deleted notes must not train anyone to ignore it."""
        m = self._load()
        self.assertEqual(m.prune_notice(3, 1707, {"wiki", "memory"}), "")
        self.assertEqual(m.prune_notice(0, 1707, {"wiki"}), "")

    def test_an_empty_index_does_not_divide_by_zero(self):
        m = self._load()
        self.assertEqual(m.prune_notice(0, 0, set()), "")

if __name__ == "__main__":
    unittest.main()

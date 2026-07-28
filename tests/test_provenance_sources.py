"""Tests voor _provenance.doc_sources + de doc_sources-indexlaag (TASK-88)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _kbindex  # noqa: E402
import _provenance  # noqa: E402

from tests._loader import load_script  # noqa: E402

DIM = 4


def _vec(seed: float):
    return [seed, seed + 0.1, seed + 0.2, seed + 0.3]


class DocSourcesTest(unittest.TestCase):
    def test_memory_uses_source_session_basename(self):
        fm = {"source_session": "01-raw/transcripts/2026-07-01-sessie.jsonl.md"}
        self.assertEqual(
            _provenance.doc_sources(Path("m.md"), "memory", fm, ""),
            ["2026-07-01-sessie.jsonl.md"])

    def test_memory_windows_path_normalized(self):
        fm = {"source_session": "01-raw\\transcripts\\2026-07-01-x.md"}
        self.assertEqual(
            _provenance.doc_sources(Path("m.md"), "memory", fm, ""),
            ["2026-07-01-x.md"])

    def test_memory_without_field_is_empty(self):
        self.assertEqual(_provenance.doc_sources(Path("m.md"), "memory", {}, ""), [])

    def test_wiki_session_links_normalized_to_stem(self):
        body = ("Zie [[raw-sessie-2026-07-01-foo]] en "
                "[[01-raw/sessies/raw-sessie-2026-07-02-bar.md|gisteren]].")
        self.assertEqual(
            _provenance.doc_sources(Path("a.md"), "wiki", {}, body),
            ["raw-sessie-2026-07-01-foo", "raw-sessie-2026-07-02-bar"])

    def test_wiki_bron_links_normalized_without_md(self):
        body = "Bron: [[05-bronnen/evernote/nota.md|nota]] en [[05-bronnen/x]]."
        self.assertEqual(
            _provenance.doc_sources(Path("a.md"), "wiki", {}, body),
            ["05-bronnen/evernote/nota", "05-bronnen/x"])

    def test_wiki_plain_article_links_are_not_sources(self):
        body = "Verwant: [[ander-artikel]] en [[nog-een|alias]]."
        self.assertEqual(_provenance.doc_sources(Path("a.md"), "wiki", {}, body), [])

    def test_wiki_dedupes_and_sorts(self):
        body = "[[raw-sessie-b]] [[raw-sessie-a]] [[raw-sessie-b]]"
        self.assertEqual(
            _provenance.doc_sources(Path("a.md"), "wiki", {}, body),
            ["raw-sessie-a", "raw-sessie-b"])

    def test_other_layers_empty(self):
        self.assertEqual(
            _provenance.doc_sources(Path("x.md"), "sessie", {}, "[[raw-sessie-a]]"), [])

    def test_parsing_agrees_with_kb_lint_on_shared_fixture(self):
        """De vergrendeling: wat kb-lint als herkomst telt, telt _provenance
        als bron — zelfde fixture, zelfde uitkomstverzameling."""
        lint = load_script("kb-lint.py")
        body = ("Herkomst: [[raw-sessie-2026-07-01-foo]], "
                "[[01-raw/sessies/raw-sessie-2026-07-02-bar.md#kop|alias]] en "
                "[[05-bronnen/import/nota.md]]. Verwant: [[gewoon-artikel]].")
        lint_sessions = {lint.normalize_target(t)
                         for t in lint.WIKILINK_RE.findall(body)
                         if lint.normalize_target(t).startswith(lint.SESSION_PREFIX)}
        prov = set(_provenance.doc_sources(Path("a.md"), "wiki", {}, body))
        self.assertTrue(lint_sessions.issubset(prov))
        self.assertIn("05-bronnen/import/nota", prov)
        self.assertNotIn("gewoon-artikel", prov)


class DocSourcesIndexTest(unittest.TestCase):
    def setUp(self):
        self.conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(self.conn, dim=DIM, embed_id="ollama:test")

    def tearDown(self):
        self.conn.close()

    def _upsert(self, path, sources, seed=0.1):
        return _kbindex.upsert(
            self.conn, path=path, layer="wiki", status="current",
            body="tekst", vector=_vec(seed), file_hash="h", sources=sources)

    def test_upsert_stores_and_batch_reads_sources(self):
        d1 = self._upsert("a.md", ["raw-sessie-x", "raw-sessie-y"])
        d2 = self._upsert("b.md", ["raw-sessie-x"], seed=0.2)
        got = _kbindex.sources_for(self.conn, [d1, d2])
        self.assertEqual(got[d1], {"raw-sessie-x", "raw-sessie-y"})
        self.assertEqual(got[d2], {"raw-sessie-x"})

    def test_reupsert_replaces_sources(self):
        d = self._upsert("a.md", ["raw-sessie-oud"])
        self._upsert("a.md", ["raw-sessie-nieuw"])
        got = _kbindex.sources_for(self.conn, [d])
        self.assertEqual(got[d], {"raw-sessie-nieuw"})

    def test_empty_sources_leaves_no_rows(self):
        d = self._upsert("a.md", [])
        self.assertEqual(_kbindex.sources_for(self.conn, [d]), {})

    def test_prune_removes_source_rows(self):
        d = self._upsert("a.md", ["raw-sessie-x"])
        _kbindex.prune(self.conn, keep_paths=set())
        n = self.conn.execute("SELECT count(*) FROM doc_sources").fetchone()[0]
        self.assertEqual(n, 0)
        self.assertEqual(_kbindex.sources_for(self.conn, [d]), {})

    def test_sources_for_failsoft_without_table(self):
        self.conn.execute("DROP TABLE doc_sources")
        self.assertEqual(_kbindex.sources_for(self.conn, [1, 2]), {})

    def test_sources_for_empty_ids(self):
        self.assertEqual(_kbindex.sources_for(self.conn, []), {})


if __name__ == "__main__":
    unittest.main()

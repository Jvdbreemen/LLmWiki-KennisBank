"""Tests voor scripts/_rank.py - relevance x recency x importance + graafbuur.

Pure functies; frontmatter-reader en file-reader geinjecteerd.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _rank  # noqa: E402


class TestRecencyFactor(unittest.TestCase):
    def test_fresh_is_neutral(self):
        self.assertEqual(_rank.recency_factor(0), 1.0)

    def test_halflife_halves(self):
        # voorkeur: halfwaardetijd 180d -> factor 0.6-vloer wint van 0.5
        self.assertEqual(_rank.recency_factor(180, "voorkeur"), 0.6)
        # net onder de vloer-grens: 90d voorkeur = 0.5**0.5 ~ 0.707
        self.assertAlmostEqual(_rank.recency_factor(90, "voorkeur"), 0.7071, places=3)

    def test_type_differentiates(self):
        # zelfde leeftijd: een beslissing vervalt trager dan een voorkeur
        self.assertGreater(_rank.recency_factor(90, "beslissing"),
                           _rank.recency_factor(90, "voorkeur"))

    def test_floor_holds_for_ancient(self):
        self.assertEqual(_rank.recency_factor(10000, "voorkeur"), _rank.RECENCY_FLOOR)

    def test_unknown_type_uses_default(self):
        self.assertEqual(_rank.recency_factor(365, "onzin"),
                         _rank.recency_factor(365, "feit"))


class TestImportanceFactor(unittest.TestCase):
    def test_neutral_is_one(self):
        self.assertEqual(_rank.importance_factor(3), 1.0)

    def test_range(self):
        self.assertEqual(_rank.importance_factor(5), 1.1)
        self.assertAlmostEqual(_rank.importance_factor(1), 0.9)

    def test_clamped(self):
        self.assertEqual(_rank.importance_factor(99), 1.1)
        self.assertAlmostEqual(_rank.importance_factor(-2), 0.9)

    def test_unparseable_is_neutral(self):
        self.assertEqual(_rank.importance_factor(None), 1.0)
        self.assertEqual(_rank.importance_factor("hoog"), 1.0)


class TestRerank(unittest.TestCase):
    def test_wiki_untouched_memory_decayed(self):
        today = date(2026, 7, 1)
        hits = [
            {"path": "m.md", "layer": "memory", "score": 1.0},
            {"path": "w.md", "layer": "wiki", "score": 0.9},
        ]
        # memory: 180 dagen oud, voorkeur, importance 3 -> 1.0 * 0.6 = 0.6
        meta = {"m.md": {"memory_type": "voorkeur", "updated": "2026-01-02",
                         "importance": 3}}
        out = _rank.rerank(hits, lambda p: meta.get(p, {}), today=today)
        self.assertEqual([h["path"] for h in out], ["w.md", "m.md"])
        self.assertEqual(out[0]["score"], 0.9)  # wiki ongewogen
        self.assertAlmostEqual(out[1]["score"], 0.6, places=2)

    def test_importance_boosts(self):
        today = date(2026, 7, 1)
        hits = [
            {"path": "a.md", "layer": "memory", "score": 1.0},
            {"path": "b.md", "layer": "memory", "score": 1.0},
        ]
        meta = {"a.md": {"importance": 5, "updated": "2026-07-01"},
                "b.md": {"importance": 1, "updated": "2026-07-01"}}
        out = _rank.rerank(hits, lambda p: meta.get(p, {}), today=today)
        self.assertEqual(out[0]["path"], "a.md")
        self.assertAlmostEqual(out[0]["score"], 1.1)
        self.assertAlmostEqual(out[1]["score"], 0.9)

    def test_missing_metadata_is_neutral(self):
        hits = [{"path": "m.md", "layer": "memory", "score": 0.8}]
        out = _rank.rerank(hits, lambda p: {})
        self.assertEqual(out[0]["score"], 0.8)

    def test_meta_reader_exception_failsoft(self):
        def boom(p):
            raise RuntimeError("kapot")
        hits = [{"path": "m.md", "layer": "memory", "score": 0.8}]
        out = _rank.rerank(hits, boom)
        self.assertEqual(out[0]["score"], 0.8)


class TestOneHopNeighbor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.wiki = self.root / "02-wiki"
        self.wiki.mkdir(parents=True)

    def _art(self, stem: str, body: str = "") -> Path:
        p = self.wiki / f"{stem}.md"
        p.write_text(body, encoding="utf-8")
        return p

    def test_most_referenced_neighbor_wins(self):
        a = self._art("a", "[[buur]] en [[zeldzaam]]")
        b = self._art("b", "[[buur]]")
        self._art("buur")
        self._art("zeldzaam")
        hits = [{"path": str(a), "layer": "wiki"}, {"path": str(b), "layer": "wiki"}]
        self.assertEqual(_rank.one_hop_neighbor(hits, self.root), "buur")

    def test_hits_excluded_as_neighbor(self):
        a = self._art("a", "[[b]]")
        b = self._art("b", "[[a]]")
        hits = [{"path": str(a), "layer": "wiki"}, {"path": str(b), "layer": "wiki"}]
        self.assertIsNone(_rank.one_hop_neighbor(hits, self.root))

    def test_nonexistent_target_ignored(self):
        a = self._art("a", "[[bestaat-niet]] en [[raw-sessie-2026-01-01-x]]")
        hits = [{"path": str(a), "layer": "wiki"}]
        self.assertIsNone(_rank.one_hop_neighbor(hits, self.root))

    def test_memory_hits_not_expanded(self):
        a = self._art("a", "[[buur]]")
        self._art("buur")
        hits = [{"path": str(a), "layer": "memory"}]
        self.assertIsNone(_rank.one_hop_neighbor(hits, self.root))

    def test_no_links_returns_none(self):
        a = self._art("a", "geen links hier")
        hits = [{"path": str(a), "layer": "wiki"}]
        self.assertIsNone(_rank.one_hop_neighbor(hits, self.root))


if __name__ == "__main__":
    unittest.main()

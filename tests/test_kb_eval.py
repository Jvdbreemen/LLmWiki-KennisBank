"""Tests voor scripts/kb-eval.py - recall@k eval-harnas.

Pure-function tests: hits_fn geinjecteerd, geen model, geen index.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._loader import load_script


def _ev():
    return load_script("kb-eval.py")


class TestRank(unittest.TestCase):
    def setUp(self):
        self.ev = _ev()

    def test_first_position(self):
        self.assertEqual(self.ev.rank_of_first_expected(["a", "b"], ["a"]), 1)

    def test_later_position(self):
        self.assertEqual(self.ev.rank_of_first_expected(["x", "y", "a"], ["a"]), 3)

    def test_not_found_is_zero(self):
        self.assertEqual(self.ev.rank_of_first_expected(["x", "y"], ["a"]), 0)

    def test_any_of_expected_counts(self):
        self.assertEqual(self.ev.rank_of_first_expected(["x", "b"], ["a", "b"]), 2)


class TestEvaluate(unittest.TestCase):
    def setUp(self):
        self.ev = _ev()
        self.entries = [
            {"q": "v1", "expect": ["a"], "type": "keyword"},
            {"q": "v2", "expect": ["b"], "type": "paraphrase"},
            {"q": "v3", "expect": ["c"], "type": "paraphrase"},
        ]
        # v1: rang 1; v2: rang 4; v3: niet gevonden
        self.hits = {"v1": ["a", "x", "y", "z", "w"],
                     "v2": ["x", "y", "z", "b", "w"],
                     "v3": ["x", "y", "z", "w", "v"]}

    def _fn(self, q, k):
        return self.hits[q][:k]

    def test_recall_at_k(self):
        r = self.ev.evaluate(self.entries, self._fn)
        self.assertEqual(r["recall"]["@1"], round(1 / 3, 3))
        self.assertEqual(r["recall"]["@3"], round(1 / 3, 3))
        self.assertEqual(r["recall"]["@5"], round(2 / 3, 3))

    def test_mrr(self):
        r = self.ev.evaluate(self.entries, self._fn)
        self.assertEqual(r["mrr"], round((1.0 + 0.25 + 0.0) / 3, 3))

    def test_by_type_breakdown(self):
        r = self.ev.evaluate(self.entries, self._fn)
        self.assertEqual(r["by_type"]["keyword"]["n"], 1)
        self.assertEqual(r["by_type"]["keyword"]["@1"], 1.0)
        self.assertEqual(r["by_type"]["paraphrase"]["n"], 2)
        self.assertEqual(r["by_type"]["paraphrase"]["@5"], 0.5)

    def test_results_carry_rank_and_hits(self):
        r = self.ev.evaluate(self.entries, self._fn)
        self.assertEqual([x["rank"] for x in r["results"]], [1, 4, 0])


class TestLoadSet(unittest.TestCase):
    def setUp(self):
        self.ev = _ev()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _write(self, obj) -> Path:
        p = Path(self.tmp.name) / "set.json"
        p.write_text(json.dumps(obj), encoding="utf-8")
        return p

    def test_valid_set_loads(self):
        p = self._write([{"q": "v", "expect": ["a"]}])
        self.assertEqual(len(self.ev.load_set(p)), 1)

    def test_empty_list_rejected(self):
        with self.assertRaises(ValueError):
            self.ev.load_set(self._write([]))

    def test_missing_expect_rejected(self):
        with self.assertRaises(ValueError):
            self.ev.load_set(self._write([{"q": "v"}]))

    def test_expect_must_be_list(self):
        with self.assertRaises(ValueError):
            self.ev.load_set(self._write([{"q": "v", "expect": "a"}]))


class TestLayerWiring(unittest.TestCase):
    def setUp(self):
        self.ev = _ev()

    def test_memory_set_constant_defined(self):
        # de geheugen-set moet een eigen default-pad hebben, los van de wiki-set
        self.assertTrue(self.ev.MEMORY_SET.endswith("kb-memory-eval-set.json"))
        self.assertNotEqual(self.ev.DEFAULT_SET, self.ev.MEMORY_SET)

    def test_run_one_reports_load_error_without_model(self):
        # _run_one faalt-soft op een onbruikbare set VOOR het model geraadpleegd
        # wordt (faalt bij load_set, geen embedding nodig).
        name, res = self.ev._run_one(Path("bestaat-niet-xyz.json"), "wiki")
        self.assertIsInstance(res, str)
        self.assertIn("niet bruikbaar", res)

    def test_repo_example_memory_set_is_valid(self):
        # de meegeleverde voorbeeld-geheugenset moet de schema-validatie passeren
        root = Path(__file__).resolve().parent.parent
        example = root / "kb-memory-eval-set.example.json"
        if example.exists():
            entries = self.ev.load_set(example)
            self.assertTrue(all("memory" not in e for e in entries))  # geen laag-veld nodig
            self.assertGreater(len(entries), 0)


if __name__ == "__main__":
    unittest.main()

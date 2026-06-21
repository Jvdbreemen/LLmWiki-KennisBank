"""Tests for scripts/kb-search.py — rank() pure function.

Unit-tests for rank(query_vec, candidates, top_n, threshold) with injected
vectors. No network, no Ollama, no filesystem.
"""
from __future__ import annotations

import unittest

from tests._loader import load_script


def _ks():
    return load_script("kb-search.py")


class TestRankEmpty(unittest.TestCase):
    def test_empty_candidates_returns_empty(self):
        ks = _ks()
        result = ks.rank([1, 0, 0], {}, top_n=3, threshold=0.5)
        self.assertEqual(result, [])


class TestRankOrdering(unittest.TestCase):
    """Results must be sorted by descending cosine score."""

    def setUp(self):
        self.ks = _ks()
        # target: [1, 0, 0]
        # near: [0.95, 0.05, 0]  — high cosine
        # mid:  [0.8,  0.2,  0]  — medium cosine
        # ortho:[0,    1,    0]  — cosine 0.0
        self.query = [1.0, 0.0, 0.0]
        self.candidates = {
            "mid.md":   [0.8,  0.2,  0.0],
            "near.md":  [0.95, 0.05, 0.0],
            "ortho.md": [0.0,  1.0,  0.0],
        }

    def test_first_result_is_highest_score(self):
        ks = self.ks
        results = ks.rank(self.query, self.candidates, top_n=5, threshold=0.0)
        self.assertEqual(results[0][0], "near.md")

    def test_second_result_is_second_highest(self):
        ks = self.ks
        results = ks.rank(self.query, self.candidates, top_n=5, threshold=0.0)
        self.assertEqual(results[1][0], "mid.md")

    def test_scores_are_descending(self):
        ks = self.ks
        results = ks.rank(self.query, self.candidates, top_n=5, threshold=0.0)
        scores = [r[1] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestRankThresholdFilter(unittest.TestCase):
    """Candidates below threshold must be excluded."""

    def test_below_threshold_excluded(self):
        ks = _ks()
        query = [1.0, 0.0, 0.0]
        candidates = {
            "high.md":  [0.95, 0.05, 0.0],   # high cosine, above threshold
            "ortho.md": [0.0,  1.0,  0.0],    # cosine 0.0, below threshold
        }
        results = ks.rank(query, candidates, top_n=5, threshold=0.60)
        paths = [r[0] for r in results]
        self.assertIn("high.md", paths)
        self.assertNotIn("ortho.md", paths)

    def test_all_below_threshold_returns_empty(self):
        ks = _ks()
        query = [1.0, 0.0, 0.0]
        candidates = {
            "ortho.md": [0.0, 1.0, 0.0],
        }
        results = ks.rank(query, candidates, top_n=5, threshold=0.60)
        self.assertEqual(results, [])


class TestRankTopNCap(unittest.TestCase):
    """With 5 candidates above threshold and top_n=2, return exactly 2."""

    def test_top_n_caps_results(self):
        ks = _ks()
        query = [1.0, 0.0, 0.0]
        # 5 candidates all with positive cosine to [1,0,0], all above threshold 0.0
        candidates = {
            "a.md": [0.99, 0.01, 0.0],
            "b.md": [0.95, 0.05, 0.0],
            "c.md": [0.90, 0.10, 0.0],
            "d.md": [0.85, 0.15, 0.0],
            "e.md": [0.80, 0.20, 0.0],
        }
        results = ks.rank(query, candidates, top_n=2, threshold=0.0)
        self.assertEqual(len(results), 2)

    def test_top_n_returns_highest_two(self):
        ks = _ks()
        query = [1.0, 0.0, 0.0]
        candidates = {
            "a.md": [0.99, 0.01, 0.0],
            "b.md": [0.95, 0.05, 0.0],
            "c.md": [0.90, 0.10, 0.0],
            "d.md": [0.85, 0.15, 0.0],
            "e.md": [0.80, 0.20, 0.0],
        }
        results = ks.rank(query, candidates, top_n=2, threshold=0.0)
        paths = [r[0] for r in results]
        self.assertIn("a.md", paths)
        self.assertIn("b.md", paths)


class TestRankReturnShape(unittest.TestCase):
    """rank() must return list of (path, score) tuples."""

    def test_returns_list(self):
        ks = _ks()
        result = ks.rank([1, 0], {"a.md": [1, 0]}, top_n=3, threshold=0.0)
        self.assertIsInstance(result, list)

    def test_each_item_is_two_tuple(self):
        ks = _ks()
        results = ks.rank([1, 0], {"a.md": [1, 0]}, top_n=3, threshold=0.0)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], tuple)
        self.assertEqual(len(results[0]), 2)

    def test_score_is_float(self):
        ks = _ks()
        results = ks.rank([1, 0], {"a.md": [1, 0]}, top_n=3, threshold=0.0)
        _, score = results[0]
        self.assertIsInstance(score, float)


if __name__ == "__main__":
    unittest.main()

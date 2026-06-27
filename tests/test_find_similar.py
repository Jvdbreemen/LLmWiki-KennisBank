"""Tests for scripts/find-similar.py — candidate-match helper.

Pure-function tests for best_match: no network, no Ollama, no filesystem.
Vectors are injected directly.
"""
from __future__ import annotations

import unittest

from tests._loader import load_script


def _fs():
    return load_script("find-similar.py")


class TestBestMatchEmpty(unittest.TestCase):
    def test_empty_candidates_returns_none_zero(self):
        fs = _fs()
        result = fs.best_match([1, 0, 0], {})
        self.assertEqual(result, (None, 0.0))


class TestBestMatchPicksHigher(unittest.TestCase):
    def setUp(self):
        self.fs = _fs()
        # target: [1, 0, 0]
        # near-parallel: [0.9, 0.1, 0]  — high cosine with target
        # orthogonal:   [0, 1, 0]       — cosine 0.0 with target
        self.target = [1.0, 0.0, 0.0]
        self.candidates = {
            "orthogonal.md": [0.0, 1.0, 0.0],
            "near-parallel.md": [0.9, 0.1, 0.0],
        }

    def test_picks_near_parallel(self):
        path, score = self.fs.best_match(self.target, self.candidates)
        self.assertEqual(path, "near-parallel.md")

    def test_score_of_near_parallel_is_higher_than_orthogonal(self):
        _, score = self.fs.best_match(self.target, self.candidates)
        self.assertGreater(score, 0.5)

    def test_orthogonal_would_score_zero(self):
        # Confirm the orthogonal vector alone scores 0 against target
        fs = self.fs
        _, score = fs.best_match(self.target, {"ortho.md": [0.0, 1.0, 0.0]})
        self.assertAlmostEqual(score, 0.0, places=6)


class TestBestMatchTwoCandidates(unittest.TestCase):
    def test_returns_highest_cosine_path(self):
        fs = _fs()
        target = [1.0, 0.0, 0.0]
        candidates = {
            "low.md": [0.5, 0.5, 0.0],   # cosine ~0.707
            "high.md": [0.99, 0.1, 0.0],  # cosine > 0.9
        }
        path, score = fs.best_match(target, candidates)
        self.assertEqual(path, "high.md")
        self.assertGreater(score, 0.8)

    def test_returns_tuple_of_two(self):
        fs = _fs()
        result = fs.best_match([1, 0], {"a.md": [0, 1]})
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_score_is_float(self):
        fs = _fs()
        _, score = fs.best_match([1, 0], {"a.md": [1, 0]})
        self.assertIsInstance(score, float)


if __name__ == "__main__":
    unittest.main()

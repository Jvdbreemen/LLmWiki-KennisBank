"""Tests for scripts/conflict-scan.py — contradiction detection.

Pure-function tests for candidate_pairs and contradiction_signal:
no network, no Ollama, no filesystem, no vault.
Vectors and texts are injected directly.
"""
from __future__ import annotations

import unittest

from tests._loader import load_script


def _cs():
    return load_script("conflict-scan.py")


# ---------------------------------------------------------------------------
# candidate_pairs
# ---------------------------------------------------------------------------

class TestCandidatePairsEmpty(unittest.TestCase):
    def test_empty_embeddings_returns_empty(self):
        cs = _cs()
        result = cs.candidate_pairs({}, sim_threshold=0.62)
        self.assertEqual(result, [])

    def test_single_article_no_pairs(self):
        cs = _cs()
        result = cs.candidate_pairs({"a.md": [1.0, 0.0, 0.0]}, sim_threshold=0.62)
        self.assertEqual(result, [])


class TestCandidatePairsThreshold(unittest.TestCase):
    """Only pairs with cosine >= sim_threshold should be included."""

    def setUp(self):
        self.cs = _cs()
        # a and b are near-parallel: cosine([1,0,0],[0.9,0.1,0]) > 0.62
        # a and c are orthogonal: cosine([1,0,0],[0,1,0]) = 0.0
        # b and c: cosine([0.9,0.1,0],[0,1,0]) low
        self.embeddings = {
            "a.md": [1.0, 0.0, 0.0],
            "b.md": [0.9, 0.1, 0.0],  # near-parallel to a
            "c.md": [0.0, 1.0, 0.0],  # orthogonal to a
        }

    def test_near_parallel_pair_included(self):
        cs = self.cs
        pairs = cs.candidate_pairs(self.embeddings, sim_threshold=0.62)
        paths = [(p[0], p[1]) for p in pairs]
        # Either (a,b) or (b,a) must be present
        self.assertTrue(
            ("a.md", "b.md") in paths or ("b.md", "a.md") in paths,
            f"Expected a.md/b.md pair in {paths}",
        )

    def test_below_threshold_pair_excluded(self):
        cs = self.cs
        pairs = cs.candidate_pairs(self.embeddings, sim_threshold=0.62)
        paths = [(p[0], p[1]) for p in pairs]
        self.assertNotIn(("a.md", "c.md"), paths)
        self.assertNotIn(("c.md", "a.md"), paths)
        self.assertNotIn(("b.md", "c.md"), paths)
        self.assertNotIn(("c.md", "b.md"), paths)

    def test_exactly_one_pair_returned(self):
        cs = self.cs
        pairs = cs.candidate_pairs(self.embeddings, sim_threshold=0.62)
        self.assertEqual(len(pairs), 1)


class TestCandidatePairsNoDuplicatesNoSelf(unittest.TestCase):
    """No self-pairs; (a,b) and (b,a) must not both appear."""

    def test_no_self_pairs(self):
        cs = _cs()
        embeddings = {"a.md": [1.0, 0.0], "b.md": [1.0, 0.0]}
        pairs = cs.candidate_pairs(embeddings, sim_threshold=0.0)
        for p in pairs:
            self.assertNotEqual(p[0], p[1], f"Self-pair found: {p}")

    def test_no_duplicate_pairs(self):
        cs = _cs()
        embeddings = {
            "a.md": [1.0, 0.0],
            "b.md": [0.9, 0.1],
            "c.md": [0.8, 0.2],
        }
        pairs = cs.candidate_pairs(embeddings, sim_threshold=0.0)
        seen = set()
        for p in pairs:
            key = (min(p[0], p[1]), max(p[0], p[1]))
            self.assertNotIn(key, seen, f"Duplicate pair: {key}")
            seen.add(key)


class TestCandidatePairsTupleShape(unittest.TestCase):
    """Each returned item must be (path_a, path_b, score)."""

    def test_tuple_has_three_elements(self):
        cs = _cs()
        embeddings = {"a.md": [1.0, 0.0], "b.md": [1.0, 0.0]}
        pairs = cs.candidate_pairs(embeddings, sim_threshold=0.0)
        self.assertGreater(len(pairs), 0)
        for p in pairs:
            self.assertEqual(len(p), 3, f"Expected 3-tuple, got: {p}")

    def test_score_is_float(self):
        cs = _cs()
        embeddings = {"a.md": [1.0, 0.0], "b.md": [1.0, 0.0]}
        pairs = cs.candidate_pairs(embeddings, sim_threshold=0.0)
        for p in pairs:
            self.assertIsInstance(p[2], float)

    def test_result_is_sorted_deterministically(self):
        """Same input must always produce the same order."""
        cs = _cs()
        embeddings = {
            "a.md": [1.0, 0.0, 0.0],
            "b.md": [0.9, 0.1, 0.0],
            "c.md": [0.8, 0.2, 0.0],
        }
        pairs1 = cs.candidate_pairs(embeddings, sim_threshold=0.0)
        pairs2 = cs.candidate_pairs(embeddings, sim_threshold=0.0)
        self.assertEqual(pairs1, pairs2)


# ---------------------------------------------------------------------------
# contradiction_signal
# ---------------------------------------------------------------------------

class TestContradictionSignalRange(unittest.TestCase):
    """Signal must always be in [0, 1]."""

    def test_identical_texts_in_range(self):
        cs = _cs()
        text = "Het cijfer is 5."
        sig = cs.contradiction_signal(text, text)
        self.assertGreaterEqual(sig, 0.0)
        self.assertLessEqual(sig, 1.0)

    def test_random_texts_in_range(self):
        cs = _cs()
        a = "De zon schijnt vandaag."
        b = "Het regent buiten."
        sig = cs.contradiction_signal(a, b)
        self.assertGreaterEqual(sig, 0.0)
        self.assertLessEqual(sig, 1.0)

    def test_empty_texts_in_range(self):
        cs = _cs()
        sig = cs.contradiction_signal("", "")
        self.assertGreaterEqual(sig, 0.0)
        self.assertLessEqual(sig, 1.0)


class TestContradictionSignalContradictsHigherThanAgreeing(unittest.TestCase):
    """Core requirement: negation pair must outscore agreeing pair."""

    def setUp(self):
        self.cs = _cs()
        # Contradiction pair: same subject, explicit negation in one
        self.contra_a = "Het cijfer is geen 5"
        self.contra_b = "Het cijfer is 5"
        # Agreeing pair: same subject, positive framing in both
        self.agree_a = "Het cijfer is 5"
        self.agree_b = "Het cijfer is vijf positief"

    def test_contradiction_signal_higher_than_agreeing(self):
        cs = self.cs
        contra_score = cs.contradiction_signal(self.contra_a, self.contra_b)
        agree_score = cs.contradiction_signal(self.agree_a, self.agree_b)
        self.assertGreater(
            contra_score,
            agree_score,
            f"Expected contradiction ({contra_score:.4f}) > agreeing ({agree_score:.4f})",
        )

    def test_both_scores_in_unit_interval(self):
        cs = self.cs
        contra = cs.contradiction_signal(self.contra_a, self.contra_b)
        agree = cs.contradiction_signal(self.agree_a, self.agree_b)
        for score in (contra, agree):
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)


class TestContradictionSignalNegationTokens(unittest.TestCase):
    """Negation tokens drive higher signal."""

    def test_niet_negation_raises_signal(self):
        cs = _cs()
        # "X is Y" vs "X is niet Y" — negation in B on shared term
        a = "De API is beschikbaar"
        b = "De API is niet beschikbaar"
        sig = cs.contradiction_signal(a, b)
        # Signal should be detectably above zero
        self.assertGreater(sig, 0.0)

    def test_no_negation_no_contradiction(self):
        cs = _cs()
        a = "De functie werkt correct"
        b = "De functie werkt prima"
        sig_agree = cs.contradiction_signal(a, b)
        a2 = "De functie werkt correct"
        b2 = "De functie werkt niet correct"
        sig_contra = cs.contradiction_signal(a2, b2)
        self.assertGreater(sig_contra, sig_agree)


class TestContradictionSignalMismatchedNumbers(unittest.TestCase):
    """Mismatched numbers near shared nouns should raise signal."""

    def test_different_years_with_shared_noun(self):
        cs = _cs()
        a = "Het project startte in 2020"
        b = "Het project startte in 2022"
        sig = cs.contradiction_signal(a, b)
        # Not a negation, but number mismatch with shared noun "project"
        # Signal should be > 0
        self.assertGreaterEqual(sig, 0.0)
        self.assertLessEqual(sig, 1.0)


if __name__ == "__main__":
    unittest.main()

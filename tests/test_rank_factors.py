"""The decomposition harness must isolate what it claims to isolate.

TASK-160 attributes a recall loss to individual factors in `_rank.rerank` by
neutralising them one at a time. Two things make that claim trustworthy, and
both are mechanical enough to test: the patch has to actually neutralise the
named factor and restore it afterwards, and the all-neutral control has to be
able to detect an incomplete decomposition rather than assume completeness.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import _rank  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "rank_factors", str(REPO / "scripts" / "rank-factors.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M = _load()


class NeutralisedTest(unittest.TestCase):
    def test_the_named_factor_returns_one_inside_the_block(self):
        self.assertNotEqual(_rank.recency_factor(400, "feit"), 1.0)
        with M.Neutralised(["recency_factor"]):
            self.assertEqual(_rank.recency_factor(400, "feit"), 1.0)

    def test_it_restores_afterwards(self):
        """A leaked patch would silently corrupt every later arm and test."""
        before = _rank.recency_factor(400, "feit")
        with M.Neutralised(["recency_factor"]):
            pass
        self.assertEqual(_rank.recency_factor(400, "feit"), before)

    def test_it_restores_even_when_the_body_raises(self):
        before = _rank.importance_factor(5)
        with self.assertRaises(RuntimeError):
            with M.Neutralised(["importance_factor"]):
                raise RuntimeError("boom")
        self.assertEqual(_rank.importance_factor(5), before)

    def test_only_the_named_factor_moves(self):
        before = _rank.importance_factor(5)
        with M.Neutralised(["recency_factor"]):
            self.assertEqual(_rank.importance_factor(5), before)

    def test_an_unknown_name_is_ignored_rather_than_crashing(self):
        """An arm naming a factor that no longer exists must not take the run
        down; it should simply neutralise nothing."""
        with M.Neutralised(["factor_that_does_not_exist"]):
            pass

    def test_every_arm_names_only_real_factors(self):
        """A typo in an arm would silently measure production twice.

        `Neutralised` skips names it cannot find, which is the right runtime
        behaviour and exactly why the arm table needs checking here instead.
        """
        for arm, names in M.ARMS.items():
            for n in names:
                with self.subTest(arm=arm, factor=n):
                    self.assertTrue(hasattr(_rank, n),
                                    f"arm {arm} names a factor that does not exist: {n}")

    def test_the_all_neutral_arm_covers_every_other_arm(self):
        """The control is only a control if it neutralises everything the
        individual arms do."""
        union = set()
        for arm, names in M.ARMS.items():
            if arm not in ("all_neutral", "production"):
                union |= set(names)
        self.assertTrue(union <= set(M.ARMS["all_neutral"]),
                        "all_neutral is missing a factor that another arm neutralises")


class RecallsTest(unittest.TestCase):
    def test_counts_at_one_and_five(self):
        rows = [{"rank": 1}, {"rank": 3}, {"rank": 9}, {"rank": 0}]
        r = M.recalls(rows)
        self.assertEqual(r["recall@1"], 0.25)
        self.assertEqual(r["recall@5"], 0.5)

    def test_absent_never_counts(self):
        self.assertEqual(M.recalls([{"rank": 0}] * 4)["recall@5"], 0.0)


class PairedTest(unittest.TestCase):
    def test_it_matches_on_the_question_not_on_position(self):
        """Arms can drop a question (an embed failure), so matching by index
        would silently compare different questions to each other."""
        base = [{"q": "a", "rank": 9}, {"q": "b", "rank": 1}]
        arm = [{"q": "b", "rank": 1}, {"q": "a", "rank": 1}]
        r = M.paired(base, arm, 1)
        self.assertEqual((r["gained"], r["lost"]), (1, 0))

    def test_a_question_missing_from_the_baseline_is_skipped(self):
        base = [{"q": "a", "rank": 9}]
        arm = [{"q": "a", "rank": 1}, {"q": "unseen", "rank": 1}]
        r = M.paired(base, arm, 1)
        self.assertEqual((r["gained"], r["lost"]), (1, 0))


if __name__ == "__main__":
    unittest.main()

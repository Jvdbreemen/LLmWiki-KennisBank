"""The ceiling harness has to be right about what it is measuring.

TASK-138 is a measurement-first task, so the harness IS the deliverable. Two
things in it are easy to get subtly wrong and would produce a confident number
that means nothing: the ceiling arithmetic, and the paired test.

The ceiling is one probability, not four. A perfect reranker puts gold at rank 1
whenever gold is anywhere in the pool, so ceiling@1 and ceiling@5 are the same
number for a given pool size. Computing them separately would invite them to
disagree.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "rerank_ceiling", str(REPO / "scripts" / "rerank-ceiling.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M = _load()


class SplitTest(unittest.TestCase):
    def test_the_dev_split_reproduces_the_recorded_count(self):
        """856 of 1224, or the numbers do not sit beside the earlier work.

        The original dev.json is gone. The count reproducing exactly is what
        makes this the same split rule; question-level identity cannot be
        confirmed without that file, which the report says out loud.
        """
        questions = [{"q": f"q{i}", "expect": [f"m{i}"]} for i in range(1224)]
        self.assertEqual(len(M.split_questions(questions, "dev")), 856)
        self.assertEqual(len(M.split_questions(questions, "holdout")), 1224 - 856)
        self.assertEqual(len(M.split_questions(questions, "all")), 1224)

    def test_dev_and_holdout_do_not_overlap(self):
        questions = [{"q": f"q{i}", "expect": [f"m{i}"]} for i in range(1224)]
        dev = {q["q"] for q in M.split_questions(questions, "dev")}
        hold = {q["q"] for q in M.split_questions(questions, "holdout")}
        self.assertEqual(dev & hold, set())
        self.assertEqual(len(dev | hold), 1224)

    def test_the_split_is_stable_across_calls(self):
        questions = [{"q": f"q{i}", "expect": [f"m{i}"]} for i in range(100)]
        a = [q["q"] for q in M.split_questions(questions, "dev")]
        b = [q["q"] for q in M.split_questions(questions, "dev")]
        self.assertEqual(a, b, "a shifting split makes every comparison meaningless")


class GoldRankTest(unittest.TestCase):
    def test_absent_is_zero_not_a_large_rank(self):
        """0 has to mean absent, because every ceiling counts `0 < rank <= k`."""
        self.assertEqual(M.gold_rank(["a", "b"], ["c"]), 0)

    def test_one_based(self):
        self.assertEqual(M.gold_rank(["a", "b"], ["a"]), 1)
        self.assertEqual(M.gold_rank(["a", "b"], ["b"]), 2)

    def test_several_acceptable_answers_take_the_best_rank(self):
        """A reranker only has to surface one of them."""
        self.assertEqual(M.gold_rank(["a", "b", "c"], ["c", "b"]), 2)

    def test_a_bare_string_works_like_a_single_element_list(self):
        self.assertEqual(M.gold_rank(["a", "b"], "b"), 2)


class CeilingArithmeticTest(unittest.TestCase):
    def _rows(self, ranks, pool=50):
        return [{"q": f"q{i}", "rank": r, "rank_cos": r, "pool": pool,
                 "expect": ["x"], "type": ""} for i, r in enumerate(ranks)]

    def test_ceiling_at_1_equals_ceiling_at_5_for_the_same_pool(self):
        """The property the whole measurement rests on.

        A perfect reranker of the pool puts gold first whenever it is in the
        pool, so both numbers are P(gold in pool). If these ever disagree the
        harness is computing something other than a ceiling.
        """
        rows = self._rows([1, 3, 7, 0, 20, 45])
        s = M.summarise(rows, 50)
        self.assertEqual(s["ceiling"]["50"], round(5 / 6, 4))

    def test_the_ceiling_grows_with_the_pool_and_never_shrinks(self):
        rows = self._rows([1, 3, 7, 0, 20, 45])
        s = M.summarise(rows, 50)
        self.assertLessEqual(s["ceiling"]["5"], s["ceiling"]["20"])
        self.assertLessEqual(s["ceiling"]["20"], s["ceiling"]["50"])

    def test_baseline_recall_at_5_equals_the_top_5_ceiling(self):
        """Not a coincidence: both are 'gold within the first five'."""
        rows = self._rows([1, 3, 7, 0, 20])
        s = M.summarise(rows, 50)
        self.assertEqual(s["baseline"]["recall@5"], s["ceiling"]["5"])

    def test_pool_size_is_reported_because_the_floor_can_bind(self):
        """A top-50 ceiling measured on pools of 12 is a number production
        can never reach, so the pool size travels with it."""
        rows = self._rows([1, 2], pool=12)
        s = M.summarise(rows, 50)
        self.assertEqual(s["pool_size"]["median"], 12)
        self.assertEqual(s["pool_size"]["at_requested"], 0)

    def test_absent_is_counted_separately(self):
        rows = self._rows([1, 0, 0, 4])
        self.assertEqual(M.summarise(rows, 50)["absent_from_pool"], 2)


class McNemarTest(unittest.TestCase):
    def test_no_discordant_pairs_is_p_one(self):
        rows = [{"rank": 1, "rank_cos": 1}, {"rank": 9, "rank_cos": 9}]
        r = M.mcnemar(rows, 5)
        self.assertEqual((r["gained"], r["lost"], r["p"]), (0, 0, 1.0))

    def test_it_counts_both_directions(self):
        """An arm that gains five and loses four is not a win, and an average
        would report it as one."""
        rows = [{"rank": 9, "rank_cos": 1}] * 5 + [{"rank": 1, "rank_cos": 9}] * 4
        r = M.mcnemar(rows, 5)
        self.assertEqual((r["gained"], r["lost"]), (5, 4))
        self.assertGreater(r["p"], 0.5, "5 against 4 is not an effect")

    def test_a_one_sided_result_is_significant(self):
        rows = [{"rank": 9, "rank_cos": 1}] * 20
        r = M.mcnemar(rows, 5)
        self.assertEqual((r["gained"], r["lost"]), (20, 0))
        self.assertLess(r["p"], 0.001)

    def test_the_threshold_k_is_respected(self):
        """A move from rank 9 to rank 3 is a gain at k=5 and not at k=1."""
        rows = [{"rank": 9, "rank_cos": 3}]
        self.assertEqual(M.mcnemar(rows, 5)["gained"], 1)
        self.assertEqual(M.mcnemar(rows, 1)["gained"], 0)


if __name__ == "__main__":
    unittest.main()

"""Development-only applicability controls; no spent holdout thresholds."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import _experience_applicability as app


class ApplicabilityTest(unittest.TestCase):
    def test_common_question_words_do_not_supply_lexical_evidence(self):
        self.assertEqual(app.terms('Wat hebben we toen gedaan en waarom werkte het?'), set())
        self.assertEqual(app.lexical_score('Hoe werkte dit voor de database?',
                                         {'lesson': 'Dit werkte voor de recorder.'}), 0)

    def test_query_identifier_and_digits_are_retained(self):
        self.assertIn('sqlite', app.terms('SQLite timeout 250 ms'))
        self.assertIn('250', app.terms('SQLite timeout 250 ms'))

    def test_lexical_score_is_query_support_not_a_rank_number(self):
        record = {'lesson': 'SQLite timeout lock', 'score': 999, 'confidence': 1}
        self.assertEqual(app.lexical_score('SQLite timeout lock', record), 1)
        self.assertEqual(app.lexical_score('PostgreSQL concurrency', record), 0)

    def test_empty_or_missing_class_cannot_select_a_policy(self):
        for rows in ([], [{'id': 'x', 'expected_experience': 'a',
                           'candidates': [{'id': 'a', 'score': 1}]}]):
            self.assertIsNone(app.select_threshold(rows, thresholds=[.5])['selected_threshold'])

    def test_development_must_keep_both_recall_and_specificity(self):
        rows = [
            {'id': 'p', 'expected_experience': 'a', 'candidates': [{'id': 'a', 'score': .6}]},
            {'id': 'n', 'expected_experience': None, 'candidates': [{'id': 'a', 'score': .7}]},
        ]
        result = app.select_threshold(rows, thresholds=[.5, .65, .8])
        self.assertIsNone(result['selected_threshold'])

    def test_failure_is_not_a_correct_abstention(self):
        rows = [{'id': 'n', 'expected_experience': None, 'candidates': [], 'status': 'unavailable'}]
        result = app.measure(rows, .5)
        self.assertEqual(result['negative_no_hit_specificity'], 0)
        self.assertEqual(result['failed'], 1)

    def test_threshold_is_selected_from_development_not_hardcoded(self):
        rows = [
            {'id': 'p', 'expected_experience': 'a', 'candidates': [{'id': 'a', 'score': .8}]},
            {'id': 'n', 'expected_experience': None, 'candidates': [{'id': 'a', 'score': .4}]},
        ]
        self.assertEqual(app.select_threshold(rows, thresholds=[.3, .6, .9])['selected_threshold'], .6)

    def test_nonfinite_scores_and_thresholds_are_rejected(self):
        with self.assertRaises(ValueError):
            app.select_threshold([], thresholds=[math.nan])
        with self.assertRaises(ValueError):
            app.measure([{'id': 'n', 'candidates': [{'id': 'a', 'score': math.inf}]}], .5)

    def test_independence_checks_structured_refs_by_path_not_offset(self):
        a = [{'id': 'a', 'query': 'first', 'source_refs': [{'source_path': '01-raw/sessies/a.md', 'start': 0}]}]
        b = [{'id': 'b', 'query': 'second', 'source_refs': [{'source_path': '01-raw/sessies/a.md', 'start': 200}]}]
        with self.assertRaises(ValueError):
            app.assert_independent(a, b)

    def test_near_identical_queries_not_independent(self):
        with self.assertRaises(ValueError):
            app.assert_independent([{'id': 'a', 'query': 'SQLite TIMEOUT?'}],
                                   [{'id': 'b', 'query': 'sqlite timeout'}])


if __name__ == '__main__':
    unittest.main()

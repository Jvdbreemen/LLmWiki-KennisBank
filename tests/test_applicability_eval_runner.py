"""Validate scorer inputs and semantic-judge output before running experiments."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('app_eval', ROOT / 'scripts/evaluate-experience-applicability.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ApplicabilityRunnerTest(unittest.TestCase):
    def test_judge_must_cover_every_candidate_exactly(self):
        self.assertEqual(mod.parse_judgments('{"a":true,"b":false}', ['a', 'b']), [1., 0.])
        for bad in ('{"a":true}', '{"a":true,"b":false,"invented":true}',
                    '{"a":"true","b":false}', '{"a":true,"a":false,"b":true}'):
            with self.assertRaises(ValueError):
                mod.parse_judgments(bad, ['a', 'b'])

    def test_scoring_text_excludes_refs_and_human_acceptance_metadata(self):
        text = mod.scoring_text({'lesson': 'Use timeout', 'applicability': 'network calls',
                                'source_refs': [{'source_path': 'private.md'}],
                                'review_state': 'accepted', 'confidence': 1})
        self.assertIn('Use timeout', text)
        self.assertNotIn('private.md', text)
        self.assertNotIn('accepted', text)

    def test_empty_query_does_not_become_a_valid_case(self):
        with self.assertRaises(ValueError):
            mod.validate_cases([{'id': 'a', 'query': '', 'expected_experience': None}], [])

    def test_expected_experience_must_exist_in_fixture_corpus(self):
        with self.assertRaises(ValueError):
            mod.validate_cases([{'id': 'a', 'query': 'Where?', 'expected_experience': 'missing'}], [])

    def test_snapshot_of_record_text_has_unambiguous_field_boundaries(self):
        a = mod.scoring_text({'lesson': 'ab', 'applicability': 'c'})
        b = mod.scoring_text({'lesson': 'a', 'applicability': 'bc'})
        self.assertNotEqual(a, b)

    def test_nested_case_score_map_covers_every_corpus_record(self):
        cases = [{'id': 'case-a', 'query': 'timeout',
                  'expected_experience': 'experience-a', 'polarity': 'positive'}]
        records = [{'experience_id': 'experience-a', 'lesson': 'timeout'},
                   {'experience_id': 'experience-b', 'lesson': 'other'}]
        rows = mod.observations_from_scores(
            cases, records,
            {'case-a': {'experience-a': .9, 'experience-b': .1}})
        self.assertEqual(rows[0]['candidates'][0]['id'], 'experience-a')
        self.assertEqual(rows[0]['candidates'][1]['score'], .1)

    def test_embedding_score_map_rejects_missing_or_incompatible_vectors(self):
        cases = [{'id': 'case-a', 'query': 'timeout',
                  'expected_experience': 'experience-a', 'polarity': 'positive'}]
        records = [{'experience_id': 'experience-a', 'lesson': 'timeout'}]

        def fake_embed(text, *, kind):
            return [1., 0.] if kind == 'query' else [1., 0.]

        scores, info = mod.embedding_scores(cases, records, fake_embed)
        self.assertEqual(scores['case-a']['experience-a'], 1.)
        self.assertEqual(info['failed'], [])

        def bad_embed(text, *, kind):
            return [1.] if kind == 'doc' else [1., 0.]

        with self.assertRaises(ValueError):
            mod.embedding_scores(cases, records, bad_embed)


if __name__ == '__main__':
    unittest.main()

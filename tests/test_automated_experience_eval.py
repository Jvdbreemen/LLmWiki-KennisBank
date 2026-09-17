"""Check evaluation denominators, exact legacy conversion and isolation."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('automated_eval', ROOT / 'scripts/dev/evaluate-experience-regression.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class AutomatedExperienceEvalTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / '01-raw/sessies/example.md'
        self.path.parent.mkdir(parents=True)
        self.raw = 'eerste\r\ntweede é\r\n'.encode('utf-8')
        self.path.write_bytes(self.raw)

    def legacy(self, digest=None):
        digest = digest or hashlib.sha256(self.raw).hexdigest()
        return '01-raw/sessies/example.md#7:13@sha256:' + digest

    def test_legacy_uses_frozen_hash_and_normalized_old_offsets(self):
        ref = mod.convert_ref(self.root, self.legacy())
        import _source_ref
        result = _source_ref.resolve_source_ref(self.root, ref)
        self.assertEqual(result['status'], 'valid')
        self.assertEqual(result['passage'], 'tweede')
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_changed_source_is_rejected_not_rebound(self):
        with self.assertRaises(ValueError):
            mod.convert_ref(self.root, self.legacy('0' * 64))

    def test_traversal_rejected(self):
        with self.assertRaises(ValueError):
            mod.convert_ref(self.root, '../secret.md#0:1@sha256:' + '0' * 64)

    def test_missing_expected_hit_stays_in_denominator(self):
        cases = [{'expected_experience': 'a'}, {'expected_experience': 'b'}, {'expected_experience': None}]
        result = mod.metrics(cases, [['a'], [], ['a']], [1, 2, 3])
        self.assertEqual(result['hit_at_3'], 0.5)
        self.assertEqual(result['negative_no_hit_specificity'], 0)

    def test_zero_cases_never_pass(self):
        result = mod.metrics([], [], [])
        self.assertIsNone(result['hit_at_3'])
        self.assertIsNone(result['negative_no_hit_specificity'])
        self.assertIsNone(result['p95_ms'])

    def test_failed_call_is_not_a_correct_negative(self):
        result = mod.metrics([{'expected_experience': None}], [[]], [3], ['unavailable'])
        self.assertEqual(result['negative_no_hit_specificity'], 0)
        self.assertEqual(result['unavailable'], 1)

    def test_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            mod.metrics([{'expected_experience': 'a'}], [], [])

    def test_output_cannot_be_repository_or_owner_root(self):
        with self.assertRaises(ValueError):
            mod.validate_output(ROOT / 'scratch', self.root)
        with self.assertRaises(ValueError):
            mod.validate_output(self.root, self.root)

    def test_existing_private_run_is_not_overwritten(self):
        output = self.root / '06-claude/evaluations/already-run'
        output.mkdir(parents=True)
        with self.assertRaises(ValueError):
            mod.validate_output(output, self.root)

    def test_wiki_is_not_silently_accepted_as_raw_evidence(self):
        with self.assertRaises(ValueError):
            mod.convert_ref(self.root, '02-wiki/derived.md#0:1@sha256:' + '0' * 64)

    def test_unicode_and_internal_newline_offsets(self):
        import _source_ref
        digest = hashlib.sha256(self.raw).hexdigest()
        ref = mod.convert_ref(self.root, '01-raw/sessies/example.md#4:15@sha256:' + digest)
        result = _source_ref.resolve_source_ref(self.root, ref)
        self.assertEqual(result['passage'], 'te\r\ntweede é')

    def test_readonly_database_connection_rejects_writes(self):
        database = self.root / 'owner.db'
        conn = sqlite3.connect(database)
        try:
            conn.execute('CREATE TABLE protected(value)')
            conn.commit()
        finally:
            conn.close()
        conn = mod.readonly(database)
        self.addCleanup(conn.close)
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute('INSERT INTO protected VALUES (1)')


if __name__ == '__main__':
    unittest.main()

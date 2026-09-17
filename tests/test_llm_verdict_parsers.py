"""conflict-triage and verify-wiki read an LLM verdict through _llmjson.

Both took the span from the first "{" to the last "}". A model that adds a
remark with braces after its answer then makes that span invalid JSON, the
verdict is thrown away, and a paid call is retried for nothing. _llmjson takes
the first complete object instead (TASK-189, WideSpanGuardTest).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script  # noqa: E402


class ConflictTriageVerdictTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_script("conflict-triage.py")

    def test_prose_with_braces_after_the_verdict_does_not_break_it(self):
        raw = ('{"tegenspraak": true, "citaat_a": "x", "citaat_b": "y"}\n'
               "Toelichting: zie {artikel A} en {artikel B}.")
        self.assertIs(self.mod.parse_verdict(raw)["tegenspraak"], True)

    def test_a_fenced_verdict_still_parses(self):
        raw = '```json\n{"tegenspraak": false}\n```'
        self.assertIs(self.mod.parse_verdict(raw)["tegenspraak"], False)

    def test_no_object_and_a_wrong_field_stay_loud(self):
        with self.assertRaises(ValueError):
            self.mod.parse_verdict("Ik weet het niet.")
        with self.assertRaises(ValueError):
            self.mod.parse_verdict('{"tegenspraak": "ja"}')


class VerifyWikiVerdictTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_script("verify-wiki.py")

    def test_prose_with_braces_after_the_verdict_does_not_break_it(self):
        raw = '{"verdict": "ok", "claims": []}\nNB: {geen} opmerkingen.'
        self.assertEqual(self.mod.parse_verdict(raw)["verdict"], "ok")

    def test_no_object_and_a_wrong_shape_stay_loud(self):
        with self.assertRaises(ValueError):
            self.mod.parse_verdict("geen json hier")
        with self.assertRaises(ValueError):
            self.mod.parse_verdict('{"verdict": "misschien", "claims": []}')
        with self.assertRaises(ValueError):
            self.mod.parse_verdict('{"verdict": "ok", "claims": "geen"}')


if __name__ == "__main__":
    unittest.main()

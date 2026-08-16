"""The judge-model sweep must parse what production parses (TASK-189).

Its three parse_* functions claimed to mirror production seams but kept the
wide find/rfind span after production moved to _llmjson — so the sweep
scored candidate models against a STRICTER parser than production runs,
deflating parse_ok_pct and steering model choice on wrong data. Each test
asserts the sweep's verdict on a raw response production demonstrably
accepts.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tests._loader import load_script  # noqa: E402


class SweepParsersMatchProductionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_script("judge-model-sweep.py")

    def test_parse_reconcile_accepts_what_production_accepts(self):
        raw = ('{"action": "SUPERSEDE", "reason": "nieuwer"}\n'
               'Toelichting: het oude {feit} klopt niet.')
        import _llmjson
        self.assertEqual((_llmjson.first_object(raw) or {}).get("action"),
                         "SUPERSEDE")  # production baseline on the same raw
        self.assertEqual(self.m.parse_reconcile(raw), ("SUPERSEDE", "ok"))

    def test_parse_judge_accepts_trailing_prose(self):
        raw = ('{"verdict": "current", "importance": 4}\n'
               'Ik twijfelde tussen {a} en {b}.')
        self.assertEqual(self.m.parse_judge(raw),
                         ({"verdict": "current", "importance": 4}, "ok"))

    def test_parse_extract_accepts_trailing_prose_with_bracket(self):
        raw = ('[{"title": "T", "body": "B"}]\n'
               'Meer [details] vond ik niet.')
        items, status = self.m.parse_extract(raw)
        self.assertEqual(status, "ok")
        self.assertEqual(len(items), 1)

    def test_parse_reconcile_still_reports_the_fallback(self):
        """The harness scores the raw response, never the fail-safe."""
        self.assertEqual(self.m.parse_reconcile("ik weet het niet"),
                         (None, "unparseable"))
        self.assertEqual(self.m.parse_reconcile(""), (None, "empty"))
        self.assertEqual(self.m.parse_reconcile('{"reason": "x"}'),
                         (None, "no_action_field"))


if __name__ == "__main__":
    unittest.main()

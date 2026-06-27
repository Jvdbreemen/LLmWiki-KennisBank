"""Tests voor scripts/_extract.py - de extractie-seam. _llm.generate gemockt."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import unittest
import _extract  # noqa: E402
import _llm  # noqa: E402


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self._orig = _llm.generate

    def tearDown(self):
        _llm.generate = self._orig

    def test_extracts_candidates(self):
        _llm.generate = lambda *a, **k: (
            '[{"title": "Bug in auth", "body": "Token-expiry gebruikte < i.p.v. <="},'
            ' {"title": "Besluit DB", "body": "Sqlite gekozen om lokaliteit"}]')
        out = _extract.extract_candidates("lange transcript tekst ...")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["title"], "Bug in auth")
        self.assertIn("body", out[1])

    def test_none_is_empty(self):
        _llm.generate = lambda *a, **k: None
        self.assertEqual(_extract.extract_candidates("x"), [])

    def test_unparseable_is_empty(self):
        _llm.generate = lambda *a, **k: "geen json"
        self.assertEqual(_extract.extract_candidates("x"), [])

    def test_filters_empty_bodies_and_caps(self):
        items = ",".join('{"title": "T%d", "body": "voldoende lange inhoud %d"}' % (i, i)
                         for i in range(20))
        _llm.generate = lambda *a, **k: "[" + items + ',{"title":"leeg","body":""}]'
        out = _extract.extract_candidates("x", max_n=5)
        self.assertLessEqual(len(out), 5)
        self.assertTrue(all(c["body"].strip() for c in out))


if __name__ == "__main__":
    unittest.main()

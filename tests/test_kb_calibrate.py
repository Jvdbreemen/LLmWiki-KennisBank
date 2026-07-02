"""Tests voor scripts/kb-calibrate.py - drempel-kalibratie (pure functies)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._loader import load_script


def _kc():
    return load_script("kb-calibrate.py")


def _pair(label, score):
    return {"label": label, "score": score}


class TestCalibrate(unittest.TestCase):
    def setUp(self):
        self.kc = _kc()

    def test_clean_separation(self):
        scored = [
            _pair("duplicate", 0.95), _pair("duplicate", 0.93),
            _pair("related", 0.80), _pair("related", 0.72),
            _pair("unrelated", 0.40), _pair("unrelated", 0.30),
        ]
        r = self.kc.calibrate(scored)
        dup = r["duplicate_boundary"]
        self.assertTrue(dup["clean"])
        self.assertEqual(dup["suggested"], round((0.93 + 0.80) / 2, 3))
        rel = r["related_boundary"]
        self.assertTrue(rel["clean"])
        self.assertEqual(rel["suggested"], round((0.72 + 0.40) / 2, 3))

    def test_overlap_flagged(self):
        scored = [
            _pair("duplicate", 0.85),   # onder de hoogste related -> overlap
            _pair("related", 0.88),
            _pair("unrelated", 0.30),
        ]
        r = self.kc.calibrate(scored)
        self.assertFalse(r["duplicate_boundary"]["clean"])
        self.assertLess(r["duplicate_boundary"]["margin"], 0)

    def test_missing_class_raises(self):
        with self.assertRaises(ValueError):
            self.kc.calibrate([_pair("duplicate", 0.9), _pair("related", 0.7)])

    def test_knob_report_flags_misaligned(self):
        scored = [
            _pair("duplicate", 0.98), _pair("related", 0.60),
            _pair("unrelated", 0.20),
        ]
        r = self.kc.calibrate(scored)
        lines = self.kc.knob_report(r)
        self.assertEqual(len(lines), len(self.kc.CURRENT_KNOBS))
        # dedup 0.92 ligt boven de geijkte duplicate-grens (0.79) -> OK
        self.assertIn("OK", lines[0])


class TestLoadSet(unittest.TestCase):
    def setUp(self):
        self.kc = _kc()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _write(self, obj) -> Path:
        p = Path(self.tmp.name) / "set.json"
        p.write_text(json.dumps(obj), encoding="utf-8")
        return p

    def test_valid_loads(self):
        p = self._write([{"a": "x", "b": "y", "label": "duplicate"}])
        self.assertEqual(len(self.kc.load_set(p)), 1)

    def test_bad_label_rejected(self):
        with self.assertRaises(ValueError):
            self.kc.load_set(self._write([{"a": "x", "b": "y", "label": "soortgelijk"}]))

    def test_missing_text_rejected(self):
        with self.assertRaises(ValueError):
            self.kc.load_set(self._write([{"a": "x", "label": "duplicate"}]))


if __name__ == "__main__":
    unittest.main()

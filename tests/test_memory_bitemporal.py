"""Tests voor het bi-temporele frontmatter-contract in scripts/_memory.py.

valid_from (event-tijd) en valid_until (sluiting) in render() en set_status().
Vault naar temp; geen model.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _memory  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402


class TestRenderBitemporal(unittest.TestCase):
    def test_valid_from_defaults_to_created(self):
        out = _memory.render("t", "b", created="2026-06-30")
        fm, _ = parse_frontmatter(out)
        self.assertEqual(fm.get("valid_from"), "2026-06-30")

    def test_explicit_valid_from_wins(self):
        out = _memory.render("t", "b", created="2026-06-30", valid_from="2026-06-25")
        fm, _ = parse_frontmatter(out)
        self.assertEqual(fm.get("valid_from"), "2026-06-25")
        self.assertEqual(fm.get("created"), "2026-06-30")

    def test_valid_until_absent_by_default(self):
        out = _memory.render("t", "b")
        fm, _ = parse_frontmatter(out)
        self.assertNotIn("valid_until", fm)

    def test_valid_until_rendered_when_given(self):
        out = _memory.render("t", "b", valid_until="2026-07-01")
        fm, _ = parse_frontmatter(out)
        self.assertEqual(fm.get("valid_until"), "2026-07-01")


class TestSetStatusValidUntil(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = self.tmp.name
        self.addCleanup(self._restore)

    def _restore(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        self.tmp.cleanup()

    def _write(self, **kw) -> Path:
        p = Path(self.tmp.name) / "m.md"
        p.write_text(_memory.render("t", "b", **kw), encoding="utf-8")
        return p

    def test_set_status_stamps_new_valid_until(self):
        p = self._write(status="current")
        ok = _memory.set_status(p, "superseded", superseded_by=["nieuw"],
                                valid_until="2026-06-25")
        self.assertTrue(ok)
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        self.assertEqual(fm.get("status"), "superseded")
        self.assertEqual(fm.get("valid_until"), "2026-06-25")
        self.assertIn("nieuw", str(fm.get("superseded_by", "")))

    def test_set_status_replaces_existing_valid_until(self):
        p = self._write(status="current", valid_until="2026-01-01")
        ok = _memory.set_status(p, "expired", valid_until="2026-06-25")
        self.assertTrue(ok)
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        self.assertEqual(fm.get("valid_until"), "2026-06-25")
        # geen dubbele valid_until-regel
        raw = p.read_text(encoding="utf-8")
        self.assertEqual(raw.count("valid_until:"), 1)

    def test_set_status_without_valid_until_leaves_frontmatter_clean(self):
        p = self._write(status="current")
        ok = _memory.set_status(p, "retracted")
        self.assertTrue(ok)
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        self.assertNotIn("valid_until", fm)

    def test_body_never_touched(self):
        p = self._write(status="current")
        before_body = parse_frontmatter(p.read_text(encoding="utf-8"))[1]
        _memory.set_status(p, "superseded", valid_until="2026-06-25")
        after_body = parse_frontmatter(p.read_text(encoding="utf-8"))[1]
        self.assertEqual(before_body, after_body)

    def test_backslash_in_valid_until_does_not_crash(self):
        # re.sub met een string-replacement zou re.PatternError gooien op
        # "\x"; de lambda-replacement schrijft de waarde letterlijk.
        p = self._write(status="current", valid_until="2026-01-01")
        ok = _memory.set_status(p, "expired", valid_until=r"2000-01-01\x")
        self.assertTrue(ok)
        self.assertIn(r"valid_until: 2000-01-01\x", p.read_text(encoding="utf-8"))

    def test_backslash_in_superseded_by_does_not_crash(self):
        p = self._write(status="current")
        _memory.set_status(p, "superseded", superseded_by=[r"pad\met\backslash"])
        p2 = self._write(status="current", superseded_by=["oud"])
        ok = _memory.set_status(p2, "superseded", superseded_by=[r"nieuw\x"])
        self.assertTrue(ok)


class TestMemoryType(unittest.TestCase):
    def test_default_type_is_feit(self):
        fm, _ = parse_frontmatter(_memory.render("t", "b"))
        self.assertEqual(fm.get("memory_type"), "feit")

    def test_explicit_type_rendered(self):
        fm, _ = parse_frontmatter(_memory.render("t", "b", memory_type="beslissing"))
        self.assertEqual(fm.get("memory_type"), "beslissing")

    def test_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            _memory.render("t", "b", memory_type="smalltalk")

    def test_coerce_valid_passthrough(self):
        self.assertEqual(_memory.coerce_memory_type("Voorkeur"), "voorkeur")

    def test_coerce_invalid_falls_back_to_feit(self):
        self.assertEqual(_memory.coerce_memory_type("nonsense"), "feit")
        self.assertEqual(_memory.coerce_memory_type(None), "feit")
        self.assertEqual(_memory.coerce_memory_type(""), "feit")


if __name__ == "__main__":
    unittest.main()

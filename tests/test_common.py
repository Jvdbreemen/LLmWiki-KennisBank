"""Tests for scripts/_common.py — the shared importer helpers.

_common.py has no hyphen so it is importable once scripts/ is on sys.path.
These tests pin the behaviour that was previously duplicated verbatim across
import-folder.py, import-claudeai-export.py and import-cc-history.py, so the
de-duplication stays byte-faithful.
"""
from __future__ import annotations

import io
import json
import re
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _common  # noqa: E402


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_common.slugify("Hello World"), "hello-world")

    def test_punctuation_dropped(self):
        self.assertEqual(_common.slugify("hello, world!"), "hello-world")

    def test_underscores_and_runs_collapse(self):
        self.assertEqual(_common.slugify("a _ - _ b"), "a-b")

    def test_empty_and_only_punct_return_untitled(self):
        self.assertEqual(_common.slugify(""), "untitled")
        self.assertEqual(_common.slugify("   "), "untitled")
        self.assertEqual(_common.slugify("!!!"), "untitled")
        self.assertEqual(_common.slugify(None), "untitled")

    def test_max_len_truncates_and_strips_trailing_dash(self):
        out = _common.slugify("abcde fghij klmno", max_len=6)
        self.assertLessEqual(len(out), 6)
        self.assertFalse(out.endswith("-"))

    def test_unicode_preserved(self):
        self.assertEqual(_common.slugify("café crème"), "café-crème")


class TestTimeHelpers(unittest.TestCase):
    def test_utcnow_iso_format(self):
        # YYYY-MM-DDTHH:MM:SSZ
        self.assertRegex(
            _common._utcnow_iso(),
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        )

    def test_today_iso_format(self):
        self.assertRegex(_common._today_iso(), r"^\d{4}-\d{2}-\d{2}$")

    def test_today_iso_is_date_prefix_of_utcnow(self):
        # Both derive from the same UTC clock; the date must agree.
        self.assertEqual(_common._today_iso(), _common._utcnow_iso()[:10])


class TestPrintSummary(unittest.TestCase):
    SUMMARY = {
        "imported": 2,
        "skipped": 1,
        "errors": 0,
        "files": ["/tmp/a.md", "/tmp/b.md"],
        "errors_detail": [],
    }

    def _capture(self, as_json: bool) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            _common.print_summary(self.SUMMARY, as_json)
        return buf.getvalue()

    def test_text_summary_line(self):
        out = self._capture(False)
        self.assertEqual(
            out,
            "--- summary: imported=2 skipped=1 errors=0\n",
        )

    def test_json_summary_roundtrips(self):
        out = self._capture(True)
        # Faithful to the old inline json.dumps(indent=2, ensure_ascii=False).
        self.assertEqual(out, json.dumps(self.SUMMARY, indent=2, ensure_ascii=False) + "\n")
        self.assertEqual(json.loads(out), self.SUMMARY)


class TestImportersUseCommon(unittest.TestCase):
    """The three importers must source these helpers from _common, not redefine."""

    IMPORTERS = (
        "import-folder.py",
        "import-claudeai-export.py",
        "import-cc-history.py",
    )

    def test_no_local_redefinition_and_shared_import(self):
        for name in self.IMPORTERS:
            src = (SCRIPTS_DIR / name).read_text(encoding="utf-8")
            for helper in ("slugify", "_utcnow_iso", "_today_iso"):
                self.assertIsNone(
                    re.search(rf"^def {helper}\(", src, re.MULTILINE),
                    f"{name} still defines a local {helper}",
                )
            self.assertIn(
                "from _common import", src, f"{name} does not import from _common"
            )


if __name__ == "__main__":
    unittest.main()

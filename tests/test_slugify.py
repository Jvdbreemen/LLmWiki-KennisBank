"""Tests for slugify(), loaded from a hyphenated importer via importlib.

slugify is defined identically in import-cc-history.py, import-claudeai-export.py
and import-folder.py. We load one importer (import-claudeai-export.py) by path
and test its slugify; the other copies are byte-identical.
"""
from __future__ import annotations

import unittest

from _loader import load_script


class TestSlugify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script("import-claudeai-export.py")
        cls.slugify = staticmethod(cls.mod.slugify)

    def test_lowercases(self):
        self.assertEqual(self.slugify("Hello World"), "hello-world")
        self.assertEqual(self.slugify("CamelCase"), "camelcase")

    def test_non_alnum_becomes_hyphen(self):
        self.assertEqual(self.slugify("a b c"), "a-b-c")
        self.assertEqual(self.slugify("under_score"), "under-score")

    def test_punctuation_dropped(self):
        # Punctuation that is not word/space/hyphen is removed, not hyphenated.
        self.assertEqual(self.slugify("hello, world!"), "hello-world")
        self.assertEqual(self.slugify("what?: now."), "what-now")

    def test_collapse_repeated_separators(self):
        self.assertEqual(self.slugify("a   b"), "a-b")
        self.assertEqual(self.slugify("a---b"), "a-b")
        self.assertEqual(self.slugify("a _ - _ b"), "a-b")

    def test_trim_leading_trailing_hyphens(self):
        self.assertEqual(self.slugify("  spaced out  "), "spaced-out")
        self.assertEqual(self.slugify("---edge---"), "edge")

    def test_empty_and_pure_punctuation_fall_back_to_untitled(self):
        self.assertEqual(self.slugify(""), "untitled")
        self.assertEqual(self.slugify("   "), "untitled")
        self.assertEqual(self.slugify("!!!"), "untitled")
        self.assertEqual(self.slugify(None), "untitled")

    def test_max_len_truncation_without_trailing_hyphen(self):
        out = self.slugify("a" * 80, max_len=10)
        self.assertEqual(out, "a" * 10)
        # Truncation must not leave a trailing hyphen.
        out2 = self.slugify("abcde fghij klmno", max_len=6)
        self.assertFalse(out2.endswith("-"))
        self.assertLessEqual(len(out2), 6)

    def test_unicode_word_chars_preserved(self):
        # \w with re.UNICODE keeps accented letters.
        self.assertEqual(self.slugify("café crème"), "café-crème")


if __name__ == "__main__":
    unittest.main()

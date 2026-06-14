"""Tests for scripts/_frontmatter.py (split_frontmatter / parse_frontmatter).

_frontmatter.py has no hyphen so it is importable once scripts/ is on sys.path.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import _frontmatter  # noqa: E402


class TestSplitFrontmatter(unittest.TestCase):
    def test_basic_split(self):
        doc = "---\ntitle: Hello\ntype: note\n---\nBody line one.\nBody line two.\n"
        fm, body = _frontmatter.split_frontmatter(doc)
        self.assertEqual(fm, "title: Hello\ntype: note")
        self.assertEqual(body, "Body line one.\nBody line two.\n")

    def test_no_frontmatter_returns_text_unchanged(self):
        doc = "Just a body.\nNo frontmatter here.\n"
        fm, body = _frontmatter.split_frontmatter(doc)
        self.assertEqual(fm, "")
        self.assertEqual(body, doc)

    def test_opening_fence_but_no_closing_fence(self):
        # Starts with --- but never closes: treated as having no frontmatter.
        doc = "---\ntitle: dangling\nstill in limbo\n"
        fm, body = _frontmatter.split_frontmatter(doc)
        self.assertEqual(fm, "")
        self.assertEqual(body, doc)

    def test_horizontal_rule_in_body_not_treated_as_delimiter(self):
        # The review's false-positive case: a body line of "---" (a markdown
        # horizontal rule) must NOT be parsed as the closing fence.
        doc = (
            "---\n"
            "title: Real Frontmatter\n"
            "---\n"
            "Intro paragraph.\n"
            "\n"
            "---\n"  # horizontal rule in the body
            "\n"
            "Section after the rule.\n"
        )
        fm, body = _frontmatter.split_frontmatter(doc)
        self.assertEqual(fm, "title: Real Frontmatter")
        # The horizontal rule must still be present in the body, untouched.
        self.assertIn("Intro paragraph.", body)
        self.assertIn("---", body)
        self.assertIn("Section after the rule.", body)


class TestParseFrontmatter(unittest.TestCase):
    def test_scalar_fields(self):
        doc = "---\ntitle: Hello World\ntype: raw-sessie\nstatus: raw\n---\nbody\n"
        data, body = _frontmatter.parse_frontmatter(doc)
        self.assertEqual(data["title"], "Hello World")
        self.assertEqual(data["type"], "raw-sessie")
        self.assertEqual(data["status"], "raw")
        self.assertEqual(body, "body\n")

    def test_quoted_values_have_quotes_stripped(self):
        doc = "---\ntitle: \"Quoted Title\"\nother: 'single quoted'\n---\nbody\n"
        data, _ = _frontmatter.parse_frontmatter(doc)
        self.assertEqual(data["title"], "Quoted Title")
        self.assertEqual(data["other"], "single quoted")

    def test_list_field(self):
        doc = "---\ntags: [claude-sessie, import-claudeai, wiki]\n---\nbody\n"
        data, _ = _frontmatter.parse_frontmatter(doc)
        self.assertEqual(data["tags"], ["claude-sessie", "import-claudeai", "wiki"])

    def test_list_field_with_quoted_items(self):
        doc = "---\ntags: ['one', \"two\", three]\n---\nbody\n"
        data, _ = _frontmatter.parse_frontmatter(doc)
        self.assertEqual(data["tags"], ["one", "two", "three"])

    def test_missing_frontmatter_returns_empty_dict(self):
        doc = "No frontmatter at all.\nSecond line.\n"
        data, body = _frontmatter.parse_frontmatter(doc)
        self.assertEqual(data, {})
        self.assertEqual(body, doc)

    def test_comment_and_blank_lines_skipped(self):
        doc = "---\n# a comment\n\ntitle: Kept\n---\nbody\n"
        data, _ = _frontmatter.parse_frontmatter(doc)
        self.assertEqual(data, {"title": "Kept"})

    def test_horizontal_rule_in_body_does_not_corrupt_parse(self):
        # Regression: parse_frontmatter must read only the real frontmatter and
        # leave the body (including a "---" horizontal rule) intact.
        doc = (
            "---\n"
            "title: Doc\n"
            "tags: [a, b]\n"
            "---\n"
            "First paragraph.\n"
            "\n"
            "---\n"
            "\n"
            "Last paragraph.\n"
        )
        data, body = _frontmatter.parse_frontmatter(doc)
        self.assertEqual(data["title"], "Doc")
        self.assertEqual(data["tags"], ["a", "b"])
        self.assertIn("First paragraph.", body)
        self.assertIn("---", body)
        self.assertIn("Last paragraph.", body)


if __name__ == "__main__":
    unittest.main()

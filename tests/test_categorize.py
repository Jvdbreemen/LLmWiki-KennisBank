"""Tests for categorize() in build-karpathy-index.py (loaded via importlib).

categorize(filename, fm, language) -> (category_name, is_memory_snapshot).
Priority: (1) frontmatter `category`, (2) tag-match against CATEGORY_RULES,
(3) filename-prefix hint, (4) Overig (nl) / Other (en).
"""
from __future__ import annotations

import unittest

from _loader import load_script


class TestCategorize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script("build-karpathy-index.py")

    def cat(self, filename, fm, language="nl"):
        return self.mod.categorize(filename, fm, language)

    def test_tag_match_known_inputs(self):
        # A 'skills' tag maps to the Claude Code workflow bucket.
        category, is_mem = self.cat("wiki-something.md", {"tags": ["skills"]})
        self.assertEqual(category, "Claude Code: workflow, skills en subagents")
        self.assertFalse(is_mem)

        # An 'ollama' tag maps to the configuration/model-infra bucket.
        category, _ = self.cat("wiki-x.md", {"tags": ["ollama"]})
        self.assertEqual(category, "Claude Code: configuratie en model-infrastructuur")

        # A 'journalistiek' tag maps to the journalism bucket.
        category, _ = self.cat("wiki-y.md", {"tags": ["journalistiek"]})
        self.assertEqual(category, "Journalistiek: methode, redactie en onderzoek")

    def test_explicit_category_field_wins(self):
        category, is_mem = self.cat(
            "wiki-anything.md",
            {"category": "Mijn Eigen Categorie", "tags": ["skills"]},
        )
        self.assertEqual(category, "Mijn Eigen Categorie")
        self.assertFalse(is_mem)

    def test_memory_type_routes_to_memory_category(self):
        category, is_mem = self.cat("wiki-mem.md", {"type": "wiki-memory"})
        self.assertEqual(category, self.mod.MEMORY_CATEGORY)
        self.assertTrue(is_mem)

    def test_prefix_hint_used_when_no_tag_match(self):
        # No tags, but the filename prefix points at the ADR bucket.
        category, _ = self.cat("wiki-adr-some-decision.md", {})
        self.assertEqual(category, "ADR en architectuurbeslissingen")

    def test_unknown_falls_back_to_default_bucket(self):
        # No tags, no recognized prefix, NL corpus -> "Overig".
        category, is_mem = self.cat("totally-unknown.md", {}, language="nl")
        self.assertEqual(category, self.mod.OVERIG_NL)
        self.assertFalse(is_mem)

    def test_unknown_default_bucket_english(self):
        category, _ = self.cat("totally-unknown.md", {}, language="en")
        self.assertEqual(category, self.mod.OVERIG_EN)

    def test_generic_tags_ignored_for_matching(self):
        # 'wiki' and 'kennisbank' are generic; on their own they should not pull
        # the article into a real category (it lands in the default bucket).
        category, _ = self.cat("plain.md", {"tags": ["wiki", "actief"]}, language="nl")
        self.assertEqual(category, self.mod.OVERIG_NL)


if __name__ == "__main__":
    unittest.main()

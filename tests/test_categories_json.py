"""Tests for the categories.json override in build-karpathy-index.py.

The taxonomy (CATEGORY_RULES, PREFIX_HINTS, NL_HINTS, GENERIC_TAGS, labels) is
extracted from the script into an optional categories.json. When absent, the
built-in defaults apply (so behavior is unchanged for the original author).
When present, it overrides the defaults. These tests prove both directions.

The loader (load_categories) searches next to the script and on each path in
`extra_paths`; apply_categories pushes the result into the module globals that
categorize() reads. Each test restores the defaults in tearDown so it does not
leak state into test_categorize.py (which asserts the default taxonomy).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _loader import load_script


class TestCategoriesJsonOverride(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script("build-karpathy-index.py")

    def tearDown(self):
        # Restore the built-in defaults so the order of test files cannot make
        # test_categorize.py see an overridden taxonomy.
        self.mod.apply_categories(self.mod.load_categories())

    def _apply_json(self, payload: dict, tmpdir: Path):
        (tmpdir / "categories.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        self.mod.apply_categories(
            self.mod.load_categories(extra_paths=[tmpdir])
        )

    def test_default_taxonomy_when_no_json(self):
        # Sanity: with no override, the built-in default rule still applies.
        self.mod.apply_categories(self.mod.load_categories())
        category, _ = self.mod.categorize("wiki-x.md", {"tags": ["skills"]}, "nl")
        self.assertEqual(category, "Claude Code: workflow, skills en subagents")

    def test_custom_category_rules_override_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            self._apply_json(
                {
                    "category_rules": [
                        ["My Custom Bucket", ["widget", "gadget"]],
                    ]
                },
                tmpdir,
            )
            # The custom keyword now wins.
            category, is_mem = self.mod.categorize(
                "anything.md", {"tags": ["widget"]}, "en"
            )
            self.assertEqual(category, "My Custom Bucket")
            self.assertFalse(is_mem)

            # A tag that only matched a DEFAULT rule ('skills') no longer maps to
            # the old bucket: defaults are fully replaced, so it falls back.
            category, _ = self.mod.categorize(
                "totally-unknown.md", {"tags": ["skills"]}, "en"
            )
            self.assertEqual(category, self.mod.OVERIG_EN)

    def test_custom_prefix_hints_override_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            self._apply_json(
                {"prefix_hints": {"myproj-": "Project Bucket"}},
                tmpdir,
            )
            category, _ = self.mod.categorize("myproj-note.md", {}, "en")
            self.assertEqual(category, "Project Bucket")

    def test_custom_labels_override_fallback_bucket(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            self._apply_json(
                {"labels": {"overig_nl": "Restcategorie", "memory_category": "Geheugen"}},
                tmpdir,
            )
            # No tags, no prefix, NL corpus -> custom 'Overig' label.
            category, _ = self.mod.categorize("nothing.md", {}, "nl")
            self.assertEqual(category, "Restcategorie")
            self.assertEqual(self.mod.OVERIG_NL, "Restcategorie")
            # Memory snapshots route to the custom memory label.
            category, is_mem = self.mod.categorize(
                "mem.md", {"type": "wiki-memory"}, "nl"
            )
            self.assertEqual(category, "Geheugen")
            self.assertTrue(is_mem)

    def test_partial_json_keeps_defaults_for_omitted_keys(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            # Only override prefix_hints; category_rules should remain default.
            self._apply_json(
                {"prefix_hints": {"foo-": "Foo Bucket"}},
                tmpdir,
            )
            # Default tag rule still works.
            category, _ = self.mod.categorize("x.md", {"tags": ["skills"]}, "nl")
            self.assertEqual(category, "Claude Code: workflow, skills en subagents")
            # And the new prefix hint applies.
            category, _ = self.mod.categorize("foo-bar.md", {}, "nl")
            self.assertEqual(category, "Foo Bucket")

    def test_malformed_json_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            (tmpdir / "categories.json").write_text("{ not valid json", encoding="utf-8")
            # Must not raise; falls back to defaults.
            self.mod.apply_categories(
                self.mod.load_categories(extra_paths=[tmpdir])
            )
            category, _ = self.mod.categorize("x.md", {"tags": ["skills"]}, "nl")
            self.assertEqual(category, "Claude Code: workflow, skills en subagents")

    def test_example_json_reproduces_defaults(self):
        # The shipped categories.example.json must equal the built-in defaults,
        # so a user who adopts it as-is sees no behavior change.
        repo_root = Path(__file__).resolve().parent.parent
        example = repo_root / "categories.example.json"
        self.assertTrue(example.is_file(), "categories.example.json missing")
        data = json.loads(example.read_text(encoding="utf-8"))

        ex_rules = [(n, set(k)) for n, k in self.mod._coerce_category_rules(data["category_rules"])]
        def_rules = [(n, set(k)) for n, k in self.mod._DEFAULT_CATEGORY_RULES]
        self.assertEqual(ex_rules, def_rules)
        self.assertEqual(
            {str(k): str(v) for k, v in data["prefix_hints"].items()},
            dict(self.mod._DEFAULT_PREFIX_HINTS),
        )
        self.assertEqual(
            {t.strip().lower() for t in data["generic_tags"]},
            set(self.mod._DEFAULT_GENERIC_TAGS),
        )
        self.assertEqual(
            {t.strip().lower() for t in data["nl_hints"]},
            set(self.mod._DEFAULT_NL_HINTS),
        )
        labels = data["labels"]
        self.assertEqual(labels["overig_nl"], self.mod._DEFAULT_OVERIG_NL)
        self.assertEqual(labels["overig_en"], self.mod._DEFAULT_OVERIG_EN)
        self.assertEqual(labels["memory_category"], self.mod._DEFAULT_MEMORY_CATEGORY)


if __name__ == "__main__":
    unittest.main()

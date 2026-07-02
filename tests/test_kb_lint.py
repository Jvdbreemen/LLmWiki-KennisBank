"""Tests for scripts/kb-lint.py — provenance-lint voor wiki-artikelen.

Filesystem tests draaien tegen een tijdelijke vault (tempfile); geen netwerk,
geen Ollama. lint_vault/lint_article krijgen de vault-root als argument, dus
KENNISBANK_VAULT is niet nodig.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._loader import load_script


def _lint():
    return load_script("kb-lint.py")


class TestNormalizeTarget(unittest.TestCase):
    def setUp(self):
        self.kl = _lint()

    def test_plain_target(self):
        self.assertEqual(
            self.kl.normalize_target("raw-sessie-2026-06-28-x"),
            "raw-sessie-2026-06-28-x",
        )

    def test_alias_stripped(self):
        self.assertEqual(
            self.kl.normalize_target("raw-sessie-2026-06-28-x|de bron"),
            "raw-sessie-2026-06-28-x",
        )

    def test_heading_anchor_stripped(self):
        self.assertEqual(
            self.kl.normalize_target("raw-sessie-2026-06-28-x#kop"),
            "raw-sessie-2026-06-28-x",
        )

    def test_path_prefix_and_extension_stripped(self):
        self.assertEqual(
            self.kl.normalize_target("01-raw/sessies/raw-sessie-2026-06-28-x.md"),
            "raw-sessie-2026-06-28-x",
        )

    def test_backslash_path(self):
        self.assertEqual(
            self.kl.normalize_target("01-raw\\sessies\\raw-sessie-2026-06-28-x"),
            "raw-sessie-2026-06-28-x",
        )


class VaultCase(unittest.TestCase):
    """Basis: tijdelijke vault met 01-raw/sessies, 02-wiki en 08-archive."""

    def setUp(self):
        self.kl = _lint()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "01-raw" / "sessies").mkdir(parents=True)
        (self.root / "02-wiki").mkdir()
        (self.root / "08-archive").mkdir()
        self.addCleanup(self._tmp.cleanup)

    def add_session(self, stem: str, archived: bool = False):
        d = self.root / ("08-archive" if archived else "01-raw/sessies")
        (d / f"{stem}.md").write_text("sessielog", encoding="utf-8")

    def add_article(self, name: str, body: str):
        (self.root / "02-wiki" / name).write_text(body, encoding="utf-8")


class TestLintVault(VaultCase):
    def test_clean_article_with_resolving_wikilink(self):
        self.add_session("raw-sessie-2026-06-28-x")
        self.add_article("a.md", "## Sessie-herkomst\n- punt: [[raw-sessie-2026-06-28-x]]\n")
        report = self.kl.lint_vault(self.root)
        self.assertEqual(report["warnings"], [])
        self.assertEqual(report["clean"], 1)

    def test_missing_provenance_warns(self):
        self.add_article("a.md", "# Titel\ngeen herkomst\n")
        report = self.kl.lint_vault(self.root)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertEqual(report["warnings"][0]["type"], "missing")

    def test_dangling_wikilink_warns(self):
        self.add_article("a.md", "- punt: [[raw-sessie-2026-01-01-bestaat-niet]]\n")
        report = self.kl.lint_vault(self.root)
        types = [w["type"] for w in report["warnings"]]
        self.assertIn("dangling", types)

    def test_path_only_reference_warns(self):
        self.add_session("raw-sessie-2026-06-28-x")
        self.add_article("a.md", "Bron: `01-raw/sessies/raw-sessie-2026-06-28-x.md`\n")
        report = self.kl.lint_vault(self.root)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertEqual(report["warnings"][0]["type"], "path-only")

    def test_path_ref_next_to_resolving_wikilink_is_clean(self):
        self.add_session("raw-sessie-2026-06-28-x")
        self.add_article(
            "a.md",
            "- punt: [[raw-sessie-2026-06-28-x]]\nook als pad: `01-raw/sessies/raw-sessie-2026-06-28-x.md`\n",
        )
        report = self.kl.lint_vault(self.root)
        self.assertEqual(report["warnings"], [])

    def test_alias_wikilink_resolves(self):
        self.add_session("raw-sessie-2026-06-28-x")
        self.add_article("a.md", "- punt: [[raw-sessie-2026-06-28-x|de bron]]\n")
        report = self.kl.lint_vault(self.root)
        self.assertEqual(report["warnings"], [])

    def test_path_style_wikilink_resolves(self):
        self.add_session("raw-sessie-2026-06-28-x")
        self.add_article("a.md", "- punt: [[01-raw/sessies/raw-sessie-2026-06-28-x.md]]\n")
        report = self.kl.lint_vault(self.root)
        self.assertEqual(report["warnings"], [])

    def test_archived_session_resolves(self):
        self.add_session("raw-sessie-2025-01-01-oud", archived=True)
        self.add_article("a.md", "- punt: [[raw-sessie-2025-01-01-oud]]\n")
        report = self.kl.lint_vault(self.root)
        self.assertEqual(report["warnings"], [])

    def test_moved_session_elsewhere_in_vault_resolves(self):
        # Obsidian resolvet wikilinks vault-breed op bestandsnaam; een sessie
        # die naar bv. 01-raw/debug/ is verplaatst blijft geldige herkomst.
        debug = self.root / "01-raw" / "debug"
        debug.mkdir(parents=True)
        (debug / "raw-sessie-2026-04-11-debug.md").write_text("log", encoding="utf-8")
        self.add_article("a.md", "- punt: [[raw-sessie-2026-04-11-debug]]\n")
        report = self.kl.lint_vault(self.root)
        self.assertEqual(report["warnings"], [])

    def test_session_inside_tooling_dirs_does_not_resolve(self):
        # .claude/ en graphify-out/ zijn tooling-output, geen herkomst.
        hidden = self.root / ".claude" / "cache"
        hidden.mkdir(parents=True)
        (hidden / "raw-sessie-2026-01-01-cache.md").write_text("x", encoding="utf-8")
        self.add_article("a.md", "- punt: [[raw-sessie-2026-01-01-cache]]\n")
        report = self.kl.lint_vault(self.root)
        self.assertEqual([w["type"] for w in report["warnings"]], ["dangling"])

    def test_index_and_log_skipped(self):
        self.add_article("index.md", "geen herkomst nodig\n")
        self.add_article("log.md", "geen herkomst nodig\n")
        report = self.kl.lint_vault(self.root)
        self.assertEqual(report["articles"], 0)
        self.assertEqual(report["warnings"], [])

    def test_resolving_and_dangling_in_one_article(self):
        # Eén resolvende link voorkomt missing/path-only, maar de dode link
        # blijft een eigen waarschuwing.
        self.add_session("raw-sessie-2026-06-28-x")
        self.add_article(
            "a.md",
            "- p1: [[raw-sessie-2026-06-28-x]]\n- p2: [[raw-sessie-2026-01-01-weg]]\n",
        )
        report = self.kl.lint_vault(self.root)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertEqual(report["warnings"][0]["type"], "dangling")

    def test_missing_wiki_dir_raises(self):
        with tempfile.TemporaryDirectory() as leeg:
            with self.assertRaises(FileNotFoundError):
                self.kl.lint_vault(Path(leeg))

    def test_warned_counts_files_not_findings(self):
        # Twee findings in één bestand tellen als één warned-bestand.
        self.add_article(
            "a.md",
            "- p1: [[raw-sessie-2026-01-01-weg]]\n- p2: [[raw-sessie-2026-01-02-ook-weg]]\n",
        )
        report = self.kl.lint_vault(self.root)
        self.assertEqual(len(report["warnings"]), 2)
        self.assertEqual(report["warned"], 1)
        self.assertEqual(report["clean"], 0)


if __name__ == "__main__":
    unittest.main()

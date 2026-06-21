"""
Structuurtest voor commands/*.md slash-command bestanden.
Elke testmethode valideert één command-bestand op vereiste strings.
"""

import unittest
from pathlib import Path

COMMANDS_DIR = Path(__file__).resolve().parents[1] / "commands"


class WikiCommandStructureTest(unittest.TestCase):
    """Controleert dat commands/wiki.md alle verwachte secties bevat."""

    def setUp(self):
        self.path = COMMANDS_DIR / "wiki.md"
        self.content = self.path.read_text(encoding="utf-8")

    # --- originele stappen (stable substrings) ---

    def test_step1_raw_logs(self):
        self.assertIn("01-raw/sessies", self.content)

    def test_step2_kandidaten(self):
        self.assertIn("wiki-kandidaten", self.content)

    def test_step3_bestaande_wiki(self):
        self.assertIn("02-wiki", self.content)

    def test_step4_frontmatter(self):
        self.assertIn("YAML frontmatter", self.content)

    def test_step5_rapporteer(self):
        self.assertIn("Rapporteer", self.content)

    # --- nieuwe Stap 3.5 vereisten ---

    def test_step35_marker(self):
        self.assertIn("3.5", self.content)

    def test_step35_find_similar(self):
        self.assertIn("find-similar", self.content)

    def test_step35_safe_edit(self):
        self.assertIn("safe-edit", self.content)

    def test_step35_wiki_rewrite_prefix(self):
        self.assertIn("wiki-rewrite:", self.content)

    # --- rapport onderscheid ---

    def test_report_herschreven(self):
        self.assertIn("**herschreven**", self.content)

    def test_report_nieuw(self):
        self.assertIn("**nieuw**", self.content)

    def test_report_overgeslagen(self):
        self.assertIn("**overgeslagen**", self.content)


class ReconcileCommandStructureTest(unittest.TestCase):
    """Controleert dat commands/reconcile.md alle verwachte secties bevat."""

    def setUp(self):
        self.path = COMMANDS_DIR / "reconcile.md"
        self.content = self.path.read_text(encoding="utf-8")

    def test_uses_conflict_scan(self):
        self.assertIn("conflict-scan", self.content)

    def test_uses_safe_edit(self):
        self.assertIn("safe-edit", self.content)

    def test_writes_reconciliation_log(self):
        self.assertIn("reconciliation-log.md", self.content)

    def test_commit_prefix(self):
        self.assertIn("reconcile:", self.content)


class UitdaagCommandStructureTest(unittest.TestCase):
    """Controleert dat commands/uitdaag.md alle verwachte elementen bevat."""

    def setUp(self):
        self.path = COMMANDS_DIR / "uitdaag.md"
        self.content = self.path.read_text(encoding="utf-8")

    def test_uses_kb_search(self):
        self.assertIn("kb-search", self.content)

    def test_uses_citation_wikilink(self):
        self.assertIn("[[", self.content)

    def test_uses_arguments(self):
        self.assertIn("$ARGUMENTS", self.content)


class BrugCommandStructureTest(unittest.TestCase):
    """Controleert dat commands/brug.md alle verwachte elementen bevat."""

    def setUp(self):
        self.path = COMMANDS_DIR / "brug.md"
        self.content = self.path.read_text(encoding="utf-8")

    def test_uses_kb_search(self):
        self.assertIn("kb-search", self.content)

    def test_uses_graph_json(self):
        self.assertIn("graph.json", self.content)

    def test_uses_arguments(self):
        self.assertIn("$ARGUMENTS", self.content)

    def test_has_fallback(self):
        has_fallback = "fallback" in self.content or "terugval" in self.content
        self.assertTrue(has_fallback, "brug.md moet 'fallback' of 'terugval' bevatten")


if __name__ == "__main__":
    unittest.main()

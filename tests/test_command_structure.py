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


if __name__ == "__main__":
    unittest.main()

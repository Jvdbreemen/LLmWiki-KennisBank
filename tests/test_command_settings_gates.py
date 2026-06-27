"""Guard: de daily-graphify-gate moet in de command-markdown verankerd staan.

Dit is geen gedragstest (markdown is instructie, geen code) maar een regression-
guard dat de toggle-naam niet stilletjes uit de commands verdwijnt bij een
herschrijving.
"""
from __future__ import annotations

import unittest
from pathlib import Path

COMMANDS = Path(__file__).resolve().parent.parent / "commands"


class CommandGateTest(unittest.TestCase):
    def _assert_mentions(self, name):
        text = (COMMANDS / name).read_text(encoding="utf-8")
        self.assertIn("daily_graphify", text,
                      f"{name} noemt de daily_graphify-gate niet")

    def test_sessielog_has_gate(self):
        self._assert_mentions("sessielog.md")

    def test_wiki_has_gate(self):
        self._assert_mentions("wiki.md")

    def test_destilleer_has_gate(self):
        self._assert_mentions("destilleer.md")

    def test_upgrade_skill_ensures_settings(self):
        skill = Path(__file__).resolve().parent.parent / "skills" / "kennisbank-upgrade" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertIn("kennisbank-settings.json", text,
                      "upgrade-skill garandeert het settings-bestand niet")


if __name__ == "__main__":
    unittest.main()

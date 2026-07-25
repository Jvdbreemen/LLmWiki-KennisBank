"""Koppelt de release-artefacten aan elkaar (TASK-58).

Bij een handmatige release liep dit uiteen: de CHANGELOG kreeg een nieuwe
sectie, maar één van de twee README-varianten bleef op de vorige versie staan,
of de compare-links wezen nog naar de oude tag. Deze test maakt van die drie
plekken één geheel, zodat een halve bump rood wordt in plaats van geshipt.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
README_EN = REPO_ROOT / "README.md"
README_NL = REPO_ROOT / "README.nl.md"

VERSION_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}\s*$", re.M)


def latest_version() -> str:
    text = CHANGELOG.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        raise AssertionError("CHANGELOG heeft geen gedateerde versiesectie")
    return match.group(1)


class ReleaseMetadataTest(unittest.TestCase):
    def test_changelog_has_an_unreleased_section(self):
        self.assertIn("## [Unreleased]", CHANGELOG.read_text(encoding="utf-8"))

    def test_compare_links_point_at_the_latest_version(self):
        version = latest_version()
        text = CHANGELOG.read_text(encoding="utf-8")
        self.assertIn(f"[Unreleased]: https://github.com/Jvdbreemen/LLmWiki-KennisBank"
                      f"/compare/v{version}...HEAD", text,
                      "de Unreleased-compare-link wijst niet naar de nieuwste tag")
        self.assertIsNotNone(
            re.search(rf"^\[{re.escape(version)}\]: ", text, re.M),
            "de nieuwste versie heeft geen eigen compare-link")

    def test_both_readmes_name_the_latest_version(self):
        version = latest_version()
        for path, heading, new_in in (
            (README_EN, "## Feature highlights", "### New in"),
            (README_NL, "## Functie-highlights", "### Nieuw in"),
        ):
            text = path.read_text(encoding="utf-8")
            with self.subTest(readme=path.name):
                self.assertIn(f"{heading} (v{version})", text,
                              f"{path.name} highlight-kop staat niet op v{version}")
                self.assertIn(f"{new_in} v{version}", text,
                              f"{path.name} mist een '{new_in} v{version}'-sectie")

    def test_the_release_skill_is_shipped(self):
        skill = REPO_ROOT / "skills" / "kennisbank-release" / "SKILL.md"
        self.assertTrue(skill.is_file(), "release-skill ontbreekt")
        text = skill.read_text(encoding="utf-8")
        # De twee stappen die bij v0.20.0 handmatig misgingen.
        self.assertIn("pulls/<n>/comments", text,
                      "de skill legt niet vast hoe de Copilot-review opgehaald wordt")
        self.assertIn("git rev-parse origin/main", text,
                      "de skill verifieert de merge niet vóór het taggen")


if __name__ == "__main__":
    unittest.main()

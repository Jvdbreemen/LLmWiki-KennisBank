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


class SessiestartCommandStructureTest(unittest.TestCase):
    """Controleert dat commands/sessiestart.md de context-budget integratie bevat."""

    def setUp(self):
        self.path = COMMANDS_DIR / "sessiestart.md"
        self.content = self.path.read_text(encoding="utf-8")

    def test_contains_context_budget(self):
        self.assertIn("context-budget", self.content)


class TemporalActivityCommandStructureTest(unittest.TestCase):
    """Controleert dat temporal commands de gedeelde activity scripts gebruiken."""

    def test_weeklog_uses_activity_cli(self):
        content = (COMMANDS_DIR / "weeklog.md").read_text(encoding="utf-8")
        self.assertIn("kb-activity.py", content)
        self.assertIn("build-activity-index.py", content)
        self.assertIn("source_ref", content)

    def test_timeline_uses_activity_cli(self):
        content = (COMMANDS_DIR / "timeline.md").read_text(encoding="utf-8")
        self.assertIn("kb-activity.py", content)
        self.assertIn("timeline", content)
        self.assertIn("$ARGUMENTS", content)

    def test_watdeedik_uses_activity_cli(self):
        content = (COMMANDS_DIR / "watdeedik.md").read_text(encoding="utf-8")
        self.assertIn("kb-activity.py", content)
        self.assertIn("watdeedik", content)
        self.assertIn("$ARGUMENTS", content)



class KennisbankUpgradeCommandStructureTest(unittest.TestCase):
    """Controleert dat commands/kennisbank-upgrade.md de skill aanstuurt."""

    def setUp(self):
        self.path = COMMANDS_DIR / "kennisbank-upgrade.md"
        self.content = self.path.read_text(encoding="utf-8")

    def test_invokes_skill(self):
        self.assertIn("kennisbank-upgrade", self.content)
        self.assertIn("skill", self.content)

    def test_passes_arguments(self):
        self.assertIn("$ARGUMENTS", self.content)

    def test_mentions_doctor_verification(self):
        self.assertIn("doctor.sh", self.content)


class KennisbankContributeCommandStructureTest(unittest.TestCase):
    """Controleert dat commands/kennisbank-contribute.md de skill aanstuurt."""

    def setUp(self):
        self.path = COMMANDS_DIR / "kennisbank-contribute.md"
        self.content = self.path.read_text(encoding="utf-8")

    def test_invokes_skill(self):
        self.assertIn("kennisbank-contribute", self.content)
        self.assertIn("skill", self.content)

    def test_passes_arguments(self):
        self.assertIn("$ARGUMENTS", self.content)

    def test_mentions_pull_request(self):
        self.assertIn("pull request", self.content)


class NoHardcodedVaultInCommandsTest(unittest.TestCase):
    """Regressie-guard: geen command-bestand mag scripts via een hardcoded
    ~/KennisBank-pad aanroepen; gebruik de $VAULT-resolutie."""

    def test_no_hardcoded_script_path(self):
        for md in sorted(COMMANDS_DIR.glob("*.md")):
            content = md.read_text(encoding="utf-8")
            self.assertNotIn(
                "~/KennisBank/.claude/scripts",
                content,
                f"{md.name} roept een script aan via een hardcoded ~/KennisBank-pad; gebruik de $VAULT-resolutie",
            )


if __name__ == "__main__":
    unittest.main()

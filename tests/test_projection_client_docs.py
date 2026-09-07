"""Cross-surface documentation contract for production deeper recall."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectionClientDocsTest(unittest.TestCase):
    def test_current_user_docs_share_the_four_default_off_flags(self):
        paths = (
            ROOT / "README.md",
            ROOT / "README.nl.md",
            ROOT / "CONFIGURATION.md",
            ROOT / "commands" / "kennisbank" / "settings.md",
            ROOT / "docs" / "AGENT-INSTALL.md",
            ROOT / "skills" / "kennisbank-upgrade" / "SKILL.md",
        )
        keys = (
            "experience_capture",
            "experience_projection",
            "experience_explicit_recall",
            "source_explicit_recall",
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for key in keys:
                self.assertIn(key, text, f"{path} omits {key}")

    def test_current_surfaces_exclude_stale_experimental_contracts(self):
        paths = (
            ROOT / "README.md",
            ROOT / "README.nl.md",
            ROOT / "CONFIGURATION.md",
            ROOT / "docs" / "AGENT-INSTALL.md",
            ROOT / "skills" / "kennisbank-upgrade" / "SKILL.md",
        )
        forbidden = (
            "`source_recall` enables",
            "`experience_recall` enables",
            "source_recall (default OFF)",
            "experience_recall (default OFF)",
            "validated experiences or failure advisories",
            "gevalideerde ervaringen of gelabelde failure-advisories",
            "`--incremental` and `--records-only`",
            "`--incremental` en `--records-only`",
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{path} retains stale text: {phrase}")

    def test_mcp_and_client_guides_teach_experience_first_source_on_demand(self):
        mcp = (ROOT / "scripts" / "kb-mcp.py").read_text(encoding="utf-8").lower()
        guide = (ROOT / "docs" / "AGENT-INSTALL.md").read_text(encoding="utf-8").lower()
        for text in (mcp, guide):
            self.assertIn("experience", text)
            self.assertIn("first", text)
            self.assertIn("source", text)
            self.assertIn("on demand", text)
            self.assertTrue("automatic advisory" in text or "automatic" in text)

    def test_c4_names_split_experience_stores_and_call_smoke(self):
        c4 = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "C4-Documentation" / "c4-container.md",
                ROOT / "docs" / "C4-Documentation" / "c4-component-agent-integration.md",
            )
        )
        self.assertIn("kb-experience-ledger.db", c4)
        self.assertIn("kb-experience-index.db", c4)
        self.assertIn("list_tools", c4)
        self.assertTrue("source" in c4 and "experience" in c4 and "call" in c4)

    def test_capture_guide_keeps_source_first_and_projection_separate(self):
        guide = (ROOT / "docs" / "experience-capture.md").read_text(
            encoding="utf-8")
        for phrase in ("experience_capture", "source_ranges",
                       "kb-experience-capture.py", "kb-experience-ledger.db"):
            self.assertIn(phrase, guide)
        self.assertIn("does not build", guide)
        self.assertIn("kb-experience-index.db", guide)


if __name__ == "__main__":
    unittest.main()

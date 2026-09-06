"""Cross-surface documentation contract for production deeper recall."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_current_user_docs_share_the_four_default_off_flags():
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
            assert key in text, f"{path} omits {key}"


def test_current_surfaces_exclude_stale_experimental_contracts():
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
            assert phrase not in text, f"{path} retains stale text: {phrase}"


def test_mcp_and_client_guides_teach_experience_first_source_on_demand():
    mcp = (ROOT / "scripts" / "kb-mcp.py").read_text(encoding="utf-8").lower()
    guide = (ROOT / "docs" / "AGENT-INSTALL.md").read_text(encoding="utf-8").lower()
    for text in (mcp, guide):
        assert "experience" in text
        assert "first" in text
        assert "source" in text
        assert "on demand" in text
        assert "automatic advisory" in text or "automatic" in text


def test_c4_names_split_experience_stores_and_call_smoke():
    c4 = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "docs" / "C4-Documentation" / "c4-container.md",
            ROOT / "docs" / "C4-Documentation" / "c4-component-agent-integration.md",
        )
    )
    assert "kb-experience-ledger.db" in c4
    assert "kb-experience-index.db" in c4
    assert "list_tools" in c4
    assert "source" in c4 and "experience" in c4 and "call" in c4

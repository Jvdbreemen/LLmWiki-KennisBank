import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_readmes_document_first_class_quiet_integrations():
    for name in ("README.md", "README.nl.md"):
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        normalized = re.sub(r"\s+", " ", text)
        for client in ("Claude Code", "Codex", "GitHub Copilot CLI"):
            assert client in text
        assert "OpenCode" in text
        assert (
            "silent on success" in normalized
            or "stil bij succes" in normalized
            or "Routine no-change" in normalized
            or "Geen-wijziging-uitvoer blijft stil" in normalized
            or "zonder wijzigingen zijn stil" in normalized
            or "quiet-hook.py" in normalized
        )
        assert "--agents claude,codex,copilot" in text


def test_product_surfaces_have_no_removed_client_reference():
    removed_client = "cur" + "sor"
    paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.nl.md",
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "CONFIGURATION.md",
        *sorted((REPO_ROOT / "docs").rglob("*.md")),
        *sorted((REPO_ROOT / "scripts").glob("*.py")),
    ]
    for path in paths:
        assert removed_client not in path.read_text(encoding="utf-8").lower(), str(path)


def test_generated_prompt_descriptions_are_english():
    source = (REPO_ROOT / "scripts" / "install-agent-envs.py").read_text(
        encoding="utf-8"
    )
    dutch_metadata = re.compile(
        r'^\s*"[^"]+":\s*"[^"]*\b'
        r"(?:maak|werk|zoek|controleer|gebruik|voor|naar|nieuwste|bruikbare)\b",
        re.IGNORECASE | re.MULTILINE,
    )
    assert not dutch_metadata.search(source)

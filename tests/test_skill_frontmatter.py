import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"
TOP_LEVEL = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?:[ \t]*(.*))?$")


def parse_frontmatter(text: str, source: str = "<text>") -> dict:
    """Parse the simple top-level YAML shape supported by agent skills.

    This is deliberately stricter than the product's permissive wiki metadata
    reader. In particular, YAML plain scalars cannot contain ``: `` because
    that starts a nested mapping; Copilot rejects such skill manifests.
    """
    if not text.startswith("---"):
        raise ValueError(f"{source} missing frontmatter open")
    end = text.index("\n---", 3)
    lines = text[3:end].strip().splitlines()
    fm = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        match = TOP_LEVEL.fullmatch(line)
        if match is None:
            raise ValueError(f"{source} invalid top-level YAML: {line!r}")
        key, raw = match.groups()
        raw = (raw or "").strip()
        if raw in {">", ">-", "|", "|-"}:
            parts = []
            index += 1
            while index < len(lines) and (
                not lines[index].strip() or lines[index][0].isspace()
            ):
                if lines[index].strip():
                    parts.append(lines[index].strip())
                index += 1
            fm[key] = " ".join(parts) if raw.startswith(">") else "\n".join(parts)
            continue
        if raw.startswith('"') and raw.endswith('"'):
            fm[key] = json.loads(raw)
            index += 1
            continue
        if raw.startswith("'") and raw.endswith("'"):
            fm[key] = raw[1:-1].replace("''", "'")
            index += 1
            continue
        if re.search(r":\s", raw):
            raise ValueError(
                f"{source} plain YAML scalar contains mapping delimiter ': '"
            )
        fm[key] = raw
        index += 1
    return fm


class SkillFrontmatterTest(unittest.TestCase):
    def test_skill_files_have_valid_frontmatter(self):
        paths = sorted(SKILLS_ROOT.glob("*/SKILL.md"))
        self.assertTrue(paths, "no shipped skills found")
        for path in paths:
            slug = path.parent.name
            self.assertTrue(path.is_file(), f"missing {path}")
            fm = parse_frontmatter(path.read_text(encoding="utf-8"), str(path))
            self.assertEqual(fm.get("name"), slug, f"{path} name mismatch")
            self.assertTrue(fm.get("description"), f"{path} empty description")

    def test_plain_description_rejects_colon_space_like_copilot(self):
        broken = (
            "---\n"
            "name: broken\n"
            "description: Useful workflow. Triggers: /broken\n"
            "---\n"
        )
        with self.assertRaisesRegex(ValueError, "mapping delimiter"):
            parse_frontmatter(broken)

    def test_quoted_description_allows_colon_space(self):
        quoted = (
            "---\n"
            "name: valid\n"
            'description: "Useful workflow. Triggers: /valid"\n'
            "---\n"
        )
        self.assertIn("Triggers:", parse_frontmatter(quoted)["description"])

    def test_kennisbank_skill_descriptions_keep_triggers(self):
        for slug in ("kennisbank-upgrade", "kennisbank-contribute"):
            path = SKILLS_ROOT / slug / "SKILL.md"
            fm = parse_frontmatter(path.read_text(encoding="utf-8"), str(path))
            self.assertIn("Triggers:", fm["description"])

    def test_all_skill_descriptions_are_english_metadata(self):
        dutch_markers = re.compile(
            r"\b(?:autonome|iteratieve|voor|geef|bevindingen|nieuwste|bruikbare)\b",
            re.IGNORECASE,
        )
        for path in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
            fm = parse_frontmatter(path.read_text(encoding="utf-8"), str(path))
            self.assertNotRegex(fm["description"], dutch_markers, str(path))

    def test_upgrade_skill_mentions_memory_backfill(self):
        text = (Path(__file__).resolve().parent.parent /
                "skills" / "kennisbank-upgrade" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("rebuild-memory", text)
        self.assertIn("backfill", text.lower())


if __name__ == "__main__":
    unittest.main()

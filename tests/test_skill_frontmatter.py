import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = ["kennisbank-upgrade", "kennisbank-contribute"]


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path} missing frontmatter open")
    end = text.index("\n---", 3)
    body = text[3:end]
    fm = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        fm[key.strip()] = val.strip()
    return fm


class SkillFrontmatterTest(unittest.TestCase):
    def test_skill_files_have_valid_frontmatter(self):
        for slug in SKILLS:
            path = REPO_ROOT / "skills" / slug / "SKILL.md"
            self.assertTrue(path.is_file(), f"missing {path}")
            fm = read_frontmatter(path)
            self.assertEqual(fm.get("name"), slug, f"{path} name mismatch")
            self.assertTrue(fm.get("description"), f"{path} empty description")

    def test_upgrade_skill_mentions_memory_backfill(self):
        text = (Path(__file__).resolve().parent.parent /
                "skills" / "kennisbank-upgrade" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("rebuild-memory", text)
        self.assertIn("backfill", text.lower())


if __name__ == "__main__":
    unittest.main()

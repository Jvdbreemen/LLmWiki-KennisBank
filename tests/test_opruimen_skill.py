"""The shipped opruimen skill must stay complete and machine-independent.

The skill carries four scripts that a user runs against their own Hermes store
and their own Claude Code transcripts. Two things can silently rot it: a script
that stops importing or passing its offline self-test, and a machine path that
got baked in while the skill was generalised. Both are cheap to assert.
"""
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "opruimen"
SCRIPTS_DIR = SKILL_DIR / "scripts"
SCRIPT_NAMES = (
    "scan_hermes_sessies.py",
    "archiveer_hermes_sessies.py",
    "scan_transcripten.py",
    "sessielog-batch.py",
)


class OpruimenSkillTest(unittest.TestCase):
    def test_skill_exists_with_frontmatter(self):
        path = SKILL_DIR / "SKILL.md"
        self.assertTrue(path.is_file(), f"missing {path}")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), "frontmatter open missing")
        fm = text[3:text.index("\n---", 3)]
        self.assertRegex(fm, r"(?m)^name:\s*opruimen\s*$")
        self.assertRegex(fm, r"(?m)^description:\s*>-?\s*$")

    def test_all_four_scripts_are_shipped(self):
        for name in SCRIPT_NAMES:
            self.assertTrue((SCRIPTS_DIR / name).is_file(),
                            f"{name} not shipped in the skill")

    def test_session_log_self_test_passes_without_a_vault(self):
        """--zelftest is the offline proof of the vault and sensitivity gate.

        KENNISBANK_VAULT is deliberately not passed: the self-test must hold on a
        machine that has no vault at all, and it never touches one.
        """
        env = {k: v for k, v in os.environ.items() if k != "KENNISBANK_VAULT"}
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "sessielog-batch.py"), "--zelftest"],
            capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, 0,
                         f"zelftest failed:\n{proc.stdout}\n{proc.stderr}")
        self.assertIn("checks PASS", proc.stdout)

    def test_sensitive_path_list_has_no_machine_path(self):
        path = SKILL_DIR / "gevoelig-paden.txt"
        self.assertTrue(path.is_file(), f"missing {path}")
        for regel in path.read_text(encoding="utf-8").splitlines():
            patroon = regel.strip()
            if not patroon or patroon.startswith("#"):
                continue
            self.assertNotIn("/Users/", patroon,
                             f"machine path in {path}: {patroon}")

    def test_skill_and_scripts_name_no_machine_path(self):
        """The generalised skill must not point at the author's home directory."""
        for path in [SKILL_DIR / "SKILL.md",
                     SKILL_DIR / "gevoelig-paden.txt",
                     *sorted(SCRIPTS_DIR.glob("*.py"))]:
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"/Users/\w",
                                f"machine path in {path}")

    def test_scripts_resolve_their_paths_from_the_environment(self):
        scan = (SCRIPTS_DIR / "scan_hermes_sessies.py").read_text(encoding="utf-8")
        batch = (SCRIPTS_DIR / "sessielog-batch.py").read_text(encoding="utf-8")
        cc = (SCRIPTS_DIR / "scan_transcripten.py").read_text(encoding="utf-8")
        self.assertIn('"HERMES_HOME"', scan)
        self.assertIn('"HERMES_HOME"', batch)
        self.assertIn('"CC_PROJECTS"', cc)
        # The product default stays allowed, a hardcoded absolute path does not.
        self.assertNotRegex(batch, r'"~/KennisBank/state\.db"')

    def test_transcript_scan_is_optional(self):
        """Claude Code is optional, so the docstring has to say so."""
        doc = (SCRIPTS_DIR / "scan_transcripten.py").read_text(encoding="utf-8")
        self.assertRegex(doc, r"no-op")
        self.assertIn("CC_PROJECTS", doc)


class OpruimenCommandTest(unittest.TestCase):
    def test_command_points_at_the_skill(self):
        text = (REPO_ROOT / "commands" / "opruimen.md").read_text(encoding="utf-8")
        self.assertIn("opruimen", text)
        self.assertIn("Claude Code", text)
        # The session-log route may no longer present CCR as the main route.
        self.assertNotRegex(text, re.compile(r"digest-route via CCR/OpenRouter"))


if __name__ == "__main__":
    unittest.main()

"""Hermetic tests for the OMP (oh-my-pi) target (scripts/_omp.py, TASK-258).

Every test runs against a temporary HOME/USERPROFILE so the real ~/.omp and
~/.agents are never touched.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = [sys.executable]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class OmpConfigTest(unittest.TestCase):
    def setUp(self):
        self.m = _load("_omp", REPO_ROOT / "scripts" / "_omp.py")
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-omp-"))
        self.home = self.tmp / ".omp" / "agent"
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        self.saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE", "PI_CODING_AGENT_DIR")}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ.pop("PI_CODING_AGENT_DIR", None)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mcp(self) -> dict:
        return json.loads((self.home / "mcp.json").read_text(encoding="utf-8"))

    def test_install_registers_the_server_on_the_active_vault_and_keeps_foreign_config(self):
        self.home.mkdir(parents=True)
        (self.home / "mcp.json").write_text(json.dumps({
            "$schema": "https://example.invalid/mcp-schema.json",
            "mcpServers": {"other": {"type": "stdio", "command": "other"}},
            "disabledServers": ["legacy"],
        }), encoding="utf-8")

        self.m.install(self.vault, python_argv=PY)

        data = self._mcp()
        self.assertEqual(data["mcpServers"]["other"], {"type": "stdio", "command": "other"})
        self.assertEqual(data["disabledServers"], ["legacy"])
        self.assertEqual(data["$schema"], "https://example.invalid/mcp-schema.json")
        srv = data["mcpServers"]["kennisbank"]
        self.assertEqual(srv["type"], "stdio")
        self.assertEqual(srv["command"], sys.executable)
        self.assertTrue(srv["args"][-1].endswith("/.claude/scripts/kb-mcp.py"))
        self.assertEqual(srv["env"]["KENNISBANK_VAULT"], str(self.vault).replace("\\", "/"))
        self.assertEqual(self.m.validate_config(self.vault), [])

    def test_instructions_are_an_always_apply_rule_and_never_agents_md(self):
        self.m.install(self.vault, python_argv=PY)

        rule = (self.home / "rules" / "kennisbank.md").read_text(encoding="utf-8")
        self.assertTrue(rule.startswith("---\n"))
        self.assertIn("alwaysApply: true", rule.split("---")[1])
        self.assertIn(str(self.vault).replace("\\", "/"), rule)
        # ~/.omp/agent/AGENTS.md would shadow every other user-level context file.
        self.assertFalse((self.home / "AGENTS.md").exists())

    def test_reinstall_changes_nothing(self):
        self.m.install(self.vault, python_argv=PY)
        before = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}

        report = self.m.install(self.vault, python_argv=PY)

        self.assertFalse(report["changed"])
        after = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_agent_dir_follows_pi_coding_agent_dir(self):
        custom = self.tmp / "custom-agent"
        os.environ["PI_CODING_AGENT_DIR"] = str(custom)

        self.m.install(self.vault, python_argv=PY)

        self.assertTrue((custom / "mcp.json").is_file())
        self.assertTrue((custom / "rules" / "kennisbank.md").is_file())
        self.assertFalse(self.home.exists())

    def test_validation_names_a_missing_or_foreign_registration(self):
        self.assertTrue(any("missing mcpServers.kennisbank" in e for e in self.m.validate_config(self.vault)))

        self.m.install(self.vault, python_argv=PY)
        other = self.tmp / "OtherVault"
        errors = self.m.validate_config(other)

        self.assertIn("OMP MCP kennisbank KENNISBANK_VAULT does not match the active vault", errors)
        self.assertTrue(any("rule does not name the active vault" in e for e in errors))


class OmpAgentTargetTest(unittest.TestCase):
    def setUp(self):
        self.m = _load("install_agent_envs", REPO_ROOT / "scripts" / "install-agent-envs.py")
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-omp-target-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        self.saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE", "PI_CODING_AGENT_DIR")}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ.pop("PI_CODING_AGENT_DIR", None)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_omp_is_a_known_target_and_part_of_all(self):
        self.assertEqual(self.m.parse_agents("omp"), ["omp"])
        self.assertIn("omp", self.m.parse_agents("all"))

    def test_install_omp_deploys_shared_skills_and_passes_validation(self):
        kb_mcp = self.vault / ".claude" / "scripts" / "kb-mcp.py"
        with patch.object(self.m, "_mcp_server_argv", lambda vault: [*PY, str(kb_mcp)]):
            result = self.m.install_omp(REPO_ROOT, self.vault)

        skills = self.tmp / ".agents" / "skills"
        for skill in ("sessielog", "sessiestart", "kennisbank-upgrade"):
            self.assertTrue((skills / skill / "SKILL.md").is_file(), skill)
        self.assertTrue(result["mcp"].endswith("/.omp/agent/mcp.json"))
        omp_errors = [
            e for e in self.m.validate_files(REPO_ROOT, self.vault, ["omp"])
            if "OMP" in e
        ]
        self.assertEqual(omp_errors, [])


if __name__ == "__main__":
    unittest.main()

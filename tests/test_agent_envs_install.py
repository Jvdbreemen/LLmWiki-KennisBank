import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "install-agent-envs.py"


def _load():
    spec = importlib.util.spec_from_file_location("install_agent_envs", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class AgentEnvInstallTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-agent-env-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        (self.vault / ".claude" / "kennisbank-embed.json").write_text(
            '{"provider":"ollama","model":"qwen3-embedding:8b"}', encoding="utf-8")
        (self.vault / ".claude" / "kennisbank-llm.json").write_text(
            '{"providers":["ollama"],"model":"gemma4:12b"}', encoding="utf-8")
        for script in (
            "kb-mcp.py",
            "kb-retrieve.py",
            "kb-presearch.py",
            "build-kb-index.py",
            "quiet-hook.py",
        ):
            (self.vault / ".claude" / "scripts" / script).write_text("# test\n", encoding="utf-8")
        self.saved = {k: os.environ.get(k) for k in (
            "HOME", "USERPROFILE", "CODEX_HOME", "OPENCODE_CONFIG_DIR", "COPILOT_HOME")}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ["CODEX_HOME"] = str(self.tmp / ".codex")
        os.environ["OPENCODE_CONFIG_DIR"] = str(self.tmp / ".config" / "opencode")
        os.environ["COPILOT_HOME"] = str(self.tmp / ".copilot")

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_codex_install_creates_native_skills_compat_prompts_and_mcp(self):
        self.m.install_codex(REPO_ROOT, self.vault)
        home = self.tmp
        codex = home / ".codex"
        self.assertTrue((home / ".agents" / "skills" / "kennisbank-upgrade" / "SKILL.md").is_file())
        self.assertTrue((home / ".agents" / "skills" / "sessielog" / "SKILL.md").is_file())
        self.assertTrue((home / ".agents" / "skills" / "sessiestart" / "SKILL.md").is_file())
        self.assertTrue((codex / "prompts" / "sessiestart.md").is_file())
        self.assertTrue((codex / "prompts" / "weeklog.md").is_file())
        self.assertTrue((codex / "prompts" / "timeline.md").is_file())
        self.assertTrue((codex / "prompts" / "watdeedik.md").is_file())
        self.assertFalse((codex / "hooks.json").exists())
        prompt = (codex / "prompts" / "sessiestart.md").read_text(encoding="utf-8")
        self.assertIn("description: Load KennisBank session-start context.", prompt)
        skill = (home / ".agents" / "skills" / "sessiestart" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("name: sessiestart", skill)
        self.assertIn('argument-hint: "[ARGUMENTS]"', skill)
        config = (codex / "config.toml").read_text(encoding="utf-8")
        self.assertIn("[mcp_servers.kennisbank]", config)
        self.assertIn(str(self.vault).replace("\\", "/"), config)

    def test_codex_install_removes_only_kennisbank_hooks(self):
        codex = self.tmp / ".codex"
        codex.mkdir(parents=True)
        hooks_path = codex / "hooks.json"
        hooks_path.write_text(json.dumps({
            "description": "user hooks",
            "hooks": {
                "SessionStart": [{
                    "hooks": [
                        {"type": "command", "command": "echo user-hook"},
                        {
                            "type": "command",
                            "command": (
                                "py -3 C:/old-vault/.claude/scripts/quiet-hook.py "
                                "--client codex C:/old-vault/.claude/scripts/build-kb-index.py"
                            ),
                        },
                    ],
                }],
                "Stop": [{
                    "hooks": [{
                        "type": "command",
                        "command": "py -3 C:/old-vault/.claude/scripts/kb-usage-scan.py",
                    }],
                }],
            },
        }), encoding="utf-8")

        self.m.install_codex(REPO_ROOT, self.vault)

        text = hooks_path.read_text(encoding="utf-8")
        self.assertIn("echo user-hook", text)
        self.assertNotIn("build-kb-index.py", text)
        self.assertNotIn("kb-usage-scan.py", text)

    def test_codex_mcp_repair_does_not_duplicate_env_subtable(self):
        codex = self.tmp / ".codex"
        codex.mkdir(parents=True)
        (codex / "config.toml").write_text(
            """
model = "gpt-5"

[mcp_servers.kennisbank]
command = "py"
args = ["-3", "old/kb-mcp.py"]

[mcp_servers.kennisbank.env]
KENNISBANK_VAULT = "old"

[mcp_servers.other]
command = "other"
""".lstrip(),
            encoding="utf-8",
        )
        self.m.install_codex(REPO_ROOT, self.vault)
        self.m.install_codex(REPO_ROOT, self.vault)

        config = (codex / "config.toml").read_text(encoding="utf-8")
        self.assertEqual(config.count("[mcp_servers.kennisbank]"), 1)
        self.assertEqual(config.count("[mcp_servers.kennisbank.env]"), 1)
        self.assertIn("[mcp_servers.other]", config)
        self.assertIn(str(self.vault).replace("\\", "/"), config)
        if tomllib is not None:
            tomllib.loads(config)

    def test_opencode_install_creates_commands_skills_plugin_and_mcp(self):
        self.m.install_opencode(REPO_ROOT, self.vault)
        cfg = self.tmp / ".config" / "opencode"
        self.assertTrue((self.tmp / ".agents" / "skills" / "autoresearch" / "SKILL.md").is_file())
        self.assertTrue((cfg / "commands" / "sessielog.md").is_file())
        self.assertTrue((cfg / "commands" / "weeklog.md").is_file())
        self.assertTrue((cfg / "commands" / "timeline.md").is_file())
        self.assertTrue((cfg / "commands" / "watdeedik.md").is_file())
        self.assertTrue((cfg / "plugins" / "kennisbank.js").is_file())
        data = json.loads((cfg / "opencode.json").read_text(encoding="utf-8"))
        self.assertIn("kennisbank", data["mcp"])
        self.assertNotIn("plugin", data, "local OpenCode plugins load from plugins/ automatically")
        self.assertEqual(data["mcp"]["kennisbank"]["environment"]["KENNISBANK_VAULT"],
                         str(self.vault).replace("\\", "/"))

    def test_copilot_install_creates_surfaces_and_validates(self):
        info = self.m.install_copilot(REPO_ROOT, self.vault)
        home = self.tmp / ".copilot"
        self.assertTrue((home / "mcp-config.json").is_file())
        self.assertFalse((home / "hooks" / "kennisbank.json").exists())
        self.assertTrue((home / "copilot-instructions.md").is_file())
        self.assertTrue((home / "agents" / "kennisbank.agent.md").is_file())
        self.assertTrue((self.tmp / ".agents" / "skills" / "autoresearch" / "SKILL.md").is_file())
        self.assertTrue((self.tmp / ".agents" / "skills" / "sessielog" / "SKILL.md").is_file())
        self.assertTrue((self.tmp / ".agents" / "skills" / "sessiestart" / "SKILL.md").is_file())
        mcp = json.loads((home / "mcp-config.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp["mcpServers"]["kennisbank"]["env"]["KENNISBANK_VAULT"],
                         str(self.vault).replace("\\", "/"))
        # capture hook script present in repo so the deployed hook is safe.
        self.assertTrue((REPO_ROOT / "scripts" / "kb-copilot-capture.py").is_file())

    def test_copilot_install_is_idempotent(self):
        self.m.install_copilot(REPO_ROOT, self.vault)
        self.m.install_copilot(REPO_ROOT, self.vault)
        home = self.tmp / ".copilot"
        mcp = json.loads((home / "mcp-config.json").read_text(encoding="utf-8"))
        self.assertEqual(list(mcp["mcpServers"].keys()).count("kennisbank"), 1)

    def test_validate_files_copilot_branch(self):
        # deployed vault files the shared validator checks.
        for f in ("build-activity-index.py", "kb-activity.py", "kb-activity-eval.py",
                  "kb-copilot-capture.py"):
            (self.vault / ".claude" / "scripts" / f).write_text("# test\n", encoding="utf-8")
        for f in ("kennisbank-embed.json", "kennisbank-llm.json"):
            pass  # already written in setUp
        self.m.install_copilot(REPO_ROOT, self.vault)
        errors = [e for e in self.m.validate_files(REPO_ROOT, self.vault, ["copilot"])
                  if "Copilot" in e or "copilot" in e]
        self.assertEqual(errors, [], errors)

    def test_configure_openrouter_writes_config_and_user_secret(self):
        self.m.configure_llm(
            self.vault,
            "openrouter",
            model="openai/gpt-5.2",
            api_key_env="OPENROUTER_API_KEY",
            api_key_value="fake-openrouter-token-for-test",
        )
        cfg = json.loads((self.vault / ".claude" / "kennisbank-llm.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["providers"], ["openrouter"])
        self.assertEqual(cfg["endpoint"], "https://openrouter.ai/api/v1")
        self.assertEqual(cfg["api_key_env"], "OPENROUTER_API_KEY")
        self.assertNotIn("fake-openrouter-token-for-test", json.dumps(cfg))
        secrets = json.loads((self.tmp / ".config" / "kennisbank" / "secrets.json").read_text(encoding="utf-8"))
        self.assertEqual(secrets["OPENROUTER_API_KEY"], "fake-openrouter-token-for-test")

    def test_validate_mcp_runtime_reports_missing_dependency(self):
        def fake_run(args, **_kwargs):
            return subprocess.CompletedProcess(args, 1, "", "No module named mcp")

        with patch.object(self.m.subprocess, "run", side_effect=fake_run):
            errors = self.m.validate_mcp_runtime(self.vault)

        self.assertEqual(len(errors), 1)
        self.assertIn("MCP dependency missing", errors[0])
        self.assertIn("pip install mcp==1.28.1", errors[0])

    def test_validate_mcp_runtime_reports_handshake_failure(self):
        calls = []

        def fake_run(args, **_kwargs):
            calls.append(args)
            if len(calls) == 1:
                return subprocess.CompletedProcess(args, 0, "", "")
            return subprocess.CompletedProcess(args, 1, "", "missing MCP tools: capture")

        with patch.object(self.m.subprocess, "run", side_effect=fake_run):
            errors = self.m.validate_mcp_runtime(self.vault)

        self.assertEqual(len(errors), 1)
        self.assertIn("MCP handshake failed", errors[0])
        self.assertIn("missing MCP tools: capture", errors[0])

    def test_validate_mcp_runtime_success(self):
        calls = []

        def fake_run(args, **_kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "MCP handshake OK: capture, recall", "")

        with patch.object(self.m.subprocess, "run", side_effect=fake_run):
            errors = self.m.validate_mcp_runtime(self.vault)

        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()

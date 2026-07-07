import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

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
        for script in ("kb-mcp.py", "kb-retrieve.py", "kb-presearch.py", "build-kb-index.py"):
            (self.vault / ".claude" / "scripts" / script).write_text("# test\n", encoding="utf-8")
        self.saved = {k: os.environ.get(k) for k in (
            "HOME", "USERPROFILE", "CODEX_HOME", "OPENCODE_CONFIG_DIR")}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ["CODEX_HOME"] = str(self.tmp / ".codex")
        os.environ["OPENCODE_CONFIG_DIR"] = str(self.tmp / ".config" / "opencode")

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_codex_install_creates_skills_prompts_hooks_and_mcp(self):
        self.m.install_codex(REPO_ROOT, self.vault)
        home = self.tmp
        codex = home / ".codex"
        self.assertTrue((home / ".agents" / "skills" / "kennisbank-upgrade" / "SKILL.md").is_file())
        self.assertTrue((codex / "prompts" / "sessiestart.md").is_file())
        hooks = json.loads((codex / "hooks.json").read_text(encoding="utf-8"))
        hook_text = json.dumps(hooks)
        self.assertIn("kb-retrieve.py", hook_text)
        self.assertIn("kb-presearch.py", hook_text)
        config = (codex / "config.toml").read_text(encoding="utf-8")
        self.assertIn("[mcp_servers.kennisbank]", config)
        self.assertIn(str(self.vault).replace("\\", "/"), config)

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
        self.assertTrue((cfg / "plugins" / "kennisbank.js").is_file())
        data = json.loads((cfg / "opencode.json").read_text(encoding="utf-8"))
        self.assertIn("kennisbank", data["mcp"])
        self.assertNotIn("plugin", data, "local OpenCode plugins load from plugins/ automatically")
        self.assertEqual(data["mcp"]["kennisbank"]["environment"]["KENNISBANK_VAULT"],
                         str(self.vault).replace("\\", "/"))

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


if __name__ == "__main__":
    unittest.main()

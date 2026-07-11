"""Tests for the multi-agent status summary (scripts/agent-status.py, TASK-26.13)."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "agent-status.py"


def _load():
    spec = importlib.util.spec_from_file_location("agent_status", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class AgentStatusTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-status-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        self.saved = {k: os.environ.get(k) for k in (
            "HOME", "USERPROFILE", "CODEX_HOME", "OPENCODE_CONFIG_DIR", "COPILOT_HOME",
            "KENNISBANK_COPILOT_BIN")}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ["CODEX_HOME"] = str(self.tmp / ".codex")
        os.environ["OPENCODE_CONFIG_DIR"] = str(self.tmp / ".config" / "opencode")
        os.environ["COPILOT_HOME"] = str(self.tmp / ".copilot")
        os.environ.pop("KENNISBANK_COPILOT_BIN", None)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _row(self, report, agent):
        return next(r for r in report["agents"] if r["agent"] == agent)

    def test_copilot_not_installed_is_skipped(self):
        os.environ["KENNISBANK_COPILOT_BIN"] = str(self.tmp / "nope")
        report = self.m.collect(["copilot"])
        row = self._row(report, "copilot")
        self.assertFalse(row["configured"])
        self.assertIn("npm install -g @github/copilot", row["detail"])

    def test_copilot_configured(self):
        # write a copilot mcp-config with kennisbank so detect() sees it registered.
        cfg = self.tmp / ".copilot" / "mcp-config.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text(json.dumps({"mcpServers": {"kennisbank": {"type": "local"}}}), encoding="utf-8")
        report = self.m.collect(["copilot"])
        self.assertTrue(self._row(report, "copilot")["configured"])

    def test_codex_configured_and_opencode_not(self):
        codex = self.tmp / ".codex"
        codex.mkdir(parents=True)
        (codex / "config.toml").write_text("[mcp_servers.kennisbank]\ncommand='py'\n", encoding="utf-8")
        report = self.m.collect(["codex", "opencode"])
        self.assertTrue(self._row(report, "codex")["configured"])
        self.assertTrue(self._row(report, "codex")["mcp"])
        self.assertFalse(self._row(report, "opencode")["configured"])

    def test_claude_configured(self):
        cl = self.tmp / ".claude"
        cl.mkdir(parents=True)
        (cl / "settings.json").write_text(
            json.dumps({"hooks": {"x": "kb-retrieve.py"}, "env": {"KENNISBANK_VAULT": "x"}}),
            encoding="utf-8")
        report = self.m.collect(["claude"])
        self.assertTrue(self._row(report, "claude")["configured"])

    def test_rollup_counts_and_render(self):
        report = self.m.collect(["claude", "codex", "opencode", "copilot"])
        self.assertEqual(report["total"], 4)
        self.assertIn("configured", report)
        text = self.m.render(report)
        self.assertIn("KennisBank multi-agent status", text)
        self.assertIn("summary:", text)

    def test_json_cli(self):
        rc = self.m.main(["--agents", "copilot", "--json"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

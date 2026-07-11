"""Copilot integration e2e / consolidation harness (TASK-26.10).

Fills the gaps left by the per-layer suites:
- a REAL fake `copilot` binary fixture (not a mock) exercising probe_cli through
  version + `mcp list` + a failure mode + exit codes (AC#2);
- a Windows-style vault path case for the real vault D:\\...\\Kluis (AC#5);
- a regression proof that installing Copilot alongside Codex leaves the Codex
  config untouched (AC#4);
- an OPT-IN live smoke against a real copilot (AC#3): skipped unless
  KB_COPILOT_LIVE=1 and copilot is on PATH, so CI never fails without it.

All hermetic tests use temp HOME/CODEX/OPENCODE/COPILOT dirs and never touch the
real ~/.copilot or vault (DoD#3).
"""
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IS_WIN = os.name == "nt"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _write_fake_copilot(path: Path) -> Path:
    """A real fake `copilot` binary honoring --version and `mcp list`, with a
    FAKE_COPILOT_FAIL env switch. Returns the executable path."""
    if IS_WIN:
        exe = path.with_suffix(".cmd")
        exe.write_text(
            "@echo off\r\n"
            "if \"%~1\"==\"--version\" (echo GitHub Copilot CLI 1.0.70.& exit /b 0)\r\n"
            "if \"%~1\"==\"mcp\" if \"%~2\"==\"list\" (\r\n"
            "  if defined FAKE_COPILOT_FAIL (echo boom& exit /b 3)\r\n"
            "  echo User servers:& echo   kennisbank ^(local^)& exit /b 0\r\n"
            ")\r\n"
            "exit /b 0\r\n",
            encoding="utf-8",
        )
    else:
        exe = path
        exe.write_text(
            "#!/usr/bin/env bash\n"
            'if [ "$1" = "--version" ]; then echo "GitHub Copilot CLI 1.0.70."; exit 0; fi\n'
            'if [ "$1" = "mcp" ] && [ "$2" = "list" ]; then\n'
            '  if [ -n "$FAKE_COPILOT_FAIL" ]; then echo boom; exit 3; fi\n'
            '  echo "User servers:"; echo "  kennisbank (local)"; exit 0\n'
            "fi\nexit 0\n",
            encoding="utf-8",
        )
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    return exe


class CopilotE2ETest(unittest.TestCase):
    def setUp(self):
        self.cp = _load("_copilot", REPO_ROOT / "scripts" / "_copilot.py")
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-e2e-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        self.saved = {k: os.environ.get(k) for k in (
            "HOME", "USERPROFILE", "COPILOT_HOME", "KENNISBANK_COPILOT_BIN", "FAKE_COPILOT_FAIL")}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ["COPILOT_HOME"] = str(self.tmp / ".copilot")
        os.environ.pop("KENNISBANK_COPILOT_BIN", None)
        os.environ.pop("FAKE_COPILOT_FAIL", None)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    # AC#2 — fake binary fixture drives probe_cli for real (no mock).
    def test_fake_binary_probe_ok(self):
        fake = _write_fake_copilot(self.tmp / "copilot")
        os.environ["KENNISBANK_COPILOT_BIN"] = str(fake)
        self.cp.install(self.vault)  # register so `mcp list` "sees" kennisbank
        out = self.cp.probe_cli(self.vault)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["version"], "1.0.70")
        self.assertTrue(out["mcp_listed"])

    def test_fake_binary_mcp_list_failure(self):
        fake = _write_fake_copilot(self.tmp / "copilot")
        os.environ["KENNISBANK_COPILOT_BIN"] = str(fake)
        os.environ["FAKE_COPILOT_FAIL"] = "1"
        out = self.cp.probe_cli(self.vault)
        # non-zero exit from `mcp list` -> kennisbank not seen -> not ok
        self.assertNotEqual(out["status"], "ok")
        self.assertFalse(out["mcp_listed"])

    # AC#5 — Windows-style vault path for the real Kluis vault.
    def test_windows_style_vault_path(self):
        win_vault = r"D:\Users\Robert\Documents\Claude\Projects\Kluis"
        report = self.cp.install(win_vault)
        mcp = json.loads((self.tmp / ".copilot" / "mcp-config.json").read_text(encoding="utf-8"))
        env_vault = mcp["mcpServers"]["kennisbank"]["env"]["KENNISBANK_VAULT"]
        self.assertEqual(env_vault, "D:/Users/Robert/Documents/Claude/Projects/Kluis")
        self.assertNotIn("\\", env_vault, "vault must be posix-normalized in config")
        self.assertEqual(self.cp.validate_config(win_vault), [])

    # AC#4 — installing Copilot must not regress the Codex config.
    def test_copilot_install_does_not_regress_codex(self):
        iae = _load("install_agent_envs", REPO_ROOT / "scripts" / "install-agent-envs.py")
        os.environ["CODEX_HOME"] = str(self.tmp / ".codex")
        try:
            for s in ("kb-mcp.py", "kb-retrieve.py", "kb-presearch.py", "build-kb-index.py"):
                (self.vault / ".claude" / "scripts" / s).write_text("# t\n", encoding="utf-8")
            iae.install_codex(REPO_ROOT, self.vault)
            codex_before = (self.tmp / ".codex" / "config.toml").read_text(encoding="utf-8")
            iae.install_copilot(REPO_ROOT, self.vault)
            codex_after = (self.tmp / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertEqual(codex_before, codex_after, "Copilot install must not touch Codex config")
            self.assertIn("[mcp_servers.kennisbank]", codex_after)
        finally:
            os.environ.pop("CODEX_HOME", None)

    # AC#3 — opt-in live smoke; skipped unless explicitly enabled.
    @unittest.skipUnless(os.environ.get("KB_COPILOT_LIVE") == "1" and shutil.which("copilot"),
                         "live smoke opt-in: set KB_COPILOT_LIVE=1 with copilot on PATH")
    def test_live_smoke(self):
        self.cp.install(self.vault)
        out = self.cp.probe_cli(self.vault)
        self.assertIn(out["status"], ("ok", "version_old", "not_logged_in", "mcp_not_listed"))


if __name__ == "__main__":
    unittest.main()

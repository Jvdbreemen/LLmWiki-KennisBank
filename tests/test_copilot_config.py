"""Hermetic tests for the Copilot config layer (scripts/_copilot.py, TASK-26.2).

Every test runs against a temporary COPILOT_HOME/HOME so the real ~/.copilot is
never touched (DoD#2). Covers: missing files, existing unmanaged content,
existing managed content, malformed config, dry-run, backup/rollback, detection,
and idempotency.
"""
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = REPO_ROOT / "scripts" / "_copilot.py"


def _load():
    spec = importlib.util.spec_from_file_location("_copilot", MODULE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CopilotConfigTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-copilot-"))
        self.home = self.tmp / ".copilot"
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        self.saved = {k: os.environ.get(k) for k in (
            "HOME", "USERPROFILE", "COPILOT_HOME", "KENNISBANK_COPILOT_BIN")}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ["COPILOT_HOME"] = str(self.home)
        os.environ.pop("KENNISBANK_COPILOT_BIN", None)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- detection ---------------------------------------------------------

    def test_copilot_home_honors_env(self):
        self.assertEqual(str(self.m.copilot_home()), str(self.m._norm_path(self.home)))

    def test_detect_no_binary(self):
        os.environ["KENNISBANK_COPILOT_BIN"] = str(self.tmp / "does-not-exist")
        d = self.m.detect()
        self.assertFalse(d["installed"])
        self.assertIsNone(d["version"])
        self.assertFalse(d["version_ok"])
        self.assertFalse(d["kennisbank_registered"])

    def test_detect_fake_binary_version(self):
        # A fake copilot that prints a version >= MIN_VERSION.
        fake = self.tmp / ("copilot.cmd" if os.name == "nt" else "copilot")
        if os.name == "nt":
            fake.write_text("@echo GitHub Copilot CLI 1.0.70.\n", encoding="utf-8")
        else:
            fake.write_text("#!/usr/bin/env bash\necho 'GitHub Copilot CLI 1.0.70.'\n",
                            encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["KENNISBANK_COPILOT_BIN"] = str(fake)
        d = self.m.detect()
        self.assertTrue(d["installed"])
        self.assertEqual(d["version"], "1.0.70")
        self.assertTrue(d["version_ok"])

    def test_detect_old_version_not_ok(self):
        self.assertFalse((1, 0, 21) >= self.m.MIN_VERSION)
        self.assertTrue((1, 0, 70) >= self.m.MIN_VERSION)

    # --- install: missing files (create) -----------------------------------

    def test_install_creates_all_surfaces(self):
        report = self.m.install(self.vault)
        self.assertTrue(report["changed"])
        self.assertTrue((self.home / "mcp-config.json").is_file())
        self.assertTrue((self.home / "hooks" / "kennisbank.json").is_file())
        self.assertTrue((self.home / "copilot-instructions.md").is_file())
        self.assertTrue((self.home / "agents" / "kennisbank.agent.md").is_file())

        mcp = json.loads((self.home / "mcp-config.json").read_text(encoding="utf-8"))
        self.assertIn("kennisbank", mcp["mcpServers"])
        self.assertEqual(mcp["mcpServers"]["kennisbank"]["type"], "local")
        self.assertEqual(mcp["mcpServers"]["kennisbank"]["env"]["KENNISBANK_VAULT"],
                         str(self.vault).replace("\\", "/"))

        hooks = json.loads((self.home / "hooks" / "kennisbank.json").read_text(encoding="utf-8"))
        self.assertEqual(hooks["version"], 1)
        blob = json.dumps(hooks)
        self.assertIn("kb-copilot-capture.py", blob)
        self.assertIn("build-activity-index.py", blob)
        # cross-platform: both shell keys present.
        entry = hooks["hooks"]["sessionStart"][0]
        self.assertIn("bash", entry)
        self.assertIn("powershell", entry)
        self.assertIn("quiet-hook.py", entry["bash"])
        self.assertIn("quiet-hook.py", entry["powershell"])

    def test_agent_profile_uses_dot_agent_md_extension(self):
        self.m.install(self.vault)
        self.assertTrue((self.home / "agents" / "kennisbank.agent.md").is_file())
        self.assertFalse((self.home / "agents" / "kennisbank.md").exists())

    # --- idempotency + dry-run ---------------------------------------------

    def test_install_idempotent(self):
        self.m.install(self.vault)
        report2 = self.m.install(self.vault)
        self.assertFalse(report2["changed"])
        for r in report2["results"].values():
            self.assertEqual(r["action"], "skipped")

    def test_dry_run_writes_nothing(self):
        report = self.m.install(self.vault, dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertTrue(report["changed"])  # would change
        self.assertFalse(self.home.exists(), "dry-run must not create COPILOT_HOME")

    # --- existing unmanaged content is preserved ---------------------------

    def test_mcp_preserves_other_servers(self):
        mcp_path = self.home / "mcp-config.json"
        mcp_path.parent.mkdir(parents=True)
        mcp_path.write_text(json.dumps({
            "mcpServers": {"other": {"type": "local", "command": "x", "args": []}}
        }), encoding="utf-8")
        self.m.ensure_mcp(self.home, self.vault)
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        self.assertIn("other", data["mcpServers"])
        self.assertIn("kennisbank", data["mcpServers"])

    def test_instructions_preserve_user_content(self):
        ins = self.home / "copilot-instructions.md"
        ins.parent.mkdir(parents=True)
        ins.write_text("# My own rules\nAlways be nice.\n", encoding="utf-8")
        self.m.ensure_instructions(self.home, self.vault)
        text = ins.read_text(encoding="utf-8")
        self.assertIn("My own rules", text)
        self.assertIn(self.m.KB_START, text)
        self.assertIn("KENNISBANK_VAULT", text)

    def test_agent_profile_unmanaged_file_left_intact(self):
        prof = self.home / "agents" / "kennisbank.agent.md"
        prof.parent.mkdir(parents=True)
        prof.write_text("# user's own kennisbank agent\n", encoding="utf-8")
        res = self.m.ensure_agent_profile(self.home, self.vault)
        self.assertEqual(res["action"], "skipped")
        self.assertEqual(prof.read_text(encoding="utf-8"), "# user's own kennisbank agent\n")

    # --- existing managed content (update on vault change) ------------------

    def test_managed_block_updates_on_vault_change(self):
        self.m.ensure_instructions(self.home, self.vault)
        other = self.tmp / "OtherVault"
        (other / ".claude" / "scripts").mkdir(parents=True)
        res = self.m.ensure_instructions(self.home, other)
        self.assertEqual(res["action"], "updated")
        text = (self.home / "copilot-instructions.md").read_text(encoding="utf-8")
        self.assertIn("OtherVault", text)
        self.assertEqual(text.count(self.m.KB_START), 1, "no duplicate managed block")

    # --- malformed config fails open ---------------------------------------

    def test_malformed_json_fails_open(self):
        mcp_path = self.home / "mcp-config.json"
        mcp_path.parent.mkdir(parents=True)
        mcp_path.write_text("{ this is not valid json ", encoding="utf-8")
        res = self.m.ensure_mcp(self.home, self.vault)
        self.assertIn(res["action"], ("created", "updated"))
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        self.assertIn("kennisbank", data["mcpServers"])

    # --- backup + rollback --------------------------------------------------

    def test_backup_created_and_restore(self):
        ins = self.home / "copilot-instructions.md"
        ins.parent.mkdir(parents=True)
        ins.write_text("original user content\n", encoding="utf-8")
        self.m.ensure_instructions(self.home, self.vault)
        bak = ins.with_name(ins.name + self.m.BACKUP_SUFFIX)
        self.assertTrue(bak.is_file(), "a backup must exist after mutating a file")
        self.assertEqual(bak.read_text(encoding="utf-8"), "original user content\n")
        self.assertTrue(self.m.restore_backup(ins))
        self.assertEqual(ins.read_text(encoding="utf-8"), "original user content\n")

    def test_remove_reverses_install_preserving_user_data(self):
        # user MCP server + user hook event that must survive removal.
        self.m.install(self.vault)
        mcp_path = self.home / "mcp-config.json"
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        data["mcpServers"]["other"] = {"type": "local", "command": "x", "args": []}
        mcp_path.write_text(json.dumps(data), encoding="utf-8")

        report = self.m.remove(self.vault)
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        self.assertNotIn("kennisbank", data["mcpServers"])
        self.assertIn("other", data["mcpServers"])
        # instructions/agent managed blocks gone.
        self.assertNotIn(self.m.KB_START,
                         (self.home / "copilot-instructions.md").read_text(encoding="utf-8"))

    # --- probe_cli status distinctions (mocked, no GitHub login) -----------

    def _fake_bin(self):
        b = self.tmp / "copilot-fake"
        b.write_text("x", encoding="utf-8")
        os.environ["KENNISBANK_COPILOT_BIN"] = str(b)
        return b

    def _patch_run(self, version_text, mcp_text, mcp_rc=0):
        from unittest.mock import patch

        def run(cmd, **_kw):
            if "--version" in cmd:
                return subprocess.CompletedProcess(cmd, 0, version_text, "")
            if "mcp" in cmd:
                return subprocess.CompletedProcess(cmd, mcp_rc, mcp_text, "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        return patch.object(self.m.subprocess, "run", side_effect=run)

    def test_probe_copilot_missing(self):
        os.environ["KENNISBANK_COPILOT_BIN"] = str(self.tmp / "nope")
        out = self.m.probe_cli(self.vault)
        self.assertEqual(out["status"], "copilot_missing")
        self.assertFalse(out["installed"])

    def test_probe_platform_binary_missing(self):
        self._fake_bin()
        with self._patch_run("GitHub Copilot CLI: no platform package found", ""):
            out = self.m.probe_cli(self.vault)
        self.assertEqual(out["status"], "platform_binary_missing")

    def test_probe_ok(self):
        self._fake_bin()
        with self._patch_run("GitHub Copilot CLI 1.0.70.", "User servers:\n  kennisbank (local)"):
            out = self.m.probe_cli(self.vault)
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["mcp_listed"])
        self.assertTrue(out["version_ok"])

    def test_probe_version_old(self):
        self._fake_bin()
        with self._patch_run("GitHub Copilot CLI 1.0.21.", "  kennisbank (local)"):
            out = self.m.probe_cli(self.vault)
        self.assertEqual(out["status"], "version_old")
        self.assertFalse(out["version_ok"])

    def test_probe_not_logged_in(self):
        self._fake_bin()
        with self._patch_run("GitHub Copilot CLI 1.0.70.", "Please run /login to authenticate"):
            out = self.m.probe_cli(self.vault)
        self.assertEqual(out["status"], "not_logged_in")
        self.assertFalse(out["mcp_listed"])

    def test_probe_mcp_not_listed(self):
        self._fake_bin()
        with self._patch_run("GitHub Copilot CLI 1.0.70.", "User servers:\n  other (local)"):
            out = self.m.probe_cli(self.vault)
        self.assertEqual(out["status"], "mcp_not_listed")

    # --- validate_config ---------------------------------------------------

    def test_validate_config_reports_missing_and_clean(self):
        self.assertTrue(self.m.validate_config(self.vault))  # nothing installed yet
        self.m.install(self.vault)
        self.assertEqual(self.m.validate_config(self.vault), [])

    def test_validate_config_flags_wrong_vault(self):
        self.m.install(self.vault)
        other = self.tmp / "Other"
        (other / ".claude" / "scripts").mkdir(parents=True)
        errs = self.m.validate_config(other)
        self.assertTrue(any("KENNISBANK_VAULT" in e for e in errs))

    # --- instructions / agent profile co-existence (TASK-26.4) -------------

    def test_install_does_not_touch_shared_agents_or_claude_md(self):
        # Copilot integration must not inject copilot-only content into the
        # shared AGENTS.md / CLAUDE.md that Claude/Codex/OpenCode also read.
        agents_md = self.home / "AGENTS.md"
        agents_md.parent.mkdir(parents=True, exist_ok=True)
        agents_md.write_text("# shared agents rules\nBe careful.\n", encoding="utf-8")
        claude_md = self.vault / "CLAUDE.md"
        claude_md.write_text("# vault CLAUDE.md\n", encoding="utf-8")
        self.m.install(self.vault)
        self.assertEqual(agents_md.read_text(encoding="utf-8"), "# shared agents rules\nBe careful.\n")
        self.assertEqual(claude_md.read_text(encoding="utf-8"), "# vault CLAUDE.md\n")
        # Copilot instructions live in their OWN file, not AGENTS.md.
        self.assertTrue((self.home / "copilot-instructions.md").is_file())

    def test_agent_profile_mentions_required_items(self):
        text = self.m._agent_profile_text(self.vault)
        for needle in (self.m._posix(self.vault), "recall", "capture",
                       "what_did_i_do", "timeline", "fail-open", "rawlog"):
            self.assertIn(needle, text, f"agent profile missing: {needle}")

    def test_agent_profile_uses_marker(self):
        self.m.ensure_agent_profile(self.home, self.vault)
        text = (self.home / "agents" / "kennisbank.agent.md").read_text(encoding="utf-8")
        self.assertIn(self.m.KB_START, text)

    # --- JSON CLI output (DoD#3) -------------------------------------------

    def test_cli_detect_json(self):
        out = subprocess.run(
            [os.sys.executable, str(MODULE), "detect", "--json"],
            capture_output=True, text=True, env={**os.environ},
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        parsed = json.loads(out.stdout)
        self.assertIn("home", parsed)
        self.assertIn("version_ok", parsed)


if __name__ == "__main__":
    unittest.main()

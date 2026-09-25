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
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "install-agent-envs.py"


def _load():
    spec = importlib.util.spec_from_file_location("install_agent_envs", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _make_fake_hermes(bin_dir: Path, behavior: str = "ok") -> Path:
    """Write a fake hermes executable that logs invocations and mimics output."""
    path = bin_dir / "hermes"
    log = bin_dir / "hermes.log"
    script = f'''#!/usr/bin/env python3
import json
import os
import sys

log = {repr(str(log))}
home = os.environ.get("HERMES_HOME", "")
with open(log, "a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv) + "\\n")

args = sys.argv[1:]
if args[:3] == ["mcp", "add", "kennisbank"]:
    print("Found 9 tool(s)")
    print("Enable all 9 tools? [Y/n/select]")
    if {repr(behavior)} != "ok":
        sys.stderr.write("hermes add failed\\n")
        sys.exit(1)
    if home:
        os.makedirs(home, exist_ok=True)
        cfg = os.path.join(home, "config.yaml")
        with open(cfg, "w", encoding="utf-8") as f:
            f.write("mcp_servers:\\n  kennisbank:\\n    command: python\\n")
    sys.exit(0)
elif args[:3] == ["mcp", "test", "kennisbank"]:
    if {repr(behavior)} == "test_fail":
        sys.stderr.write("test handshake failed\\n")
        sys.exit(1)
    print("OK")
    sys.exit(0)
else:
    sys.stderr.write(f"unexpected hermes argv: {{args}}\\n")
    sys.exit(2)
'''
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class HermesInstallTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-hermes-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        (self.vault / ".claude" / "kennisbank-embed.json").write_text(
            '{"provider":"ollama","model":"qwen3-embedding:4b"}', encoding="utf-8")
        (self.vault / ".claude" / "kennisbank-llm.json").write_text(
            '{"providers":["ollama"],"model":"qwen3.5:4b"}', encoding="utf-8")
        for script in ("kb-mcp.py",):
            (self.vault / ".claude" / "scripts" / script).write_text("# test\n", encoding="utf-8")

        self.saved = {k: os.environ.get(k) for k in (
            "HOME", "USERPROFILE", "HERMES_HOME", "KENNISBANK_PYTHON", "PATH")}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ["HERMES_HOME"] = str(self.tmp / ".hermes")
        # Use the test runner's Python so select_capable_interpreter() succeeds.
        os.environ["KENNISBANK_PYTHON"] = sys.executable

        self.bin_dir = self.tmp / "bin"
        self.bin_dir.mkdir()
        # Provide a python3 symlink so the fake hermes shebang resolves, and
        # restrict PATH to the temp bin_dir so tests never call the real hermes.
        (self.bin_dir / "python3").symlink_to(sys.executable)
        os.environ["PATH"] = str(self.bin_dir)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.m._MCP_SELECTION = None

    def test_install_runs_hermes_mcp_add_with_args_last(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        result = self.m.install_hermes(REPO_ROOT, self.vault)
        self.assertTrue(result.get("completed"), result)
        log = json.loads((self.bin_dir / "hermes.log").read_text(encoding="utf-8").strip().splitlines()[0])
        self.assertTrue(log[0].endswith("hermes"))
        self.assertEqual(log[1:4], ["mcp", "add", "kennisbank"])
        args_idx = log.index("--args")
        # --args must be the last option; everything after it is positional args.
        self.assertEqual(log[args_idx + 1], str(self.vault / ".claude" / "scripts" / "kb-mcp.py").replace("\\", "/"))
        self.assertTrue(all(opt not in ("--env", "--connect-timeout") for opt in log[args_idx + 2:]))
        self.assertEqual(result.get("tools"), 9)

    def test_install_reports_missing_hermes_binary(self):
        # PATH is the temp bin_dir, which contains no hermes executable.
        result = self.m.install_hermes(REPO_ROOT, self.vault)
        self.assertFalse(result.get("completed"))
        self.assertIn("hermes binary not found", result.get("error", ""))
        self.assertIn("bash setup.sh --agents hermes", result.get("error", ""))

    def test_install_is_idempotent(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        self.m.install_hermes(REPO_ROOT, self.vault)
        self.m.install_hermes(REPO_ROOT, self.vault)
        log_lines = (self.bin_dir / "hermes.log").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(log_lines), 2, "two installs should invoke hermes twice")
        config_path = Path(os.environ["HERMES_HOME"]) / "config.yaml"
        self.assertEqual(config_path.read_text(encoding="utf-8").count("kennisbank:"), 1)

    def test_validate_hermes_reports_missing_config(self):
        errors = self.m.validate_hermes(self.vault, selected=True)
        self.assertEqual(len(errors), 1)
        self.assertIn("missing Hermes config", errors[0])

    def test_validate_hermes_reports_test_failure(self):
        _make_fake_hermes(self.bin_dir, behavior="test_fail")
        config_path = Path(os.environ["HERMES_HOME"]) / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("mcp_servers:\n  kennisbank:\n    command: python\n", encoding="utf-8")
        errors = self.m.validate_hermes(self.vault, selected=True)
        self.assertEqual(len(errors), 1)
        self.assertIn("hermes mcp test kennisbank failed", errors[0])
        self.assertIn("test handshake failed", errors[0])

    def test_validate_hermes_passes_when_test_passes(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        config_path = Path(os.environ["HERMES_HOME"]) / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("mcp_servers:\n  kennisbank:\n    command: python\n", encoding="utf-8")
        errors = self.m.validate_hermes(self.vault, selected=True)
        self.assertEqual(errors, [])

    def test_validate_hermes_silent_when_not_selected_and_unconfigured(self):
        errors = self.m.validate_hermes(self.vault, selected=False)
        self.assertEqual(errors, [])

    def test_install_deploys_namespaced_skills(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        result = self.m.install_hermes(REPO_ROOT, self.vault)
        self.assertTrue(result.get("completed"), result)
        for skill in ("autoresearch", "kennisbank-contribute", "kennisbank-release"):
            path = Path(os.environ["HERMES_HOME"]) / "skills" / "kennisbank" / skill / "SKILL.md"
            self.assertTrue(path.is_file(), skill)
            text = path.read_text(encoding="utf-8")
            self.assertIn("name:", text)
            self.assertIn("description:", text)

    def test_install_preserves_existing_skills_outside_namespace(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        decoy = Path(os.environ["HERMES_HOME"]) / "skills" / "other" / "decoy"
        decoy.mkdir(parents=True)
        (decoy / "SKILL.md").write_text("---\nname: decoy\ndescription: x\n---\nbody\n", encoding="utf-8")
        self.m.install_hermes(REPO_ROOT, self.vault)
        self.assertTrue((decoy / "SKILL.md").is_file())
        self.assertEqual((decoy / "SKILL.md").read_text(encoding="utf-8"), "---\nname: decoy\ndescription: x\n---\nbody\n")

    def test_install_warns_on_skill_name_collision(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        # A pre-existing skill outside the kennisbank namespace claims the same name.
        decoy = Path(os.environ["HERMES_HOME"]) / "skills" / "other" / "autoresearch"
        decoy.mkdir(parents=True)
        (decoy / "SKILL.md").write_text("---\nname: autoresearch\ndescription: x\n---\nbody\n", encoding="utf-8")
        result = self.m.install_hermes(REPO_ROOT, self.vault)
        warnings = result.get("warnings", [])
        self.assertTrue(any("collision" in w and "autoresearch" in w for w in warnings), warnings)

    def test_install_warns_on_invalid_skill_frontmatter(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        # Use a copy of the repo skills so the real source is never mutated.
        fake_repo = self.tmp / "repo"
        shutil.copytree(REPO_ROOT / "skills", fake_repo / "skills")
        (fake_repo / "skills" / "autoresearch" / "SKILL.md").write_text(
            "---\nno-name-here: x\n---\nbody\n", encoding="utf-8")
        result = self.m.install_hermes(fake_repo, self.vault)
        warnings = result.get("warnings", [])
        self.assertTrue(any("missing frontmatter name" in w for w in warnings), warnings)


if __name__ == "__main__":
    unittest.main()

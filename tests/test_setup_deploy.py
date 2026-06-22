import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _hook_commands(settings, event):
    """All hook command strings registered under `event` in a settings dict."""
    out = []
    for group in settings.get("hooks", {}).get(event, []):
        for h in group.get("hooks", []):
            cmd = h.get("command")
            if cmd is not None:
                out.append(cmd)
    return out


def _bash_path(p: Path) -> str:
    """Convert a path to a form Git Bash accepts.

    On Windows, C:\\Users\\x -> /c/Users/x (drive letter lowercased, backslashes
    to forward slashes). On macOS/Linux the path is already POSIX, so identity.
    """
    if sys.platform.startswith("win"):
        s = str(p).replace("\\", "/")
        if len(s) > 1 and s[1] == ":":
            s = "/" + s[0].lower() + s[2:]
        return s
    return str(p)


def _find_bash() -> str:
    """Locate a usable bash for invoking setup.sh, cross-platform.

    macOS/Linux: the PATH bash. Windows: Git Bash, discovered via
    GIT_INSTALL_ROOT, common per-user/system install paths, or the
    GitForWindows registry key, explicitly rejecting the System32 WSL/Store
    bash stub (a different filesystem namespace where /c/... paths break).
    Skips the test with a clear reason if no suitable bash is found.
    """
    if not sys.platform.startswith("win"):
        return shutil.which("bash") or "bash"
    candidates = []
    root = os.environ.get("GIT_INSTALL_ROOT")
    if root:
        candidates.append(Path(root) / "bin" / "bash.exe")
    localapp = os.environ.get("LOCALAPPDATA")
    if localapp:
        candidates.append(Path(localapp) / "Programs" / "Git" / "bin" / "bash.exe")
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if base:
            candidates.append(Path(base) / "Git" / "bin" / "bash.exe")
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\GitForWindows") as key:
                    install = winreg.QueryValueEx(key, "InstallPath")[0]
                    candidates.append(Path(install) / "bin" / "bash.exe")
            except OSError:
                pass
    except ImportError:
        pass
    for cand in candidates:
        if cand.is_file():
            return str(cand)
    which = shutil.which("bash")
    if which and "system32" not in which.lower():
        return which
    raise unittest.SkipTest(
        "No Git Bash found (install Git for Windows to run this test)"
    )


class SetupDeployTest(unittest.TestCase):
    def run_setup(self):
        tmp = Path(tempfile.mkdtemp(prefix="kb-home-"))
        vault = tmp / "KennisBank"
        env = dict(os.environ)
        # HOME drives the ~/.claude deploy targets; KENNISBANK_VAULT drives the
        # vault. Both must be POSIX-form so Git Bash resolves them correctly.
        env["HOME"] = _bash_path(tmp)
        env["USERPROFILE"] = _bash_path(tmp)
        env["KENNISBANK_VAULT"] = _bash_path(vault)
        bash = _find_bash()
        subprocess.run(
            [bash, "setup.sh", "--yes"],
            cwd=REPO_ROOT, env=env, check=True,
            capture_output=True, text=True,
        )
        return tmp, vault

    def test_doctor_sh_is_deployed(self):
        tmp, vault = self.run_setup()
        try:
            doctor = vault / ".claude" / "scripts" / "doctor.sh"
            self.assertTrue(doctor.is_file(), f"doctor.sh not deployed at {doctor}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_python_scripts_still_deployed(self):
        tmp, vault = self.run_setup()
        try:
            common = vault / ".claude" / "scripts" / "_common.py"
            self.assertTrue(common.is_file(), "_common.py regressed out of deploy")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_new_skills_are_installed(self):
        tmp, vault = self.run_setup()
        try:
            base = tmp / ".claude" / "skills"
            for slug in ("autoresearch", "kennisbank-upgrade", "kennisbank-contribute"):
                skill = base / slug / "SKILL.md"
                self.assertTrue(skill.is_file(), f"{slug} not installed at {skill}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_embedding_scripts_deployed(self):
        tmp, vault = self.run_setup()
        try:
            scripts = vault / ".claude" / "scripts"
            for name in ("_embeddings.py", "kb-retrieve.py", "build-embed-index.py"):
                self.assertTrue((scripts / name).is_file(), f"{name} not deployed")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_embed_config_is_deployed(self):
        tmp, vault = self.run_setup()
        try:
            cfg = vault / ".claude" / "kennisbank-embed.json"
            self.assertTrue(cfg.is_file(), f"kennisbank-embed.json not deployed at {cfg}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_vault_onderhoud_scripts_deployed(self):
        """safe-edit.py, find-similar.py, kb-search.py, conflict-scan.py, context-budget.py."""
        tmp, vault = self.run_setup()
        try:
            scripts = vault / ".claude" / "scripts"
            for name in (
                "safe-edit.py",
                "find-similar.py",
                "kb-search.py",
                "conflict-scan.py",
                "context-budget.py",
            ):
                self.assertTrue(
                    (scripts / name).is_file(),
                    f"{name} not deployed at {scripts / name}",
                )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_vault_onderhoud_commands_deployed(self):
        """reconcile.md, uitdaag.md, brug.md must be installed as slash commands."""
        tmp, vault = self.run_setup()
        try:
            commands = tmp / ".claude" / "commands"
            for name in ("reconcile.md", "uitdaag.md", "brug.md"):
                self.assertTrue(
                    (commands / name).is_file(),
                    f"{name} not installed at {commands / name}",
                )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


    def run_setup_in(self, tmp):
        """Run setup.sh --yes against an existing temp HOME (for re-run tests)."""
        vault = tmp / "KennisBank"
        env = dict(os.environ)
        env["HOME"] = _bash_path(tmp)
        env["USERPROFILE"] = _bash_path(tmp)
        env["KENNISBANK_VAULT"] = _bash_path(vault)
        bash = _find_bash()
        subprocess.run(
            [bash, "setup.sh", "--yes"],
            cwd=REPO_ROOT, env=env, check=True,
            capture_output=True, text=True,
        )
        return tmp, vault

    def run_doctor_in(self, tmp, vault):
        """Run doctor.sh against a temp HOME/vault; return the CompletedProcess."""
        env = dict(os.environ)
        env["HOME"] = _bash_path(tmp)
        env["USERPROFILE"] = _bash_path(tmp)
        env["KENNISBANK_VAULT"] = _bash_path(vault)
        bash = _find_bash()
        return subprocess.run(
            [bash, "scripts/doctor.sh"],
            cwd=REPO_ROOT, env=env, check=False,
            capture_output=True, text=True,
        )

    def test_hooks_registered_in_settings(self):
        tmp, vault = self.run_setup()
        try:
            settings_path = tmp / ".claude" / "settings.json"
            self.assertTrue(settings_path.is_file(), f"settings.json not created at {settings_path}")
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            session = _hook_commands(settings, "SessionStart")
            prompt = _hook_commands(settings, "UserPromptSubmit")
            self.assertTrue(any("build-embed-index.py" in c for c in session),
                            f"build-embed-index.py not on SessionStart: {session}")
            self.assertTrue(any("kb-retrieve.py" in c for c in prompt),
                            f"kb-retrieve.py not on UserPromptSubmit: {prompt}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_doctor_reports_registered_hooks(self):
        tmp, vault = self.run_setup()
        try:
            result = self.run_doctor_in(tmp, vault)
            out = result.stdout
            self.assertRegex(out, r"\[PASS\].*build-embed-index\.py.*registered")
            self.assertRegex(out, r"\[PASS\].*kb-retrieve\.py.*registered")
            self.assertEqual(result.returncode, 0, f"doctor exited {result.returncode}:\n{out}\n{result.stderr}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_doctor_warns_and_exits_clean_when_hooks_missing(self):
        tmp, vault = self.run_setup()
        try:
            settings_path = tmp / ".claude" / "settings.json"
            if settings_path.exists():
                settings_path.unlink()
            result = self.run_doctor_in(tmp, vault)
            self.assertRegex(result.stdout, r"\[WARN\].*retrieval hooks")
            self.assertEqual(result.returncode, 0, f"doctor must exit clean:\n{result.stdout}\n{result.stderr}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_hook_registration_is_idempotent(self):
        tmp = Path(tempfile.mkdtemp(prefix="kb-home-"))
        try:
            self.run_setup_in(tmp)
            self.run_setup_in(tmp)
            settings_path = tmp / ".claude" / "settings.json"
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            session = [c for c in _hook_commands(settings, "SessionStart") if "build-embed-index.py" in c]
            prompt = [c for c in _hook_commands(settings, "UserPromptSubmit") if "kb-retrieve.py" in c]
            self.assertEqual(len(session), 1, f"duplicate SessionStart hooks: {session}")
            self.assertEqual(len(prompt), 1, f"duplicate UserPromptSubmit hooks: {prompt}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_hook_registration_preserves_existing_settings(self):
        tmp = Path(tempfile.mkdtemp(prefix="kb-home-"))
        try:
            claude_dir = tmp / ".claude"
            claude_dir.mkdir(parents=True)
            (claude_dir / "settings.json").write_text(json.dumps({
                "permissions": {"allow": ["Bash(ls:*)"]},
                "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo pre-existing"}]}]},
            }), encoding="utf-8")
            self.run_setup_in(tmp)
            settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(settings["permissions"], {"allow": ["Bash(ls:*)"]})
            session = _hook_commands(settings, "SessionStart")
            self.assertIn("echo pre-existing", session)
            self.assertTrue(any("build-embed-index.py" in c for c in session))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

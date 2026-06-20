import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


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
            for slug in ("kennisbank-upgrade", "kennisbank-contribute"):
                skill = base / slug / "SKILL.md"
                self.assertTrue(skill.is_file(), f"{slug} not installed at {skill}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

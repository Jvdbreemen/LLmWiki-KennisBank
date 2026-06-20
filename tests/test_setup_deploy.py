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
    """Find a bash that properly forwards environment variables on this platform.

    On Windows, prefer Git Bash (which respects env vars via subprocess).
    On macOS/Linux, use the default bash from PATH.
    """
    if sys.platform.startswith("win"):
        # On Windows, look for Git Bash
        git_bash = Path("C:/Program Files/Git/bin/bash.exe")
        if git_bash.exists():
            return str(git_bash)
        # Fallback to PATH bash if Git Bash is not installed
        return "bash"
    return "bash"


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


if __name__ == "__main__":
    unittest.main()

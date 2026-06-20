import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class SetupDeployTest(unittest.TestCase):
    def run_setup(self):
        home = tempfile.mkdtemp(prefix="kb-home-")
        env = dict(os.environ, HOME=home)
        # Windows-style override so the test is HOME-driven on every platform.
        env["USERPROFILE"] = home
        subprocess.run(
            ["bash", "setup.sh", "--yes"],
            cwd=REPO_ROOT, env=env, check=True,
            capture_output=True, text=True,
        )
        return Path(home)

    def test_doctor_sh_is_deployed(self):
        home = self.run_setup()
        try:
            doctor = home / "KennisBank" / ".claude" / "scripts" / "doctor.sh"
            self.assertTrue(doctor.is_file(), f"doctor.sh not deployed at {doctor}")
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_python_scripts_still_deployed(self):
        home = self.run_setup()
        try:
            common = home / "KennisBank" / ".claude" / "scripts" / "_common.py"
            self.assertTrue(common.is_file(), "_common.py regressed out of deploy")
        finally:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

"""setup.sh refuses to run under WSL against a Windows checkout (TASK-259).

On Windows a plain `bash` can resolve to System32's WSL bash. Windows HOME and
KENNISBANK_VAULT do not cross into WSL, so setup would install into the WSL home
instead. The guard runs before the first write, so each refused run must leave
the target vault path absent.
"""
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _deploy_helpers():
    spec = importlib.util.spec_from_file_location(
        "_setup_deploy_helpers", REPO_ROOT / "tests" / "test_setup_deploy.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class SetupWslGuardTest(unittest.TestCase):
    def setUp(self):
        helpers = _deploy_helpers()
        self.bash = helpers._find_bash()
        self.to_bash = helpers._bash_path
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-wsl-guard-"))
        # A vault path whose parent is a regular file: if the guard lets setup
        # through, its first mkdir fails fast instead of installing anything.
        blocker = self.tmp / "blocker"
        blocker.write_text("", encoding="utf-8")
        self.vault = blocker / "vault"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *args, wsl: bool, checkout: str = "/mnt/d/src/LLmWiki-KennisBank"):
        env = dict(os.environ)
        env["HOME"] = self.to_bash(self.tmp)
        env["KENNISBANK_VAULT"] = self.to_bash(self.vault)
        env["KENNISBANK_SETUP_CHECKOUT_DIR"] = checkout
        if wsl:
            env["WSL_DISTRO_NAME"] = "Ubuntu"
        else:
            env.pop("WSL_DISTRO_NAME", None)
        return subprocess.run(
            [self.bash, "setup.sh", "--yes", "--agents", "claude", "--skip-model-check",
             "--skip-doctor", *args],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )

    def test_wsl_with_a_windows_checkout_is_refused_before_any_write(self):
        result = self._run(wsl=True)

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Git Bash", result.stderr)
        self.assertIn("--allow-wsl", result.stderr)
        self.assertNotIn("/vault", result.stdout)

    def test_allow_wsl_lets_a_deliberate_wsl_install_through(self):
        result = self._run("--allow-wsl", wsl=True)

        self.assertNotEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("--allow-wsl", result.stderr)

    def test_a_checkout_inside_wsl_is_not_refused(self):
        result = self._run(wsl=True, checkout="/home/robert/src/LLmWiki-KennisBank")

        self.assertNotEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("--allow-wsl", result.stderr)

    def test_outside_wsl_the_guard_never_fires(self):
        try:
            on_wsl = "microsoft" in Path("/proc/version").read_text().lower()
        except OSError:
            on_wsl = False
        if on_wsl:
            self.skipTest("the host itself is WSL")

        result = self._run(wsl=False)

        self.assertNotEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("--allow-wsl", result.stderr)


if __name__ == "__main__":
    unittest.main()

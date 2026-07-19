"""doctor.sh Copilot section tests (TASK-26.9 AC#5).

Runs the real scripts/doctor.sh against a fixture vault + temp COPILOT_HOME and
asserts the Copilot checks report PASS / not-configured / FAIL correctly. Skips
where bash is unavailable. Hermetic: never touches the real ~/.copilot.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCTOR = REPO_ROOT / "scripts" / "doctor.sh"


def _find_bash():
    """Prefer Git Bash on Windows; reject the WSL filesystem namespace."""
    if os.name != "nt":
        return shutil.which("bash")
    git = shutil.which("git")
    candidates = []
    if git:
        candidates.append(Path(git).resolve().parent.parent / "bin" / "bash.exe")
    for root in (
        os.environ.get("GIT_INSTALL_ROOT"),
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
    ):
        if root:
            base = Path(root)
            candidates.extend(
                (base / "bin" / "bash.exe", base / "Git" / "bin" / "bash.exe")
            )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    bash = shutil.which("bash")
    return bash if bash and "system32" not in bash.lower() else None


BASH = _find_bash()

# Scripts the Copilot doctor block invokes from the vault's .claude/scripts.
VAULT_SCRIPTS = (
    "_copilot.py", "kb-copilot-capture.py", "kb-mcp.py", "kb-activity.py",
    "build-activity-index.py", "_activity.py", "_frontmatter.py", "_vaultpath.py",
)


def _posix(path: Path) -> str:
    s = str(path)
    if os.name == "nt":
        s = s.replace("\\", "/")
        if len(s) > 1 and s[1] == ":":
            s = "/" + s[0].lower() + s[2:]
    return s


@unittest.skipIf(BASH is None, "bash not available")
class CopilotDoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-cdoctor-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        for name in VAULT_SCRIPTS:
            src = REPO_ROOT / "scripts" / name
            if src.is_file():
                shutil.copy2(src, self.vault / ".claude" / "scripts" / name)
        self.saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE", "COPILOT_HOME")}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ["COPILOT_HOME"] = str(self.tmp / ".copilot")

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_doctor(self):
        env = {**os.environ, "KENNISBANK_VAULT": _posix(self.vault),
               "COPILOT_HOME": str(self.tmp / ".copilot")}
        proc = subprocess.run(
            [BASH, "scripts/doctor.sh"], cwd=str(REPO_ROOT), env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
        )
        return proc.stdout + proc.stderr

    def _install_copilot(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("_copilot", REPO_ROOT / "scripts" / "_copilot.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        m.install(self.vault)

    def _copilot_lines(self, out):
        return [l for l in out.splitlines() if "copilot" in l.lower() and "] copilot" in l.lower()]

    def test_not_configured_no_fail(self):
        out = self._run_doctor()
        self.assertIn("not configured", out)
        fails = [l for l in out.splitlines() if "[FAIL]" in l and "copilot" in l.lower()]
        self.assertEqual(fails, [], f"copilot must not FAIL when unconfigured: {fails}")

    def test_configured_pass(self):
        self._install_copilot()
        out = self._run_doctor()
        self.assertRegex(out, r"\[PASS\] copilot config")

    def test_broken_config_fails(self):
        self._install_copilot()
        # break it: remove the managed instructions file so validate_config fails.
        (self.tmp / ".copilot" / "copilot-instructions.md").unlink()
        out = self._run_doctor()
        self.assertRegex(out, r"\[FAIL\] copilot config")


if __name__ == "__main__":
    unittest.main()

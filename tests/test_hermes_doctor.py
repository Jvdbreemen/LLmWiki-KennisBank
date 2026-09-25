"""doctor.sh Hermes section tests.

Runs the real scripts/doctor.sh against a fixture vault + temp HERMES_HOME and
asserts the Hermes checks report PASS / not-configured / FAIL correctly.
Hermetic: never touches the real ~/.hermes.
"""
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCTOR = REPO_ROOT / "scripts" / "doctor.sh"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _proc import run_bounded  # noqa: E402

DOCTOR_TIMEOUT = 120


def _find_bash():
    if os.name != "nt":
        return shutil.which("bash")
    return None


BASH = _find_bash()

VAULT_SCRIPTS = (
    "_mcp_probe.py", "kb-mcp.py", "kb-activity.py", "build-activity-index.py",
    "_activity.py", "_frontmatter.py", "_vaultpath.py", "_embeddings.py",
    "_settings.py", "_kbindex.py", "_usage.py", "_llm.py", "_llmjson.py",
    "_common.py", "_provenance.py", "_outcome.py",
)


def _posix(path: Path) -> str:
    s = str(path)
    if os.name == "nt":
        s = s.replace("\\", "/")
        if len(s) > 1 and s[1] == ":":
            s = "/" + s[0].lower() + s[2:]
    return s


def _make_fake_hermes(bin_dir: Path, behavior: str = "ok") -> Path:
    path = bin_dir / "hermes"
    log = bin_dir / "hermes.log"
    script = f'''#!/usr/bin/env python3
import json
import os
import sys

log = {repr(str(log))}
with open(log, "a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv) + "\\n")

args = sys.argv[1:]
if args[:3] == ["mcp", "test", "kennisbank"]:
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


@unittest.skipIf(BASH is None, "bash not available")
class HermesDoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-hdoctor-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        for name in VAULT_SCRIPTS:
            src = REPO_ROOT / "scripts" / name
            if src.is_file():
                shutil.copy2(src, self.vault / ".claude" / "scripts" / name)
        # Embed config needed by _embeddings probe path.
        (self.vault / ".claude" / "kennisbank-embed.json").write_text(
            '{"provider":"ollama","model":"qwen3-embedding:4b"}', encoding="utf-8")
        (self.vault / ".claude" / "kennisbank-llm.json").write_text(
            '{"providers":["ollama"],"model":"qwen3.5:4b"}', encoding="utf-8")

        self.saved = {k: os.environ.get(k) for k in (
            "HOME", "USERPROFILE", "HERMES_HOME", "PATH")}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ["HERMES_HOME"] = str(self.tmp / ".hermes")

        self.bin_dir = self.tmp / "bin"
        self.bin_dir.mkdir()
        # Provide a python3 symlink for the fake hermes shebang, and give doctor.sh
        # just enough PATH for core utilities without reaching a real hermes binary.
        (self.bin_dir / "python3").symlink_to(sys.executable)
        os.environ["PATH"] = str(self.bin_dir) + ":/usr/bin:/bin:/usr/local/bin"

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_doctor(self):
        env = {**os.environ, "KENNISBANK_VAULT": _posix(self.vault),
               "HERMES_HOME": str(self.tmp / ".hermes")}
        r = run_bounded([BASH, "scripts/doctor.sh"], cwd=str(REPO_ROOT),
                        env=env, timeout=DOCTOR_TIMEOUT)
        self.assertFalse(
            r.timed_out,
            f"doctor.sh kwam niet binnen {DOCTOR_TIMEOUT}s klaar "
            f"({r.duur:.0f}s). Laatste uitvoer:" + os.linesep + r.output[-2000:])
        return r.output

    def _configure_hermes(self, interpreter=None):
        hermes_home = self.tmp / ".hermes"
        hermes_home.mkdir(parents=True, exist_ok=True)
        interp = interpreter or sys.executable
        config = (
            "mcp_servers:\n"
            "  kennisbank:\n"
            f"    command: {interp}\n"
            f"    args: [{self.vault / '.claude' / 'scripts' / 'kb-mcp.py'}]\n"
        )
        (hermes_home / "config.yaml").write_text(config, encoding="utf-8")

    def _hermes_lines(self, out):
        return [l for l in out.splitlines() if "hermes" in l.lower() and "] hermes" in l.lower()]

    def test_not_configured_no_fail(self):
        out = self._run_doctor()
        self.assertIn("hermes integration", out)
        self.assertIn("not configured", out)
        fails = [l for l in out.splitlines() if "[FAIL]" in l and "hermes" in l.lower()]
        self.assertEqual(fails, [], fails)

    def test_configured_pass(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        self._configure_hermes()
        (self.tmp / ".hermes" / "skills" / "kennisbank" / "autoresearch").mkdir(parents=True)
        (self.tmp / ".hermes" / "skills" / "kennisbank" / "autoresearch" / "SKILL.md").write_text(
            "---\nname: autoresearch\ndescription: x\n---\n", encoding="utf-8")
        (self.tmp / ".hermes" / "SOUL.md").write_text(
            "<!-- BEGIN LLmWiki-KennisBank -->\nblock\n<!-- END LLmWiki-KennisBank -->\n", encoding="utf-8")
        out = self._run_doctor()
        self.assertRegex(out, r"\[PASS\] hermes mcp test")
        self.assertRegex(out, r"\[PASS\] hermes interpreter")
        self.assertRegex(out, r"\[PASS\] hermes skills dir")
        self.assertRegex(out, r"\[PASS\] hermes SOUL\.md")

    def test_missing_binary_fails(self):
        self._configure_hermes()
        # No fake hermes binary on PATH.
        out = self._run_doctor()
        self.assertRegex(out, r"\[FAIL\] hermes cli")

    def test_mcp_test_failure_fails(self):
        _make_fake_hermes(self.bin_dir, behavior="test_fail")
        self._configure_hermes()
        out = self._run_doctor()
        self.assertRegex(out, r"\[FAIL\] hermes mcp test")

    def test_incapable_interpreter_fails(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        # Use a stub interpreter that cannot load sqlite-vec.
        stub = self.bin_dir / "bad-python"
        stub.write_text("#!/bin/sh\necho 'no vec0' >&2\nexit 1\n", encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self._configure_hermes(interpreter=str(stub))
        out = self._run_doctor()
        self.assertRegex(out, r"\[FAIL\] hermes interpreter")

    def test_missing_skills_warns(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        self._configure_hermes()
        (self.tmp / ".hermes" / "SOUL.md").write_text(
            "<!-- BEGIN LLmWiki-KennisBank -->\nblock\n<!-- END LLmWiki-KennisBank -->\n", encoding="utf-8")
        out = self._run_doctor()
        self.assertRegex(out, r"\[WARN\] hermes skills dir")

    def test_missing_soul_warns(self):
        _make_fake_hermes(self.bin_dir, behavior="ok")
        self._configure_hermes()
        (self.tmp / ".hermes" / "skills" / "kennisbank" / "autoresearch").mkdir(parents=True)
        (self.tmp / ".hermes" / "skills" / "kennisbank" / "autoresearch" / "SKILL.md").write_text(
            "---\nname: autoresearch\ndescription: x\n---\n", encoding="utf-8")
        out = self._run_doctor()
        self.assertRegex(out, r"\[WARN\] hermes SOUL\.md")


if __name__ == "__main__":
    unittest.main()

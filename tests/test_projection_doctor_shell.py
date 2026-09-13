"""The actual setup doctor boundary must use bounded, canonical health data."""
from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from tests._proc import run_bounded
from tests.test_copilot_doctor import BASH, _posix

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "projection_doctor_shell_test", SCRIPTS / "kb-projection-doctor.py")
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class ProjectionDoctorShellTest(unittest.TestCase):
    def report(self):
        return {"schema_version": 2, "inventory_check": "not_checked",
                "routes": {"source": "disabled", "experience": "enabled"},
                "forbidden_flags": [],
                "source": {"status": "present", "documents": 3,
                           "integrity": None, "provenance_coverage": None},
                "experience": {
                    "ledger": {"status": "ready", "integrity": "ok",
                               "events": 7, "outcomes": 6, "reviews": 1},
                    "projection": {"status": "ready", "integrity": "ok",
                                   "records": 1, "source_ref_check": "not_checked",
                                   "model_compatibility": "lexical_fallback",
                                   "contradictory_count": 0}}}

    def test_summary_uses_explicit_routes_and_separate_stores(self):
        output = "\n".join(doctor.shell_summary(self.report()))
        self.assertIn("info|source recall|disabled", output)
        self.assertIn("info|experience recall|enabled", output)
        self.assertIn("pass|experience ledger|", output)
        self.assertIn("pass|experience projection|", output)
        self.assertIn("events=7", output)
        self.assertIn("records=1", output)
        self.assertIn("not checked", output)
        self.assertNotIn("pass|source projection|", output)
        self.assertNotIn("coverage=1", output)

    def test_summary_warns_without_echoing_content_or_promoting_missing_stores(self):
        report = self.report()
        report["forbidden_flags"] = ["experience_recall"]
        report["source"] = {"status": "unreadable", "reason": "private query|\nsecret"}
        report["experience"]["ledger"] = {"status": "missing"}
        report["experience"]["projection"]["model_compatibility"] = "mismatch"
        output = "\n".join(doctor.shell_summary(report))
        for label in ("source projection", "experience ledger", "experience projection",
                      "projection policy"):
            self.assertIn("warn|" + label + "|", output)
        self.assertNotIn("private", output)
        self.assertNotIn("secret", output)
        self.assertNotIn("pass|experience", output)

    def test_unknown_schema_is_not_reported_as_healthy(self):
        output = "\n".join(doctor.shell_summary({"schema_version": 1}))
        self.assertIn("warn|projection health|", output)
        self.assertNotIn("pass|", output)

    def test_shell_mode_is_always_fast_even_if_deep_was_requested(self):
        with tempfile.TemporaryDirectory(prefix="kb-doctor-main-") as directory:
            with mock.patch.object(doctor, "health", return_value=self.report()) as health:
                with redirect_stdout(io.StringIO()) as output:
                    doctor.main(["--vault", directory, "--shell-summary", "--deep"])
        self.assertTrue(health.call_args.kwargs["fast"])
        self.assertFalse(health.call_args.kwargs["deep_integrity"])
        self.assertIn("info|source recall|disabled", output.getvalue())

    def test_present_source_with_unknown_checks_is_never_a_pass(self):
        report = self.report()
        report["source"]["integrity"] = "ok"
        output = "\n".join(doctor.shell_summary(report))
        self.assertIn("info|source projection|state=present", output)
        self.assertNotIn("pass|source projection|", output)

    def run_section(self, *, fail=False):
        if BASH is None:
            self.skipTest("Git Bash is unavailable")
        with tempfile.TemporaryDirectory(prefix="kb-projection-shell-") as directory:
            vault = Path(directory) / "vault with spaces"
            scripts = vault / ".claude" / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "kb-projection-doctor.py").write_text(
                "import sys\n"
                "assert '--fast' in sys.argv and '--shell-summary' in sys.argv\n"
                "assert '--vault' in sys.argv\n"
                + ("raise SystemExit(3)\n" if fail else
                   "print('info|source recall|disabled')\n"
                   "print('pass|experience ledger|events=7; integrity=ok')\n"
                   "print('pass|experience projection|records=1; exact refs=not checked')\n"),
                encoding="utf-8")
            # Extract the unchanged entrypoint block, not a reimplementation.
            content = (SCRIPTS / "doctor.sh").read_text(encoding="utf-8")
            block = content.split("# 13e.", 1)[1].split("# Footer.", 1)[0]
            prelude = """set -u
VAULT="$KENNISBANK_VAULT"
SCRIPTS_DIR="$VAULT/.claude/scripts"
report_pass() { printf '[PASS] %s: %s\\n' "$1" "$2"; }
report_info() { printf '[INFO] %s: %s\\n' "$1" "$2"; }
report_warn() { printf '[WARN] %s: %s\\n' "$1" "$2"; }
"""
            runner = Path(directory) / "doctor-section.sh"
            runner.write_text(prelude + "# 13e." + block, encoding="utf-8")
            result = run_bounded([BASH, _posix(runner)], cwd=str(ROOT),
                                 env={**os.environ, "KENNISBANK_VAULT": _posix(vault)},
                                 timeout=20)
            self.assertFalse(result.timed_out, result.output)
            return result.output

    def test_real_shell_section_calls_bounded_canonical_summary(self):
        output = self.run_section()
        self.assertIn("[PASS] experience ledger: events=7", output)
        self.assertIn("[PASS] experience projection: records=1", output)
        self.assertIn("exact refs=not checked", output)
        self.assertIn("[INFO] source recall: disabled", output)

    def test_failed_health_command_is_a_warning_not_a_pass(self):
        output = self.run_section(fail=True)
        self.assertIn("[WARN] projection health:", output)
        self.assertNotIn("[PASS]", output)

    def test_commands_use_installed_namespace_not_root_decoys(self):
        if BASH is None:
            self.skipTest("Git Bash is unavailable")
        names = ("rebuild-source-index", "rebuild-experience", "source-recall",
                 "experience-recall")
        content = (SCRIPTS / "doctor.sh").read_text(encoding="utf-8")
        block = "# 7." + content.split("# 7.", 1)[1].split("# 8.", 1)[0]
        with tempfile.TemporaryDirectory(prefix="kb-command-space-") as directory:
            commands = Path(directory) / "commands with spaces"
            namespace = commands / "kennisbank"
            namespace.mkdir(parents=True)
            (commands / "wiki.md").touch()
            for name in names:
                (commands / (name + ".md")).touch()
                (namespace / (name + ".md")).touch()
            runner = Path(directory) / "commands.sh"
            runner.write_text(
                'COMMANDS_DIR="$TEST_COMMANDS"\n'
                'report_pass() { echo "PASS:$1"; }\n'
                'report_warn() { echo "WARN:$1"; }\n' + block,
                encoding="utf-8")
            for installed in (True, False):
                if not installed:
                    for name in names:
                        (namespace / (name + ".md")).unlink()
                result = run_bounded(
                    [BASH, _posix(runner)], cwd=str(ROOT), timeout=20,
                    env={**os.environ, "TEST_COMMANDS": _posix(commands)})
                self.assertFalse(result.timed_out, result.output)
                self.assertIn("PASS:command /wiki", result.output)
                for name in names:
                    status = "PASS" if installed else "WARN"
                    self.assertIn(f"{status}:command /kennisbank:{name}", result.output)


if __name__ == "__main__":
    unittest.main()

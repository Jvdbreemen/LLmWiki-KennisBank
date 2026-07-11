"""Hermetic tests for the Copilot launcher (scripts/kennisbank-copilot.py, TASK-26.7).

Every test runs against a temporary COPILOT_HOME/HOME so the real ~/.copilot is
never touched, and ``launch()`` is monkeypatched so no interactive Copilot TUI is
ever spawned. Covers (AC#5): env setup (KENNISBANK_VAULT pinned + KB_LLM_*
present, do-not-clobber), arg passthrough, exit-code passthrough, missing binary
(fatal on real launch, non-fatal in --kb-dry-run), vault override, --no-capture
sets KENNISBANK_COPILOT_NO_CAPTURE=1, and --kb-dry-run/--kb-doctor working without
a binary/login while emitting JSON. Plus DoD#3: no inherited secrets leak.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = REPO_ROOT / "scripts" / "kennisbank-copilot.py"

# Env keys the tests mutate; saved and restored so runs are isolated.
_ENV_KEYS = (
    "HOME", "USERPROFILE", "COPILOT_HOME", "KENNISBANK_COPILOT_BIN",
    "KENNISBANK_VAULT", "KB_LLM_PROVIDERS", "KB_LLM_MODEL", "KB_LLM_ENDPOINT",
    "KENNISBANK_COPILOT_NO_CAPTURE", "MY_SECRET_TOKEN",
)


def _load():
    spec = importlib.util.spec_from_file_location("kennisbank_copilot", MODULE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CopilotWrapperTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()  # fresh module per test -> monkeypatched launch is isolated
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-copilot-wrap-"))
        self.home = self.tmp / ".copilot"
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        (self.vault / ".claude" / "scripts" / "kb-mcp.py").write_text(
            "# fake mcp server\n", encoding="utf-8")

        self.saved = {k: os.environ.get(k) for k in _ENV_KEYS}
        os.environ["HOME"] = str(self.tmp)
        os.environ["USERPROFILE"] = str(self.tmp)
        os.environ["COPILOT_HOME"] = str(self.home)
        # Start from a clean base so set-if-absent and override logic is deterministic.
        for k in ("KENNISBANK_COPILOT_BIN", "KENNISBANK_VAULT", "KB_LLM_PROVIDERS",
                  "KB_LLM_MODEL", "KB_LLM_ENDPOINT", "KENNISBANK_COPILOT_NO_CAPTURE",
                  "MY_SECRET_TOKEN"):
            os.environ.pop(k, None)
        # Point most tests at our temp vault; individual tests may override.
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- helpers -----------------------------------------------------------

    def _posix(self, p):
        return str(p).replace("\\", "/")

    def _fake_bin(self):
        """A real file so find_binary() returns non-None. launch is mocked, so
        the file need not be executable."""
        b = self.tmp / "copilot-fake"
        b.write_text("x", encoding="utf-8")
        os.environ["KENNISBANK_COPILOT_BIN"] = str(b)
        return b

    def _capture_launch(self, rc=0):
        """Replace launch() with a recorder; returns the dict it fills in."""
        calls = {}

        def fake(binary, args, env):
            calls["binary"] = binary
            calls["args"] = list(args)
            calls["env"] = dict(env)
            return rc

        self.m.launch = fake
        return calls

    # --- env setup ---------------------------------------------------------

    def test_env_setup_pins_vault_and_kb_llm(self):
        self._fake_bin()
        calls = self._capture_launch(0)
        rc = self.m.main([])
        self.assertEqual(rc, 0)
        env = calls["env"]
        self.assertEqual(env["KENNISBANK_VAULT"], self._posix(self.vault))
        self.assertEqual(env["KB_LLM_PROVIDERS"], "ollama")
        self.assertEqual(env["KB_LLM_MODEL"], "gemma4:12b")
        self.assertEqual(env["KB_LLM_ENDPOINT"], "http://localhost:11434")

    def test_kb_llm_not_clobbered_when_user_set(self):
        os.environ["KB_LLM_MODEL"] = "user-model"
        self._fake_bin()
        calls = self._capture_launch(0)
        self.m.main([])
        self.assertEqual(calls["env"]["KB_LLM_MODEL"], "user-model")

    # --- arg passthrough ---------------------------------------------------

    def test_arg_passthrough_verbatim(self):
        self._fake_bin()
        calls = self._capture_launch(0)
        self.m.main(["chat", "--model", "gpt-x", "hello world"])
        self.assertEqual(calls["args"], ["chat", "--model", "gpt-x", "hello world"])

    def test_wrapper_flag_not_passed_through(self):
        self._fake_bin()
        calls = self._capture_launch(0)
        self.m.main(["--no-capture", "realarg"])
        self.assertEqual(calls["args"], ["realarg"])
        self.assertNotIn("--no-capture", calls["args"])

    # --- exit-code passthrough ---------------------------------------------

    def test_exit_code_passthrough(self):
        self._fake_bin()
        self._capture_launch(7)
        self.assertEqual(self.m.main(["chat"]), 7)

    # --- --no-capture ------------------------------------------------------

    def test_no_capture_sets_child_env(self):
        self._fake_bin()
        calls = self._capture_launch(0)
        self.m.main(["--no-capture", "chat"])
        self.assertEqual(calls["env"][self.m.NO_CAPTURE_ENV], "1")

    def test_no_capture_absent_by_default(self):
        self._fake_bin()
        calls = self._capture_launch(0)
        self.m.main(["chat"])
        self.assertNotIn(self.m.NO_CAPTURE_ENV, calls["env"])

    # --- missing binary ----------------------------------------------------

    def test_missing_binary_fatal_on_launch(self):
        os.environ["KENNISBANK_COPILOT_BIN"] = str(self.tmp / "does-not-exist")

        def boom(*a, **k):
            raise AssertionError("launch must not run without a binary")

        self.m.launch = boom
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = self.m.main(["chat"])
        self.assertNotEqual(rc, 0)
        self.assertIn("npm install -g @github/copilot", err.getvalue())

    def test_missing_binary_non_fatal_in_dry_run(self):
        os.environ["KENNISBANK_COPILOT_BIN"] = str(self.tmp / "does-not-exist")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.m.main([self.m.FLAG_DRY_RUN])
        self.assertEqual(rc, 0)
        data = json.loads(out.getvalue())
        self.assertFalse(data["binary_found"])
        self.assertEqual(data["vault"], self._posix(self.vault))

    # --- vault override ----------------------------------------------------

    def test_vault_override_respected(self):
        other = self.tmp / "OtherVault"
        (other / ".claude" / "scripts").mkdir(parents=True)
        os.environ["KENNISBANK_VAULT"] = str(other)
        self._fake_bin()
        calls = self._capture_launch(0)
        with contextlib.redirect_stderr(io.StringIO()):  # swallow fail-open MCP warning
            self.m.main(["chat"])
        self.assertEqual(calls["env"]["KENNISBANK_VAULT"], self._posix(other))

    # --- --kb-dry-run (no login) -------------------------------------------

    def test_dry_run_emits_json_and_launches_nothing(self):
        self._fake_bin()

        def boom(*a, **k):
            raise AssertionError("dry-run must not launch")

        self.m.launch = boom
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.m.main([self.m.FLAG_DRY_RUN, "chat", "--flag"])
        self.assertEqual(rc, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["mode"], "dry-run")
        self.assertEqual(data["vault"], self._posix(self.vault))
        self.assertIn("KENNISBANK_VAULT", data["env"])
        self.assertEqual(data["copilot_args"], ["chat", "--flag"])

    # --- --kb-doctor (no login) --------------------------------------------

    def test_doctor_json_exit_zero_without_login(self):
        # not_logged_in is the login-free healthy case: JSON, exit 0.
        canned = {"status": "not_logged_in", "installed": True, "binary": "copilot",
                  "detail": "kennisbank not shown; copilot may need /login"}
        with mock.patch.object(self.m._copilot, "probe_cli", return_value=canned):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = self.m.main([self.m.FLAG_DOCTOR])
        self.assertEqual(rc, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["status"], "not_logged_in")
        self.assertTrue(data["ok"])
        self.assertIn("config", data)  # validate_config info is present...
        # ...but config errors do NOT change the exit code.
        self.assertFalse(data["config"]["ok"])

    def test_doctor_no_binary_exits_nonzero_but_emits_json(self):
        os.environ["KENNISBANK_COPILOT_BIN"] = str(self.tmp / "does-not-exist")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.m.main([self.m.FLAG_DOCTOR])
        self.assertNotEqual(rc, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["status"], "copilot_missing")
        self.assertFalse(data["ok"])

    # --- --kb-print-env + DoD#3 (no inherited secrets) ---------------------

    def test_print_env_lists_kb_vars_and_leaks_no_secrets(self):
        os.environ["MY_SECRET_TOKEN"] = "supersecret-should-never-print"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.m.main([self.m.FLAG_PRINT_ENV])
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn(f"KENNISBANK_VAULT={self._posix(self.vault)}", text)
        self.assertIn("KB_LLM_MODEL=gemma4:12b", text)
        # DoD#3: the launcher prints only the vars it injects, never the
        # inherited environment, so an ambient secret can never surface.
        self.assertNotIn("supersecret-should-never-print", text)
        self.assertNotIn("MY_SECRET_TOKEN", text)

    def test_print_env_no_capture_included(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.m.main([self.m.FLAG_PRINT_ENV, "--no-capture"])
        self.assertEqual(rc, 0)
        self.assertIn(f"{self.m.NO_CAPTURE_ENV}=1", out.getvalue())


if __name__ == "__main__":
    unittest.main()

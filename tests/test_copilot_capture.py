"""Tests for the Copilot capture hook (scripts/kb-copilot-capture.py, TASK-26.6).

Covers payload parsing (camelCase + snake_case), secret redaction, malformed
payloads, fail-open exit codes, and structured event output. Hermetic: writes
only under a temp vault.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "kb-copilot-capture.py"


def _load():
    spec = importlib.util.spec_from_file_location("kb_copilot_capture", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CopilotCaptureTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-cap-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude").mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _events(self, path):
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_captures_tool_event(self):
        payload = {"sessionId": "abc-123", "cwd": "/work",
                   "timestamp": 1704614400000,
                   "toolName": "bash", "toolArgs": '{"command":"ls -la"}'}
        path = self.m.run("preToolUse", payload, vault=self.vault)
        self.assertIsNotNone(path)
        events = self._events(path)
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["event"], "preToolUse")
        self.assertEqual(ev["agent"], "github-copilot-cli")
        self.assertEqual(ev["source"], "copilot-hooks")
        self.assertEqual(ev["session_id"], "abc-123")
        self.assertEqual(ev["tool"], "bash")
        self.assertEqual(ev["role"], "tool_use")
        self.assertIn("ls -la", ev["message"])
        self.assertTrue(ev["timestamp"].startswith("2024-01-07"))

    def test_redacts_secret_keys_in_args(self):
        payload = {"sessionId": "s", "toolName": "http",
                   "toolArgs": json.dumps({"url": "https://x", "api_key": "SUPERSECRET123",
                                           "headers": {"Authorization": "Bearer tok_live_999"}})}
        path = self.m.run("preToolUse", payload, vault=self.vault)
        blob = path.read_text(encoding="utf-8")
        self.assertNotIn("SUPERSECRET123", blob)
        self.assertNotIn("tok_live_999", blob)
        self.assertIn("***", blob)

    def test_redacts_inline_secrets_in_freeform_args(self):
        payload = {"sessionId": "s", "toolName": "bash",
                   "toolArgs": "curl -H 'Authorization: Bearer ghp_ABCDEFGHIJKLMNOP123456'"}
        path = self.m.run("preToolUse", payload, vault=self.vault)
        blob = path.read_text(encoding="utf-8")
        self.assertNotIn("ghp_ABCDEFGHIJKLMNOP123456", blob)
        self.assertIn("***", blob)

    def test_snake_case_payload(self):
        payload = {"session_id": "snake", "tool_name": "read", "tool_args": "{}"}
        path = self.m.run("preToolUse", payload, vault=self.vault)
        ev = self._events(path)[0]
        self.assertEqual(ev["session_id"], "snake")
        self.assertEqual(ev["tool"], "read")

    def test_session_start_with_prompt(self):
        payload = {"sessionId": "s2", "source": "startup",
                   "initialPrompt": "help me refactor"}
        path = self.m.run("sessionStart", payload, vault=self.vault)
        ev = self._events(path)[0]
        self.assertEqual(ev["event"], "sessionStart")
        self.assertEqual(ev["role"], "user")
        self.assertIn("refactor", ev["message"])

    def test_empty_payload_is_fail_open(self):
        path = self.m.run("sessionEnd", {}, vault=self.vault)
        self.assertIsNotNone(path)
        ev = self._events(path)[0]
        self.assertEqual(ev["session_id"], "unknown")
        self.assertEqual(ev["event"], "sessionEnd")

    def test_events_append_to_same_session_file(self):
        self.m.run("sessionStart", {"sessionId": "sx"}, vault=self.vault)
        self.m.run("preToolUse", {"sessionId": "sx", "toolName": "bash", "toolArgs": "{}"}, vault=self.vault)
        path = self.m.output_path(self.vault, "sx")
        self.assertEqual(len(self._events(path)), 2)

    def test_no_capture_env_disables_write(self):
        os.environ["KENNISBANK_COPILOT_NO_CAPTURE"] = "1"
        try:
            path = self.m.run("preToolUse", {"sessionId": "nc", "toolName": "bash"}, vault=self.vault)
        finally:
            os.environ.pop("KENNISBANK_COPILOT_NO_CAPTURE", None)
        self.assertIsNone(path)
        self.assertFalse((self.vault / ".claude" / "copilot-events" / "nc.jsonl").exists())

    def test_session_id_sanitized_for_filename(self):
        path = self.m.run("preToolUse", {"sessionId": "../../evil/../x"}, vault=self.vault)
        self.assertIn("copilot-events", str(path))
        self.assertNotIn("..", path.name)

    # --- subprocess: real stdin + exit code (fail-open) --------------------

    def _run_cli(self, event, stdin_bytes, extra=None):
        env = {**os.environ, "KENNISBANK_VAULT": str(self.vault)}
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--event", event, *(extra or [])],
            input=stdin_bytes, capture_output=True, env=env,
        )

    def test_cli_exit_zero_on_valid_payload(self):
        out = self._run_cli("preToolUse",
                            json.dumps({"sessionId": "cli1", "toolName": "bash", "toolArgs": "{}"}).encode())
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), b"", "hook must print nothing on stdout")

    def test_cli_exit_zero_on_garbage_stdin(self):
        out = self._run_cli("preToolUse", b"}{ not json at all \x00")
        self.assertEqual(out.returncode, 0, "must fail open (exit 0) on garbage")

    def test_cli_exit_zero_on_empty_stdin(self):
        out = self._run_cli("sessionStart", b"")
        self.assertEqual(out.returncode, 0)


if __name__ == "__main__":
    unittest.main()

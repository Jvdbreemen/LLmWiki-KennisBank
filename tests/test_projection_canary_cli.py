"""CLI contracts for private owner-canary review and safe aggregation."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location(
    "kb_projection_canary", SCRIPTS / "kb-projection-canary.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class ProjectionCanaryCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = self.tmp.name
        self.addCleanup(self._restore)

    def _restore(self):
        if self.saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self.saved

    def test_default_log_stays_inside_private_vault(self):
        path = cli.default_log_path()
        self.assertTrue(path.is_relative_to(Path(self.tmp.name)))
        self.assertIn("06-claude", path.parts)

    def test_record_source_then_render_content_free_status(self):
        args = [
            "record-source", "--id", "source-one",
            "--observed-at", "2026-09-07T09:00:00Z",
            "--status", "ok", "--route", "exact_ref",
            "--shown-count", "1", "--latency-ms", "12.5",
            "--owner-reviewed", "yes", "--reconstruction-correct", "yes",
            "--provenance-correct", "yes", "--candidate-leakage", "0",
            "--idempotency-key", "source-one",
        ]
        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(args), 0)
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["appended"])
        self.assertEqual(result["layer"], "source")

        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["report"]), 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["source"]["eligible_n"], 1)
        rendered = json.dumps(report).lower()
        self.assertNotIn("source-one", rendered)

    def test_explicit_log_outside_vault_is_refused(self):
        outside = Path(self.tmp.name).parent / "outside-canary.jsonl"
        with self.assertRaisesRegex(ValueError, "inside KENNISBANK_VAULT"):
            cli.main(["--log", str(outside), "report"])


if __name__ == "__main__":
    unittest.main()

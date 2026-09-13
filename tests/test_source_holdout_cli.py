"""CLI contract for freezing a source holdout."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class SourceHoldoutCliTest(unittest.TestCase):
    def test_cli_reads_jsonl_and_reports_counts_without_printing_case_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vault = root / "vault"
            source = vault / "05-bronnen" / "note.md"
            source.parent.mkdir(parents=True)
            source.write_text("reviewed local fact", encoding="utf-8")
            cases = root / "cases.jsonl"
            cases.write_text(json.dumps({
                "id": "cli-1", "query": "What fact?",
                "expected_source": "05-bronnen/note.md",
                "expected_windows": [{"start": 0, "end": 8}],
                "answer": "private answer that must not be printed",
            }) + "\n", encoding="utf-8")
            output = root / "holdout.json"
            result = subprocess.run(
                [sys.executable, "scripts/build-source-holdout.py",
                 "--cases", str(cases), "--output", str(output), "--vault", str(vault)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["counts"]["source"], 1)
            self.assertNotIn("private answer", result.stdout)
            self.assertNotIn("reviewed local fact", output.read_text(encoding="utf-8"))

            report = subprocess.run(
                [sys.executable, "scripts/source-holdout-report.py", str(output),
                 "--vault", str(vault)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(report.returncode, 0, report.stderr)
            report_json = json.loads(report.stdout)
            self.assertEqual(report_json["oracle"]["ceiling"], 1.0)
            self.assertNotIn("What fact?", report.stdout)


if __name__ == "__main__":
    unittest.main()

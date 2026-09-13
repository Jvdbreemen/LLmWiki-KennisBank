"""Association-only exposure/outcome report contracts."""
from __future__ import annotations

import sys
import unittest
import sqlite3
import tempfile
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _outcome_report as report  # noqa: E402
spec = importlib.util.spec_from_file_location("kb_outcome_report", SCRIPTS / "kb-outcome-report.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class OutcomeReportTest(unittest.TestCase):
    def test_groups_exposures_without_claiming_item_causality(self):
        result = report.correlate(
            [{"session_id": "s1", "task_id": "t1", "item_id": "m1", "layer": "memory"},
             {"session_id": "s2", "task_id": "t2", "item_id": "src1", "layer": "source"}],
            [{"session_id": "s1", "task_id": "t1", "state": "success"},
             {"session_id": "s2", "task_id": "t2", "state": "unknown"}],
        )
        self.assertEqual(result["by_layer"]["memory"]["success"], 1)
        self.assertEqual(result["by_layer"]["source"]["unknown"], 1)
        self.assertEqual(result["attribution_scope"], "association_only")
        self.assertNotIn("caused", str(result).lower())

    def test_missing_outcome_is_unknown(self):
        result = report.correlate(
            [{"session_id": "s1", "task_id": "t1", "item_id": "m1", "layer": "memory"}], [])
        self.assertEqual(result["by_layer"]["memory"]["unknown"], 1)

    def test_cli_loads_both_local_ledgers_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            (vault / ".claude").mkdir()
            usage = sqlite3.connect(vault / ".claude" / "kb-usage.db")
            usage.execute("CREATE TABLE exposures(session_id TEXT, task_id TEXT, item_id TEXT, layer TEXT)")
            usage.execute("INSERT INTO exposures VALUES ('s','t','m','memory')")
            usage.commit(); usage.close()
            experience = sqlite3.connect(vault / ".claude" / "kb-experience.db")
            experience.execute("CREATE TABLE experience_outcomes(session_id TEXT, task_id TEXT, state TEXT)")
            experience.execute("INSERT INTO experience_outcomes VALUES ('s','t','success')")
            experience.commit(); experience.close()
            result = cli.build_report(vault)
            self.assertEqual(result["by_layer"]["memory"]["success"], 1)


if __name__ == "__main__":
    unittest.main()

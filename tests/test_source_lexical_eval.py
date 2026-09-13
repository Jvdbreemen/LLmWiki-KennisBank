"""Full-document lexical source baseline contracts."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _source_lexical_eval as lexical  # noqa: E402


class SourceLexicalEvalTest(unittest.TestCase):
    def test_build_and_evaluate_report_only_aggregates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vault = root / "vault"
            first = vault / "01-raw" / "transcripts" / "first.md"
            second = vault / "05-bronnen" / "second.md"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_text("rare timeout grandchild pipe", encoding="utf-8")
            second.write_text("unrelated boiler telemetry", encoding="utf-8")
            db = root / "source-fts.db"
            build = lexical.build_index(vault, db)
            report = lexical.evaluate([
                {"id": "S1", "query": "grandchild pipe timeout",
                 "expected_source": "01-raw/transcripts/first.md"},
                {"id": "S2", "query": "imaginary weather detail",
                 "expected_source": None},
            ], db)
        self.assertEqual(build["documents"], 2)
        self.assertEqual(report["retrieval"]["hit@5"], 1.0)
        self.assertEqual(report["retrieval"]["no_hit_precision"], 1.0)
        self.assertNotIn("grandchild", repr(report))


if __name__ == "__main__":
    unittest.main()

"""Canonical experience history and search projection are separate stores."""
from __future__ import annotations

import importlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


class ExperienceProjectionBoundaryContractTest(unittest.TestCase):
    def setUp(self):
        self.experience = importlib.import_module("_experience")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"

    def test_store_paths_are_distinct_and_explicit(self):
        ledger = self.experience.ledger_path(self.vault)
        projection = self.experience.projection_path(self.vault)
        self.assertEqual(ledger.name, "kb-experience-ledger.db")
        self.assertEqual(projection.name, "kb-experience-index.db")
        self.assertNotEqual(ledger, projection)

    def test_ledger_schema_contains_no_retrieval_tables(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        self.experience.ensure_ledger_schema(conn)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"experience_events", "experience_outcomes", "experience_reviews"} <= tables)
        self.assertFalse({"docs", "fts_docs", "vec_docs", "experiences"} & tables)

    def test_projection_schema_contains_no_canonical_event_or_outcome_tables(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        self.experience.ensure_projection_schema(conn, dim=3, embed_id="fake:3")
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertFalse({"experience_events", "experience_outcomes", "experience_reviews"} & tables)


if __name__ == "__main__":
    unittest.main()

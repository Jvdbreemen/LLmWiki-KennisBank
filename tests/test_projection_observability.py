"""Aggregate observability for deeper projections must remain content-free."""
from __future__ import annotations

import inspect
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _usage  # noqa: E402


class ProjectionObservabilityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.previous = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = self.tmp.name

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self.previous

    def test_projection_metric_api_cannot_accept_content_fields(self):
        parameters = set(inspect.signature(_usage.log_projection_metric).parameters)
        self.assertEqual(parameters, {
            "layer", "route", "status", "hits", "latency_ms", "today",
        })
        for forbidden in ("query", "prompt", "passage", "lesson", "source_ref",
                          "embedding", "path"):
            self.assertNotIn(forbidden, parameters)

    def test_projection_metrics_store_aggregates_only(self):
        self.assertTrue(_usage.log_projection_metric(
            layer="experience", route="lexical_fallback", status="ok",
            hits=2, latency_ms=7.5, today="2026-09-06"))
        conn = sqlite3.connect(_usage.db_path())
        try:
            columns = [row[1] for row in conn.execute(
                "PRAGMA table_info(projection_metrics)")]
            row = conn.execute("SELECT * FROM projection_metrics").fetchone()
        finally:
            conn.close()
        self.assertEqual(columns, [
            "day", "layer", "route", "status", "calls", "hits",
            "latency_ms_total", "latency_ms_max",
        ])
        rendered = repr((columns, row)).lower()
        for secret in ("private prompt", "raw passage", "c:/users/robert",
                       "sr_full_reference", "embedding"):
            self.assertNotIn(secret, rendered)

    def test_deeper_gateways_do_not_send_query_or_path_to_exposure_log(self):
        source = (SCRIPTS / "kb-source-recall.py").read_text(encoding="utf-8")
        experience = (SCRIPTS / "kb-experience-recall.py").read_text(encoding="utf-8")
        self.assertNotIn("query=prompt", source)
        self.assertNotIn("query=prompt", experience)
        self.assertNotIn('"source_id": hit.get("source_path"', source)


if __name__ == "__main__":
    unittest.main()

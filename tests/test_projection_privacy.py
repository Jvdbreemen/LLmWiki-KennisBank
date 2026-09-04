"""Projection telemetry is aggregate-only and content-free."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _metrics_module():
    path = SCRIPTS / "_projection_metrics.py"
    if not path.is_file():
        raise AssertionError("TASK-234 must provide scripts/_projection_metrics.py")
    spec = importlib.util.spec_from_file_location("_projection_metrics_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProjectionPrivacyContractTest(unittest.TestCase):
    def test_metric_sanitizer_keeps_only_aggregate_allowlisted_fields(self):
        metrics = _metrics_module()
        sanitized = metrics.sanitize_metric({
            "route": "exact_ref", "status": "ok", "latency_ms": 4.2, "count": 1,
            "query": "private question", "passage": "private evidence",
            "lesson": "private lesson", "source_path": "D:/Users/Robert/private.md",
            "source_ref": {"source_sha256": "secret"}, "embedding": [0.1, 0.2],
        })
        self.assertEqual(sanitized, {
            "route": "exact_ref", "status": "ok", "latency_ms": 4.2, "count": 1})

    def test_unknown_fields_are_dropped_instead_of_logged_opportunistically(self):
        metrics = _metrics_module()
        self.assertEqual(metrics.sanitize_metric({"future_private_field": "secret"}), {})


if __name__ == "__main__":
    unittest.main()

"""One-shot and decision contracts for the TASK-223 evaluator CLI."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "evaluate-source-sparse.py"


def _load():
    spec = importlib.util.spec_from_file_location("evaluate_source_sparse", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceSparseEvalCliTest(unittest.TestCase):
    def setUp(self):
        self.module = _load()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _manifest(self):
        cases = []
        for number in range(50):
            cases.append({
                "id": f"S-{number:03d}", "query": f"positive {number}",
                "expected_source": f"01-raw/sessions/{number}.md",
                "expected_windows": [{"start": 0, "end": 5}],
            })
        for number in range(10):
            cases.append({
                "id": f"N-{number:03d}", "query": f"negative {number}",
                "expected_source": None, "expected_windows": [],
            })
        return {"schema_version": 1, "cases": cases}

    def test_frozen_loader_requires_exact_reviewed_composition(self):
        path = self.root / "source-holdout.json"
        path.write_text(json.dumps(self._manifest()), encoding="utf-8")
        cases = self.module.load_cases(path, frozen=True)
        self.assertEqual(len(cases), 60)
        broken = self._manifest()
        broken["cases"].pop()
        path.write_text(json.dumps(broken), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.module.load_cases(path, frozen=True)

    def test_private_boundary_rejects_repository_paths(self):
        with self.assertRaises(ValueError):
            self.module.private_path(REPO / "source-report.json")
        outside = self.module.private_path(self.root / "source-report.json")
        self.assertEqual(outside, (self.root / "source-report.json").resolve())

    def test_claim_report_is_exclusive_and_marks_one_shot_policy(self):
        path = self.root / "report.json"
        self.module.claim_report(path, input_sha256="sha256:abc")
        marker = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(marker["status"], "running")
        self.assertEqual(marker["input_sha256"], "sha256:abc")
        self.assertEqual(marker["holdout_policy"], "frozen_one_shot_no_further_tuning")
        with self.assertRaises(ValueError):
            self.module.claim_report(path, input_sha256="sha256:def")

    def test_decision_requires_gain_specificity_and_warm_latency(self):
        passing = {
            "retrieval": {"hit@5": 0.80},
            "no_hit_specificity": 1.0,
            "latency_ms": {"p95_ms": 1800.0},
        }
        decision = self.module.choose_decision(
            passing, lexical_hit5=0.66, required_gain=0.10,
            minimum_specificity=0.95, maximum_warm_p95_ms=2000.0)
        self.assertEqual(decision["choice"], "sparse-first")
        self.assertTrue(decision["passes"])

        unsafe = dict(passing, no_hit_specificity=0.90)
        rejected = self.module.choose_decision(
            unsafe, lexical_hit5=0.66, required_gain=0.10,
            minimum_specificity=0.95, maximum_warm_p95_ms=2000.0)
        self.assertEqual(rejected["choice"], "reject")
        self.assertFalse(rejected["passes"])

    def test_public_report_contains_aggregates_not_private_cases(self):
        report = self.module.build_report(
            input_sha256="sha256:abc", model_id="fake:model",
            measured={
                "retrieval": {"hit@5": 0.8}, "no_hit_specificity": 1.0,
                "latency_ms": {"p95_ms": 10}, "citation_precision": 1.0,
                "passage_hit@5": 0.78,
                "counts": {"total": 60, "positive": 50, "negative": 10},
                "configuration": {"candidate_docs": 50},
            },
            warm_latency={"n": 20, "p50_ms": 6, "p95_ms": 8},
            source_db_bytes=1105334272, cache_db_bytes=2048,
            lexical_hit5=0.66, lexical_index_bytes=1105334272,
        )
        rendered = json.dumps(report)
        self.assertEqual(report["decision"]["choice"], "sparse-first")
        self.assertNotIn("positive 1", rendered)
        self.assertNotIn("expected_source", rendered)
        self.assertEqual(report["costs"]["lexical_index_bytes"], 1105334272)

    def test_frozen_holdout_calls_evaluator_once_for_all_cases(self):
        cases = self._manifest()["cases"]
        calls = []

        def evaluator(received, **options):
            calls.append([case["id"] for case in received])
            return {"counts": {"total": len(received)}}

        result = self.module.run_holdout_once(
            cases, evaluator=evaluator, options={"private": True})
        self.assertEqual(result["counts"]["total"], 60)
        self.assertEqual(calls, [[case["id"] for case in cases]])

    def test_failed_run_keeps_content_safe_spent_marker(self):
        path = self.root / "report.json"
        self.module.claim_report(path, input_sha256="sha256:abc")
        self.module.mark_failed(path, failure_class="embedding_unavailable")
        marker = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(marker["status"], "failed")
        self.assertEqual(marker["failure_class"], "embedding_unavailable")
        self.assertNotIn("exception", marker)


if __name__ == "__main__":
    unittest.main()

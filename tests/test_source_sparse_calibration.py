"""Development-only selection contracts for sparse-first source recall."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _source_sparse_selection as selection  # noqa: E402

SCRIPT = SCRIPTS / "calibrate-source-sparse.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("calibrate_source_sparse", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceSparseSelectionTest(unittest.TestCase):
    def test_development_split_rejects_id_query_and_source_overlap(self):
        frozen = [{
            "id": "S-001", "query": "Where is the valve?",
            "expected_source": "01-raw/sessions/valve.md",
        }]
        selection.assert_independent_source_cases(
            [{"id": "D-001", "query": "How was the boiler fixed?",
              "expected_source": "01-raw/sessions/boiler.md"}], frozen)
        for development in (
            [{"id": "S-001", "query": "different",
              "expected_source": "01-raw/sessions/other.md"}],
            [{"id": "D-002", "query": " where  is the VALVE? ",
              "expected_source": "01-raw/sessions/other.md"}],
            [{"id": "D-003", "query": "different",
              "expected_source": "01-RAW\\sessions\\VALVE.md"}],
        ):
            with self.assertRaises(ValueError):
                selection.assert_independent_source_cases(development, frozen)

    def test_selection_maximizes_recall_subject_to_safety_and_latency(self):
        trials = [
            {"configuration": {"candidate_docs": 20, "min_cos": 0.5},
             "retrieval": {"hit@5": 0.90}, "passage_hit@5": 0.85,
             "citation_precision": 0.9, "no_hit_specificity": 0.8,
             "warm_latency": {"p95_ms": 100}, "cache_bytes": 1000},
            {"configuration": {"candidate_docs": 50, "min_cos": 0.6},
             "retrieval": {"hit@5": 0.80}, "passage_hit@5": 0.75,
             "citation_precision": 0.8, "no_hit_specificity": 1.0,
             "warm_latency": {"p95_ms": 1500}, "cache_bytes": 2000},
            {"configuration": {"candidate_docs": 100, "min_cos": 0.7},
             "retrieval": {"hit@5": 0.85}, "passage_hit@5": 0.80,
             "citation_precision": 0.85, "no_hit_specificity": 1.0,
             "warm_latency": {"p95_ms": 2500}, "cache_bytes": 3000},
        ]
        result = selection.select_configuration(
            trials, minimum_specificity=0.95, maximum_warm_p95_ms=2000)
        self.assertTrue(result["development_constraints_pass"])
        self.assertEqual(result["selected"]["configuration"]["candidate_docs"], 50)
        self.assertEqual(result["selection_source"], "development_only")

    def test_no_safe_trial_is_explicit_not_silently_approved(self):
        trials = [{
            "configuration": {"candidate_docs": 20},
            "retrieval": {"hit@5": 0.7}, "passage_hit@5": 0.6,
            "citation_precision": 0.7, "no_hit_specificity": 0.8,
            "warm_latency": {"p95_ms": 100}, "cache_bytes": 1000,
        }]
        result = selection.select_configuration(trials)
        self.assertFalse(result["development_constraints_pass"])
        self.assertEqual(result["reason"], "best_available_no_safe_trial")


class SourceSparseCalibrationCliTest(unittest.TestCase):
    def setUp(self):
        self.cli = _load_cli()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _cases(self):
        cases = []
        for number in range(20):
            cases.append({
                "id": f"D-S-{number:03d}", "query": f"positive {number}",
                "expected_source": f"01-raw/dev/{number}.md",
                "expected_hash": "sha256:" + ("a" * 64),
                "expected_windows": [{"start": 0, "end": 5}],
                "review_status": "reviewed", "review_decision": "keep",
            })
        for number in range(10):
            cases.append({
                "id": f"D-N-{number:03d}", "query": f"negative {number}",
                "expected_source": None, "expected_windows": [],
                "review_status": "reviewed", "review_decision": "keep",
            })
        return cases

    def test_development_loader_requires_20_positive_10_negative_and_review(self):
        path = self.root / "dev.json"
        path.write_text(json.dumps({"schema_version": 1, "cases": self._cases()}),
                        encoding="utf-8")
        self.assertEqual(len(self.cli.load_development_cases(path)), 30)
        broken = self._cases()
        broken[0]["review_decision"] = "pending"
        path.write_text(json.dumps({"schema_version": 1, "cases": broken}),
                        encoding="utf-8")
        with self.assertRaises(ValueError):
            self.cli.load_development_cases(path)

    def test_development_loader_accepts_owner_review_jsonl_directly(self):
        path = self.root / "source-dev-review.jsonl"
        path.write_text(
            "\n".join(json.dumps(case) for case in self._cases()) + "\n",
            encoding="utf-8")
        self.assertEqual(len(self.cli.load_development_cases(path)), 30)

    def test_positive_cases_require_exact_hash_and_fresh_fts_snapshot(self):
        vault = self.root / "vault"
        source = vault / "01-raw" / "dev" / "one.md"
        source.parent.mkdir(parents=True)
        source.write_text("alpha reviewed passage", encoding="utf-8")
        raw = source.read_bytes()
        case = {
            "id": "D-S-001", "query": "alpha",
            "expected_source": "01-raw/dev/one.md",
            "expected_hash": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "expected_windows": [{"start": 0, "end": 5}],
        }
        database = self.root / "source.db"
        with closing(sqlite3.connect(database)) as conn:
            conn.execute(
                "CREATE VIRTUAL TABLE source_fts USING fts5(source_path UNINDEXED, body)")
            conn.execute("INSERT INTO source_fts(source_path, body) VALUES (?, ?)",
                         (case["expected_source"], source.read_text(encoding="utf-8")))
            conn.commit()
        self.cli.validate_case_provenance([case], vault=vault, source_db=database)

        source.write_text("changed reviewed passage", encoding="utf-8")
        case["expected_hash"] = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            self.cli.validate_case_provenance([case], vault=vault, source_db=database)

    def test_report_binds_inputs_index_revision_models_and_selected_config(self):
        cases = self._cases()
        report = self.cli.build_selection_report(
            development_sha256="sha256:dev", frozen_sha256="sha256:frozen",
            source_db_sha256="sha256:index", repository_revision="abc123",
            document_model_id="fake:doc", query_model_id="fake:query",
            cases=cases,
            selection_result={
                "selection_source": "development_only",
                "development_constraints_pass": True,
                "reason": "max_recall_subject_to_safety_and_latency",
                "constraints": {"minimum_specificity": 0.95,
                                "maximum_warm_p95_ms": 2000.0},
                "selected": {
                    "configuration": {"candidate_docs": 50,
                                      "max_passages": 100,
                                      "chunk_size": 2000, "overlap": 200,
                                      "k": 5, "min_cos": 0.6},
                    "retrieval": {"hit@5": 0.8},
                    "no_hit_specificity": 1.0,
                    "warm_latency": {"n": 30, "p95_ms": 1200.0},
                    "cache_bytes": 4096,
                },
                "trial_count": 6,
            })
        rendered = json.dumps(report)
        self.assertEqual(report["source_db_sha256"], "sha256:index")
        self.assertEqual(report["selected_configuration"]["min_cos"], 0.6)
        self.assertEqual(report["development_warm_latency"]["p95_ms"], 1200.0)
        self.assertEqual(report["counts"], {"total": 30, "positive": 20,
                                            "negative": 10})
        self.assertNotIn("positive 1", rendered)
        self.assertNotIn("expected_source", rendered)

    def test_query_embeddings_are_reused_across_measured_and_warm_runs(self):
        calls = []

        def embed(texts):
            calls.append(list(texts))
            return [[float(len(text))] for text in texts]

        cached = self.cli.memoize_embeddings(embed)
        self.assertEqual(cached(["alpha", "beta"]), [[5.0], [4.0]])
        self.assertEqual(cached(["beta", "alpha", "gamma"]),
                         [[4.0], [5.0], [5.0]])
        self.assertEqual(calls, [["alpha", "beta"], ["gamma"]])

    def test_trial_grid_uses_one_content_addressed_embedding_cache(self):
        cache_dir = self.root / "cache"
        cache_dir.mkdir()
        query_calls = []
        observed_cache_paths = []

        def embed_queries(texts):
            query_calls.append(list(texts))
            return [[1.0] for _ in texts]

        def fake_evaluate(cases, **options):
            observed_cache_paths.append(options["cache_db"])
            options["embed_query_fn"](["same query"])
            options["cache_db"].write_bytes(b"shared-cache")
            return {
                "configuration": {
                    "candidate_docs": options["candidate_docs"],
                    "max_passages": options["max_passages"],
                    "min_cos": options["min_cos"],
                },
                "retrieval": {"hit@5": 0.5},
                "passage_hit@5": 0.5,
                "citation_precision": 1.0,
                "provenance_precision": 1.0,
                "no_hit_specificity": 1.0,
                "latency_ms": {"n": 1, "p95_ms": 100.0},
            }

        with mock.patch.object(self.cli.sparse, "evaluate", side_effect=fake_evaluate):
            trials = self.cli.run_trial_grid(
                [{}], cache_dir=cache_dir,
                candidate_docs=[20, 50], max_passages=[40],
                min_cos=[0.4, 0.7], base_options={
                    "embed_query_fn": embed_queries,
                })

        self.assertEqual(len(trials), 4)
        self.assertEqual(len(set(observed_cache_paths)), 1)
        self.assertEqual(query_calls, [["same query"]])
        self.assertEqual({row["cache_bytes"] for row in trials},
                         {len(b"shared-cache")})


if __name__ == "__main__":
    unittest.main()

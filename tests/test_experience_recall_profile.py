"""Contracts for the read-only explicit-experience recall profiler."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _experience as experience  # noqa: E402


def _profiler():
    spec = importlib.util.spec_from_file_location(
        "experience_recall_profiler", SCRIPTS / "profile-experience-recall.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExperienceRecallProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.eval_dir = self.vault / "evaluations" / "run"
        self.projection = self.eval_dir / "isolated-vault" / ".claude" / \
            "kb-experience-index.db"
        self.projection.parent.mkdir(parents=True)
        self.conn = experience.connect(self.projection)
        self.addCleanup(self.conn.close)
        experience.ensure_projection_schema(self.conn, dim=3, embed_id="fake:3")
        record = {
            "experience_id": "safe", "session_id": "session", "task_id": "task",
            "status": "validated", "situation": "bounded timeout",
            "goal": "finish safely", "approach": "bounded timeout",
            "action": "apply bounded timeout", "observed_result": "verified",
            "lesson": "bounded timeout", "applicability": "tests",
            "outcome_state": "success", "attempt_state": "success",
            "resolution_state": "not_applicable", "confidence": 0.8,
            "source_refs": [{"source_ref_id": "sr_safe"}],
            "outcome_refs": ["out-safe"], "evidence_state": "verified",
            "review_state": "accepted", "content_hash": "sha256:" + "a" * 64,
        }
        experience.projection_upsert(self.conn, record)
        experience.index_experience(self.conn, "safe", vector=[1, 0, 0])
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_read_only_connection_keeps_projection_byte_identical(self):
        profiler = _profiler()
        before = hashlib.sha256(self.projection.read_bytes()).hexdigest()
        conn = profiler.connect_read_only(self.projection)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0], 1)
        finally:
            conn.close()
        after = hashlib.sha256(self.projection.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_cached_vector_validation_counts_missing_and_wrong_dimensions(self):
        profiler = _profiler()
        cases = [{"id": "ok"}, {"id": "missing"}, {"id": "wrong"}]
        vectors = {"ok": [1, 0, 0], "wrong": [1, 0]}

        valid, failures = profiler.validate_cached_vectors(cases, vectors, dimension=3)

        self.assertEqual(list(valid), ["ok"])
        self.assertEqual(failures, [
            {"id": "missing", "reason": "missing_cached_vector"},
            {"id": "wrong", "reason": "incompatible_cached_vector"},
        ])

    def test_profile_suppresses_telemetry_and_keeps_projection_unchanged(self):
        profiler = _profiler()
        cases = [{"id": "Q1", "query": "bounded timeout"}]
        vectors = {"Q1": [1, 0, 0]}
        before = hashlib.sha256(self.projection.read_bytes()).hexdigest()
        usage_db = self.vault / ".claude" / "kb-usage.db"

        with mock.patch.dict(os.environ, {"KENNISBANK_VAULT": str(self.vault)}, clear=False):
            result = profiler.profile(
                self.projection, self.eval_dir / "isolated-vault", cases, vectors,
                repeat=1)

        after = hashlib.sha256(self.projection.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertFalse(usage_db.exists())
        self.assertEqual(result["gateway"]["attempted"], 1)
        self.assertEqual(result["gateway"]["failed"], 0)
        self.assertFalse(result["integrity"]["projection_changed"])
        self.assertFalse(result["integrity"]["telemetry_changed"])

    def test_unavailable_gateway_is_counted_but_no_hit_is_not_a_failure(self):
        profiler = _profiler()
        cases = [{"id": "Q1", "query": "bounded timeout"},
                 {"id": "Q2", "query": "bounded timeout"}]
        vectors = {"Q1": [1, 0, 0], "Q2": [1, 0, 0]}
        responses = iter((
            {"status": "unavailable", "hits": []},
            {"status": "no_hit", "hits": []},
        ))

        result = profiler.profile(
            self.projection, self.eval_dir / "isolated-vault", cases, vectors,
            repeat=1, gateway_run=lambda _request, _vault: next(responses))

        self.assertEqual(result["gateway"]["attempted"], 2)
        self.assertEqual(result["gateway"]["failed"], 1)
        self.assertEqual(result["gateway"]["failures"], [
            {"id": "Q1", "reason": "status:unavailable"},
        ])

    def test_telemetry_snapshot_detects_a_write_even_when_gateway_is_injected(self):
        profiler = _profiler()
        cases = [{"id": "Q1", "query": "bounded timeout"}]
        vectors = {"Q1": [1, 0, 0]}

        def writes_usage(_request, _vault):
            usage_db = Path(_vault) / ".claude" / "kb-usage.db"
            usage_db.parent.mkdir(parents=True, exist_ok=True)
            usage_db.write_bytes(b"unexpected eval telemetry")
            return {"status": "no_hit", "hits": []}

        with mock.patch.dict(os.environ, {"KENNISBANK_VAULT": str(self.vault)}, clear=False):
            result = profiler.profile(
                self.projection, self.eval_dir / "isolated-vault", cases, vectors,
                repeat=1, gateway_run=writes_usage)

        self.assertTrue(result["integrity"]["telemetry_changed"])

    def test_profile_can_measure_real_query_embedding_separately_from_gateway(self):
        profiler = _profiler()
        cases = [{"id": "Q1", "query": "bounded timeout"}]

        result = profiler.profile(
            self.projection, self.eval_dir / "isolated-vault", cases, {}, repeat=1,
            query_embed=lambda _query: [1, 0, 0],
            gateway_run=lambda _request, _vault: {"status": "no_hit", "hits": []})

        self.assertEqual(result["embedding"]["attempted"], 1)
        self.assertEqual(result["embedding"]["failed"], 0)
        self.assertEqual(result["gateway"]["attempted"], 1)
        self.assertIsNotNone(result["end_to_end"]["p95_ms"])

    def test_existing_output_directory_is_never_overwritten(self):
        profiler = _profiler()
        output = self.eval_dir / "profile-existing"
        output.mkdir(parents=True)
        marker = output / "marker.txt"
        marker.write_text("keep", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            profiler.write_result(output, {"safe": True})

        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()

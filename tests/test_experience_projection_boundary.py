"""Canonical experience history and search projection are separate stores."""
from __future__ import annotations

import importlib
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_experience_projection_contract", SCRIPTS / "build-experience-index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def _ledger_with_one_task(self):
        source_path = self.vault / "01-raw" / "transcripts" / "one.md"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("retry with a bounded wait", encoding="utf-8")
        source_ref = importlib.import_module("_source_ref").make_source_ref(
            self.vault, "01-raw/transcripts/one.md", start=0,
            end=len("retry with a bounded wait"), chunk_id="chunk-0",
            captured_at="2026-09-04T00:00:00Z")
        ledger = self.experience.ledger_path(self.vault)
        ledger.parent.mkdir(parents=True, exist_ok=True)
        conn = self.experience.connect(ledger)
        self.experience.ensure_ledger_schema(conn)
        self.experience.append_event(
            conn, event_id="evt-1", session_id="s1", task_id="t1",
            event_type="attempt", observed_at="2026-09-04T00:00:00Z",
            payload={"situation": "retry", "approach": "bound it", "lesson": "bound retry"},
            source_refs=[source_ref])
        self.experience.record_outcome(
            conn, outcome_id="out-1", session_id="s1", task_id="t1",
            state="success", evidence=["test"], attribution_strength="strong")
        builder = _builder()
        extract = importlib.import_module("_experience_extract")
        experience_id = builder.experience_id_for("s1", "t1")
        candidate = extract.derive_experience_values(conn, "s1", "t1", experience_id)
        self.experience.record_review(
            conn, review_id="review-1", experience_id=experience_id,
            decision="accepted", actor="owner", reviewed_at="2026-09-04T00:01:00Z",
            reason="owner verified source and outcome",
            content_hash=self.experience.experience_content_hash(candidate))
        conn.close()
        return ledger

    def test_projection_is_rebuildable_from_ledger_without_mutating_it(self):
        ledger = self._ledger_with_one_task()
        projection = self.experience.projection_path(self.vault)
        ledger_before = ledger.read_bytes()
        builder = _builder()
        first = builder.rebuild_experience_projection(ledger, projection)
        self.assertEqual(first["status"], "ok")
        conn = self.experience.connect(projection)
        rows_before = conn.execute(
            "SELECT experience_id, lesson FROM experiences ORDER BY experience_id").fetchall()
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        self.assertFalse({"experience_events", "experience_outcomes", "experience_reviews"} & tables)
        projection.unlink()
        second = builder.rebuild_experience_projection(ledger, projection)
        conn = self.experience.connect(projection)
        rows_after = conn.execute(
            "SELECT experience_id, lesson FROM experiences ORDER BY experience_id").fetchall()
        conn.close()
        self.assertEqual(second["status"], "ok")
        self.assertEqual(rows_before, rows_after)
        self.assertEqual(ledger.read_bytes(), ledger_before)

    def test_failed_projection_rebuild_preserves_previous_good_file(self):
        ledger = self._ledger_with_one_task()
        projection = self.experience.projection_path(self.vault)
        builder = _builder()
        self.assertEqual(
            builder.rebuild_experience_projection(ledger, projection)["status"], "ok")
        before = projection.read_bytes()
        report = builder.rebuild_experience_projection(
            ledger, projection,
            derive_fn=lambda *_args: (_ for _ in ()).throw(RuntimeError("boom")))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(projection.read_bytes(), before)

    def test_unreviewed_candidate_is_reported_but_never_materialized(self):
        source_path = self.vault / "01-raw" / "transcripts" / "candidate.md"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("candidate evidence", encoding="utf-8")
        source_ref = importlib.import_module("_source_ref").make_source_ref(
            self.vault, "01-raw/transcripts/candidate.md", start=0,
            end=len("candidate evidence"), chunk_id="chunk-0")
        ledger = self.experience.ledger_path(self.vault)
        conn = self.experience.connect(ledger)
        self.experience.ensure_ledger_schema(conn)
        self.experience.append_event(
            conn, event_id="evt-candidate", session_id="s2", task_id="t2",
            event_type="attempt", observed_at="2026-09-04T00:00:00Z",
            payload={"lesson": "not reviewed"}, source_refs=[source_ref])
        self.experience.record_outcome(
            conn, outcome_id="out-candidate", session_id="s2", task_id="t2",
            state="success", evidence=["test"], attribution_strength="strong")
        conn.close()

        projection = self.experience.projection_path(self.vault)
        report = _builder().rebuild_experience_projection(ledger, projection)
        conn = self.experience.connect(projection)
        try:
            count = conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(report["experiences"], 0)
        self.assertEqual(count, 0)
        self.assertEqual(report["skipped_candidates"][0]["review_state"], "unreviewed")

    def test_embedding_failure_still_publishes_complete_lexical_projection(self):
        ledger = self._ledger_with_one_task()
        projection = self.experience.projection_path(self.vault)

        report = _builder().rebuild_experience_projection(
            ledger, projection,
            embed_fn=lambda _text: (_ for _ in ()).throw(RuntimeError("offline")),
            embed_id="fake:3")
        conn = self.experience.connect(projection)
        try:
            hits = self.experience.experience_lexical_hits(
                conn, query_text="bound retry", k=3)
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["vector_status"], "lexical_fallback")
        self.assertEqual(len(report["failed_embeddings"]), 1)
        self.assertEqual(len(hits), 1)
        self.assertNotIn("vec_docs", tables)


if __name__ == "__main__":
    unittest.main()

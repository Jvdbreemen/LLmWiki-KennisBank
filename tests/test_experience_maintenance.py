"""Tests-first contracts for experience lifecycle diagnostics and rebuilds."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _experience as exp  # noqa: E402
import _source_ref as source_ref  # noqa: E402


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_experience_index", SCRIPTS / "build-experience-index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExperienceMaintenanceTest(unittest.TestCase):
    @staticmethod
    def _source(vault: Path, name: str, passage: str) -> dict:
        relative = f"01-raw/transcripts/{name}.md"
        path = vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(passage, encoding="utf-8")
        return source_ref.make_source_ref(
            vault, relative, start=0, end=len(passage), chunk_id=name)

    def test_lifecycle_report_surfaces_status_and_provenance_gaps(self):
        from _experience_maintenance import lifecycle_report

        report = lifecycle_report([
            {"experience_id": "ok", "status": "validated",
             "source_refs": ["01-raw/a.md#0:10"], "outcome_refs": ["o1"]},
            {"experience_id": "retracted", "status": "retracted",
             "source_refs": ["05-bronnen/redacted.md#0:10"], "outcome_refs": ["o2"]},
            {"experience_id": "orphan", "status": "validated",
             "source_refs": ["01-raw/missing.md#0:10"], "outcome_refs": []},
            {"experience_id": "narrowed", "status": "validated",
             "source_refs": ["01-raw/a.md#10:20"], "outcome_refs": ["o3"],
             "attribution_limits": "narrowed to shutdown helpers"},
            {"experience_id": "superseded", "status": "superseded",
             "source_refs": [{"source_path": "01-raw/a.md",
                              "source_ref_id": "sr_a"}],
             "outcome_refs": ["o4"]},
        ], existing_sources={"01-raw/a.md"},
            redacted_sources={"05-bronnen/redacted.md"})
        self.assertEqual(report["status_counts"]["validated"], 3)
        self.assertEqual(report["status_counts"]["retracted"], 1)
        self.assertEqual(report["orphan_experiences"], ["orphan"])
        self.assertEqual(report["redacted_experiences"], ["retracted"])
        self.assertEqual(report["retracted_or_superseded"],
                         ["retracted", "superseded"])
        self.assertEqual(report["narrowed_experiences"], ["narrowed"])

    def test_full_rebuild_rederives_experiences_and_reports_progress(self):
        builder = load_builder()
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            ref = self._source(vault, "s1", "child hangs; bound waits")
            db = vault / "kb-experience.db"
            conn = exp.connect(db)
            exp.ensure_schema(conn)
            exp.append_event(conn, event_id="event-1", session_id="s1", task_id="t1",
                             event_type="attempt", observed_at="2026-08-26T10:00:00Z",
                             payload={"situation": "child hangs", "action": "bound timeout",
                                      "lesson": "bound waits"},
                             source_refs=[ref])
            exp.record_outcome(conn, outcome_id="out-1", session_id="s1", task_id="t1",
                               state="success", evidence=[{"kind": "test", "value": "pass"}],
                               attribution_strength="strong", observed_at="2026-08-26")
            exp.save_experience(conn, experience_id="orphan", session_id="old", task_id="old",
                               status="candidate", situation="old", approach="old",
                               observed_result="old", lesson="old", applicability="old",
                               outcome_state="unknown", confidence=0.2)
            conn.close()
            progress = []
            report = builder.rebuild_experience_store(db, progress_fn=progress.append)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["derived_experiences"], 1)
            self.assertEqual(report["orphan_experiences"], ["orphan"])
            self.assertEqual(progress[0]["phase"], "scan")
            self.assertEqual(progress[-1]["phase"], "complete")
            conn = exp.connect(db)
            try:
                rows = conn.execute("SELECT experience_id, status FROM experiences").fetchall()
                event = conn.execute("SELECT payload_json FROM experience_events").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(rows, [("experience-ec6d822afdb17dbab473", "candidate")])
            self.assertEqual(json.loads(event)["lesson"], "bound waits")

    def test_failed_rebuild_keeps_previous_store(self):
        builder = load_builder()
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "kb-experience.db"
            conn = exp.connect(db)
            exp.ensure_schema(conn)
            exp.save_experience(conn, experience_id="stable", session_id="s", task_id="t",
                               status="candidate", situation="s", approach="a",
                               observed_result="r", lesson="stable", applicability="scope",
                               outcome_state="unknown", confidence=0.2)
            exp.append_event(conn, event_id="event-1", session_id="s", task_id="t",
                             event_type="attempt", observed_at="2026-08-26T10:00:00Z",
                             payload={"lesson": "new"}, source_refs=["raw#1"])
            conn.close()
            before = db.read_bytes()
            report = builder.rebuild_experience_store(
                db, derive_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(db.read_bytes(), before)

    def test_rebuild_can_materialize_the_local_vector_projection(self):
        builder = load_builder()
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            ref = self._source(vault, "retry", "retry; bound retry")
            db = vault / "kb-experience.db"
            conn = exp.connect(db)
            exp.ensure_schema(conn)
            exp.append_event(conn, event_id="event-1", session_id="s", task_id="t",
                             event_type="attempt", observed_at="2026-08-26T10:00:00Z",
                             payload={"situation": "retry", "action": "bound retry",
                                      "lesson": "bound retry"}, source_refs=[ref])
            exp.record_outcome(conn, outcome_id="out-1", session_id="s", task_id="t",
                               state="success", evidence=[{"kind": "test"}],
                               attribution_strength="strong")
            conn.close()
            report = builder.rebuild_experience_store(
                db, embed_fn=lambda _text: [1, 0, 0, 0], embed_id="fake:4")
            self.assertEqual(report["vector_status"], "ok")
            conn = exp.connect(db)
            try:
                exp.ensure_recall_schema(conn, dim=4, embed_id="fake:4")
                default_hits = exp.experience_hits(
                    conn, query_vector=[1, 0, 0, 0], query_text="bound retry")
                diagnostic_hits = exp.experience_hits(
                    conn, query_vector=[1, 0, 0, 0], query_text="bound retry",
                    statuses=("candidate",))
            finally:
                conn.close()
            self.assertEqual(default_hits, [])
            self.assertEqual(
                [hit["status"] for hit in diagnostic_hits], ["candidate"])


if __name__ == "__main__":
    unittest.main()

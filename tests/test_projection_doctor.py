"""Read-only health checks for the source and experience projections."""
from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _experience as exp  # noqa: E402
import _source_ref as source_ref  # noqa: E402


class ProjectionDoctorTest(unittest.TestCase):
    def test_health_is_read_only_and_reports_split_stores_and_flags(self):
        spec = importlib.util.spec_from_file_location(
            "kb_projection_doctor", SCRIPTS / "kb-projection-doctor.py")
        doctor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(doctor)

        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            (vault / ".claude").mkdir()
            (vault / "01-raw" / "transcripts").mkdir(parents=True)
            (vault / "01-raw" / "transcripts" / "s.md").write_text("source", encoding="utf-8")
            (vault / "kennisbank-settings.json").write_text(
                json.dumps({"source_explicit_recall": False,
                            "experience_explicit_recall": True,
                            "experience_recall": True}),
                encoding="utf-8")
            ledger = exp.ledger_path(vault)
            conn = exp.connect(ledger)
            exp.ensure_ledger_schema(conn)
            conn.close()
            projection = exp.projection_path(vault)
            conn = exp.connect(projection)
            exp.ensure_projection_schema(conn, dim=None, embed_id="lexical-only:1")
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("experience_projection_version", "1"))
            conn.commit()
            conn.close()
            before = {ledger: ledger.read_bytes(), projection: projection.read_bytes()}
            report = doctor.health(vault, live_embed_id="fake:3")
            self.assertEqual(report["routes"], {"experience": "enabled", "source": "disabled"})
            self.assertEqual(report["experience"]["ledger"]["status"], "ready")
            self.assertEqual(report["experience"]["ledger"]["integrity_mode"], "quick")
            self.assertEqual(report["experience"]["projection"]["status"], "ready")
            self.assertEqual(report["experience"]["projection"]["projection_version"], "1")
            self.assertEqual(report["experience"]["projection"]["model_compatibility"],
                             "lexical_fallback")
            self.assertIn("experience_recall", report["forbidden_flags"])
            self.assertEqual(ledger.read_bytes(), before[ledger])
            self.assertEqual(projection.read_bytes(), before[projection])

    def test_source_health_reports_stale_orphaned_projection(self):
        spec = importlib.util.spec_from_file_location(
            "kb_projection_doctor", SCRIPTS / "kb-projection-doctor.py")
        doctor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(doctor)
        import _source_recall as source

        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            (vault / ".claude").mkdir()
            source_file = vault / "05-bronnen" / "s.md"
            source_file.parent.mkdir()
            source_file.write_text("original", encoding="utf-8")
            db = vault / ".claude" / "kb-source.db"
            conn = source.connect(db)
            source.ensure_schema(conn)
            conn.execute(
                "INSERT OR REPLACE INTO source_meta(key, value) VALUES (?, ?)",
                ("retrieval_backend", "sqlite_fts5"))
            conn.commit()
            source.upsert_source(conn, source_path="05-bronnen/s.md",
                                 source_hash="sha256:old", chunks=[{
                                     "index": 0, "start": 0, "end": 8,
                                     "text": "original"}])
            source.upsert_source(conn, source_path="05-bronnen/missing.md",
                                 source_hash="sha256:missing", chunks=[{
                                     "index": 0, "start": 0, "end": 7,
                                     "text": "missing"}])
            redacted = vault / "05-bronnen" / "redacted.md"
            redacted.write_text("---\nredacted: true\n---\nsecret", encoding="utf-8")
            source.upsert_source(conn, source_path="05-bronnen/redacted.md",
                                 source_hash="sha256:redacted", chunks=[{
                                     "index": 0, "start": 0, "end": 6,
                                     "text": "secret"}])
            conn.close()
            source_file.write_text("changed", encoding="utf-8")
            report = doctor.health(vault)["source"]
            self.assertEqual(report["status"], "ready")
            self.assertEqual(report["retrieval_backend"], "sqlite_fts5")
            self.assertEqual(report["stale_sources"], ["05-bronnen/s.md"])
            self.assertEqual(report["missing_sources"], ["05-bronnen/missing.md"])
            self.assertEqual(report["redacted_sources"], ["05-bronnen/redacted.md"])
            self.assertEqual(report["integrity"], "ok")
            self.assertEqual(report["forbidden_vector_tables"], [])

    def test_projection_health_resolves_changed_source_hash(self):
        spec = importlib.util.spec_from_file_location(
            "kb_projection_doctor", SCRIPTS / "kb-projection-doctor.py")
        doctor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(doctor)

        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            (vault / ".claude").mkdir()
            raw = vault / "01-raw" / "transcripts" / "session.md"
            raw.parent.mkdir(parents=True)
            raw.write_text("verified source", encoding="utf-8")
            ref = source_ref.make_source_ref(
                vault, "01-raw/transcripts/session.md", start=0, end=15)
            conn = exp.connect(exp.projection_path(vault))
            exp.ensure_projection_schema(conn, dim=None, embed_id="lexical-only:1")
            exp.save_experience(
                conn, experience_id="exp-stale", session_id="s", task_id="t",
                status="candidate", situation="situation", approach="approach",
                observed_result="result", lesson="lesson", applicability="local",
                outcome_state="success", confidence=0.2, source_refs=[ref])
            conn.close()
            raw.write_text("changed source!", encoding="utf-8")

            projection = doctor.health(vault)["experience"]["projection"]
            self.assertEqual(projection["stale_count"], 1)
            self.assertEqual(projection["resolved_source_ref_counts"], {"stale": 1})


if __name__ == "__main__":
    unittest.main()

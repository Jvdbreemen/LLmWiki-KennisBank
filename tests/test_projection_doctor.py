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


class ProjectionDoctorTest(unittest.TestCase):
    def test_health_is_read_only_and_reports_disabled_routes(self):
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
                json.dumps({"source_recall": False, "experience_recall": True}),
                encoding="utf-8")
            db = vault / ".claude" / "kb-experience.db"
            conn = exp.connect(db)
            exp.ensure_schema(conn)
            exp.save_experience(conn, experience_id="candidate", session_id="s", task_id="t",
                               status="candidate", situation="s", approach="a",
                               observed_result="unknown", lesson="l", applicability="scope",
                               outcome_state="unknown", confidence=0.2)
            conn.close()
            before = db.read_bytes()
            report = doctor.health(vault)
            self.assertEqual(report["routes"], {"experience": "enabled", "source": "disabled"})
            self.assertEqual(report["experience"]["status"], "ready")
            self.assertEqual(report["experience"]["status_counts"], {"candidate": 1})
            self.assertTrue(report["experience"]["rebuildable"])
            self.assertEqual(db.read_bytes(), before)

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
            source.ensure_schema(conn, 4, "fake:4")
            conn.execute("INSERT INTO source_manifest(source_path, source_hash) VALUES (?, ?)",
                         ("05-bronnen/s.md", "sha256:old"))
            conn.commit()
            source.upsert_source(conn, source_path="05-bronnen/s.md",
                                 source_hash="sha256:old", chunks=[{
                                     "index": 0, "start": 0, "end": 8, "text": "original"}],
                                 vectors=[[1, 0, 0, 0]])
            conn.close()
            source_file.write_text("changed", encoding="utf-8")
            report = doctor.health(vault)["source"]
            self.assertEqual(report["status"], "ready")
            self.assertEqual(report["stale_sources"], ["05-bronnen/s.md"])


if __name__ == "__main__":
    unittest.main()

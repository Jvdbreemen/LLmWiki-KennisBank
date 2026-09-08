"""Legacy experience migration is previewable, reversible, and idempotent."""
from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _migration_module():
    path = SCRIPTS / "_experience_migration.py"
    if not path.is_file():
        raise AssertionError("TASK-229 must provide scripts/_experience_migration.py")
    spec = importlib.util.spec_from_file_location("_experience_migration_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProjectionMigrationContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        claude = self.vault / ".claude"
        claude.mkdir(parents=True)
        self.legacy = claude / "kb-experience.db"
        conn = sqlite3.connect(self.legacy)
        conn.execute("CREATE TABLE experience_events(event_id TEXT PRIMARY KEY, payload_json TEXT)")
        conn.execute("INSERT INTO experience_events VALUES ('evt-1', '{}')")
        conn.commit()
        conn.close()

    def test_preflight_and_dry_run_do_not_mutate_the_vault(self):
        migration = _migration_module()
        before = self.legacy.read_bytes()
        report = migration.preflight(self.vault)
        self.assertFalse(report["mutated"])
        self.assertTrue(report["legacy_exists"])
        dry = migration.migrate(self.vault, dry_run=True)
        self.assertFalse(dry["mutated"])
        self.assertEqual(self.legacy.read_bytes(), before)
        self.assertFalse((self.vault / ".claude" / "kb-experience-ledger.db").exists())
        self.assertEqual(report["legacy_files"][0]["bytes"], len(before))
        self.assertEqual(report["counts"], report["legacy_tables"])
        self.assertIn("legacy", report["schema_versions"])
        self.assertGreaterEqual(report["disk_estimate_bytes"], len(before) * 2)
        self.assertEqual(report["backup_target"], report["backup_path"])
        self.assertIn("feature_flags", report)

    def test_real_migration_preserves_legacy_and_is_idempotent(self):
        migration = _migration_module()
        first = migration.migrate(self.vault, dry_run=False)
        second = migration.migrate(self.vault, dry_run=False)
        self.assertTrue(self.legacy.exists())
        self.assertTrue((self.vault / ".claude" / "kb-experience-ledger.db").exists())
        self.assertTrue(first["mutated"])
        self.assertFalse(second["mutated"])
        self.assertTrue(first["backup_path"])
        self.assertEqual(first["verified_counts"]["experience_events"], 1)
        self.assertEqual(
            Path(first["backup_path"]).read_bytes(), self.legacy.read_bytes())

    def test_interrupted_migration_preserves_previous_good_ledger(self):
        migration = _migration_module()
        ledger = self.vault / ".claude" / "kb-experience-ledger.db"
        ledger.write_bytes(b"previous-good-ledger")

        def fail_before_swap():
            raise RuntimeError("injected interruption")

        report = migration.migrate(
            self.vault, dry_run=False, before_swap=fail_before_swap)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(ledger.read_bytes(), b"previous-good-ledger")

    def _canonical_ledger(self):
        migration = _migration_module()
        ledger = self.vault / ".claude" / "kb-experience-ledger.db"
        conn = sqlite3.connect(ledger)
        migration.ensure_ledger_schema(conn)
        conn.execute(
            "INSERT INTO experience_events VALUES (?,?,?,?,?,?,?,?)",
            ("owner-event", "session", "task", "observation", "2026-09-08",
             '{"bounded":"owner-approved"}', "[]", "1"))
        conn.commit()
        conn.close()
        return ledger

    def test_existing_canonical_ledger_requires_review_and_is_never_replaced(self):
        migration = _migration_module()
        ledger = self._canonical_ledger()
        before = ledger.read_bytes()
        report = migration.migrate(self.vault)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["mutated"])
        self.assertEqual(report["reason"], "existing_ledger_requires_review")
        self.assertEqual(ledger.read_bytes(), before)

    def test_dry_run_exposes_existing_target_conflict_without_changes(self):
        migration = _migration_module()
        ledger = self._canonical_ledger()
        before = {p.name: p.read_bytes() for p in ledger.parent.iterdir()}
        report = migration.migrate(self.vault, dry_run=True)
        self.assertEqual(report["status"], "conflict")
        self.assertTrue(report["existing_ledger_requires_review"])
        self.assertFalse(report["mutated"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in ledger.parent.iterdir()})

    def test_unsupported_no_clobber_publish_fails_without_replace_fallback(self):
        migration = _migration_module()
        with mock.patch.object(migration.os, "link", side_effect=OSError("unsupported")):
            with mock.patch.object(migration.os, "replace") as replace:
                report = migration.migrate(self.vault)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["mutated"])
        replace.assert_not_called()
        self.assertFalse((self.vault / ".claude" / "kb-experience-ledger.db").exists())
        self.assertEqual(list((self.vault / ".claude").glob("*.staging")), [])

    def test_concurrent_first_capture_cannot_be_overwritten_at_publication(self):
        migration = _migration_module()
        captured = {}

        def capture_before_publication():
            ledger = self._canonical_ledger()
            captured["bytes"] = ledger.read_bytes()

        report = migration.migrate(self.vault, before_swap=capture_before_publication)
        ledger = self.vault / ".claude" / "kb-experience-ledger.db"
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["mutated"])
        self.assertEqual(ledger.read_bytes(), captured["bytes"])

    def test_interrupted_new_target_publishes_nothing_and_leaves_foreign_stage(self):
        migration = _migration_module()
        foreign_stage = self.vault / ".claude" / "kb-experience-ledger.db.staging"
        foreign_stage.write_bytes(b"another operation owns this")
        reached = []

        def fail_before_publication():
            reached.append(True)
            raise RuntimeError("injected interruption")

        report = migration.migrate(self.vault, before_swap=fail_before_publication)
        self.assertEqual(reached, [True])
        self.assertEqual(report["status"], "failed")
        self.assertFalse((self.vault / ".claude" / "kb-experience-ledger.db").exists())
        self.assertEqual(foreign_stage.read_bytes(), b"another operation owns this")
        self.assertEqual(list((self.vault / ".claude").glob("*.staging")), [foreign_stage])


if __name__ == "__main__":
    unittest.main()

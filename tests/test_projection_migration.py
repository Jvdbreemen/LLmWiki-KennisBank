"""Legacy experience migration is previewable, reversible, and idempotent."""
from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

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

    def test_real_migration_preserves_legacy_and_is_idempotent(self):
        migration = _migration_module()
        first = migration.migrate(self.vault, dry_run=False)
        second = migration.migrate(self.vault, dry_run=False)
        self.assertTrue(self.legacy.exists())
        self.assertTrue((self.vault / ".claude" / "kb-experience-ledger.db").exists())
        self.assertTrue(first["mutated"])
        self.assertFalse(second["mutated"])
        self.assertTrue(first["backup_path"])

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


if __name__ == "__main__":
    unittest.main()

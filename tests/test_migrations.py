import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("_migrations", SCRIPTS / "_migrations.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class MigrationsTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-migr-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self.settings = self.tmp / "settings.json"
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_read_stamp_absent_is_zero(self):
        self.assertEqual(self.m.read_stamp(self.vault), "0.0.0")

    def test_pending_gates_on_stamp(self):
        self.assertTrue(self.m.pending(self.vault))           # geen stamp -> alles pending
        self.m.write_stamp(self.vault, self.m.VERSION)
        self.assertEqual(self.m.pending(self.vault), [])       # actueel -> niets

    def test_run_applies_and_stamps(self):
        applied = self.m.run(self.vault, str(self.settings))
        self.assertTrue(applied)
        self.assertEqual(self.m.read_stamp(self.vault), self.m.VERSION)
        # geheugen-dirs migratie
        self.assertTrue((self.vault / "09-memory").is_dir())
        # toggles migratie
        data = json.loads((self.vault / "kennisbank-settings.json").read_text(encoding="utf-8"))
        self.assertIn("memory_capture", data)
        # hooks migratie
        s = json.loads(self.settings.read_text(encoding="utf-8"))
        joined = json.dumps(s)
        self.assertIn("build-kb-index.py", joined)

    def test_run_idempotent(self):
        self.m.run(self.vault, str(self.settings))
        self.assertEqual(self.m.run(self.vault, str(self.settings)), [])  # niets pending

    def test_failing_migration_leaves_stamp(self):
        # injecteer een falende migratie vooraan
        def boom(vault, ctx):
            raise RuntimeError("kapot")
        self.m.MIGRATIONS.insert(0, ("0.9.0", "boom", boom))
        try:
            with self.assertRaises(RuntimeError):
                self.m.run(self.vault, str(self.settings))
            self.assertEqual(self.m.read_stamp(self.vault), "0.0.0")  # geen stamp
        finally:
            self.m.MIGRATIONS.pop(0)

    def test_skip_hooks(self):
        self.m.run(self.vault, str(self.settings), skip_hooks=True)
        self.assertFalse(self.settings.exists())  # geen hooks geschreven

    def test_corrupt_global_settings_soft_skip_hooks_applies_toggles_and_stamps(self):
        # F4: corrupt ~/.claude/settings.json must NOT block toggles + stamp.
        # _m_register_hooks should catch ValueError and warn, not raise.
        self.settings.write_text("{ not json", encoding="utf-8")
        # Should not raise; returns applied list (may exclude hooks)
        applied = self.m.run(self.vault, str(self.settings))
        # stamp MUST be written
        self.assertEqual(self.m.read_stamp(self.vault), self.m.VERSION)
        # toggles MUST be applied
        settings_data = json.loads((self.vault / "kennisbank-settings.json").read_text(encoding="utf-8"))
        self.assertIn("memory_capture", settings_data)
        # corrupt file must NOT be overwritten by hooks registration
        self.assertEqual(self.settings.read_text(encoding="utf-8"), "{ not json")

    def test_run_does_not_downgrade_newer_stamp(self):
        # F6: if vault already has a NEWER stamp, run() must leave it intact.
        future_version = "9.9.9"
        self.m.write_stamp(self.vault, future_version)
        # pending() will be empty because 9.9.9 > 0.9.0
        self.m.run(self.vault, str(self.settings))
        self.assertEqual(self.m.read_stamp(self.vault), future_version,
                         "run() must not downgrade a newer version stamp")

    def test_mid_list_failure_leaves_stamp_at_old_value(self):
        # M2: a migration that fails AFTER an earlier one applied
        # leaves the stamp at the old value (resume semantics).
        call_log = []

        def first_ok(vault, ctx):
            call_log.append("first_ok")

        def second_boom(vault, ctx):
            call_log.append("second_boom")
            raise RuntimeError("mid-list boom")

        self.m.MIGRATIONS.insert(0, ("0.9.0", "second_boom", second_boom))
        self.m.MIGRATIONS.insert(0, ("0.9.0", "first_ok", first_ok))
        try:
            with self.assertRaises(RuntimeError):
                self.m.run(self.vault, str(self.settings))
            # The first migration ran, but the second raised — stamp must be at 0.0.0
            self.assertEqual(self.m.read_stamp(self.vault), "0.0.0",
                             "stamp must stay at old value when a mid-list migration fails")
            self.assertIn("first_ok", call_log, "first migration must have been applied")
        finally:
            # Clean up injected migrations
            self.m.MIGRATIONS.pop(0)
            self.m.MIGRATIONS.pop(0)


if __name__ == "__main__":
    unittest.main()

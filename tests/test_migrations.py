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


if __name__ == "__main__":
    unittest.main()

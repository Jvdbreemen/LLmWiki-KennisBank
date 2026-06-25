"""Tests voor scripts/_settings.py - de toggle-store.

_settings.py heeft geen hyphen, dus het importeert direct zodra scripts/ op
sys.path staat (idem _vaultpath.py). De vault wordt per test naar een temp-map
gewezen via KENNISBANK_VAULT; de env wordt in tearDown hersteld zodat hij niet
naar latere tests lekt.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _settings  # noqa: E402


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-set-"))
        self.vault = self.tmp / "vault"
        self.vault.mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, text: str):
        (self.vault / "kennisbank-settings.json").write_text(text, encoding="utf-8")

    def test_get_missing_file_returns_default(self):
        self.assertTrue(_settings.get("embed_index", True))
        self.assertFalse(_settings.get("auto_archive", False))

    def test_get_corrupt_file_returns_default(self):
        self._write("{ this is not json")
        self.assertTrue(_settings.get("embed_index", True))

    def test_get_missing_key_returns_default(self):
        self._write(json.dumps({"embed_index": True}))
        self.assertFalse(_settings.get("auto_archive", False))

    def test_get_reads_stored_value(self):
        self._write(json.dumps({"auto_archive": True}))
        self.assertTrue(_settings.get("auto_archive", False))

    def test_get_coerces_hand_edited_string(self):
        # Een met de hand bewerkte string-waarde mag niet per ongeluk truthy zijn.
        self._write(json.dumps({"embed_index": "false"}))
        self.assertFalse(_settings.get("embed_index", True))
        self._write(json.dumps({"auto_archive": "true"}))
        self.assertTrue(_settings.get("auto_archive", False))

    def test_set_then_get_roundtrip(self):
        _settings.set("auto_archive", True)
        self.assertTrue(_settings.get("auto_archive", False))
        _settings.set("auto_archive", False)
        self.assertFalse(_settings.get("auto_archive", True))

    def test_set_preserves_unknown_keys(self):
        self._write(json.dumps({"some_future_key": 42}))
        _settings.set("auto_archive", True)
        data = json.loads((self.vault / "kennisbank-settings.json").read_text(encoding="utf-8"))
        self.assertEqual(data["some_future_key"], 42)
        self.assertTrue(data["auto_archive"])

    def test_init_writes_defaults_when_absent(self):
        self.assertTrue(_settings.init())
        data = json.loads((self.vault / "kennisbank-settings.json").read_text(encoding="utf-8"))
        self.assertEqual(data, _settings.DEFAULTS)

    def test_init_is_noop_when_present(self):
        self._write(json.dumps({"auto_archive": True}))
        self.assertFalse(_settings.init())
        data = json.loads((self.vault / "kennisbank-settings.json").read_text(encoding="utf-8"))
        self.assertEqual(data, {"auto_archive": True})

    def test_settings_path_honors_env(self):
        self.assertEqual(_settings.settings_path(), self.vault / "kennisbank-settings.json")

    # --- CLI ---
    def _cli(self, *args):
        env = dict(os.environ)
        env["KENNISBANK_VAULT"] = str(self.vault)
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "_settings.py"), *args],
            env=env, capture_output=True, text=True,
        )

    def test_cli_get_default(self):
        r = self._cli("get", "embed_index")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "1")
        r = self._cli("get", "auto_archive")
        self.assertEqual(r.stdout.strip(), "0")

    def test_cli_set_then_get(self):
        self._cli("set", "auto_archive", "true")
        r = self._cli("get", "auto_archive")
        self.assertEqual(r.stdout.strip(), "1")

    def test_cli_init(self):
        r = self._cli("init")
        self.assertEqual(r.stdout.strip(), "written")
        r = self._cli("init")
        self.assertEqual(r.stdout.strip(), "exists")

    def test_example_matches_defaults(self):
        example = Path(__file__).resolve().parent.parent / "kennisbank-settings.example.json"
        data = json.loads(example.read_text(encoding="utf-8"))
        self.assertEqual(set(data.keys()), set(_settings.DEFAULTS.keys()))
        self.assertEqual(data, _settings.DEFAULTS)


if __name__ == "__main__":
    unittest.main()

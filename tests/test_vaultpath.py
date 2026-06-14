"""Tests for the KENNISBANK_VAULT env-var resolver in scripts/_vaultpath.py.

The four non-importer scripts (stale-check, semantic-tiling, auto-crosslink,
intake-scan) used to hardcode `Path.home() / "KennisBank"`. They now resolve the
vault via the shared helper vault_root(), which honors $KENNISBANK_VAULT and
defaults to ~/KennisBank. _vaultpath.py has no hyphen so it imports directly
once scripts/ is on sys.path.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _vaultpath  # noqa: E402


class TestVaultRootResolver(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get(_vaultpath.ENV_VAR)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop(_vaultpath.ENV_VAR, None)
        else:
            os.environ[_vaultpath.ENV_VAR] = self._saved

    def test_env_var_is_honored(self):
        os.environ[_vaultpath.ENV_VAR] = "/tmp/my-kb"
        self.assertEqual(_vaultpath.vault_root(), Path("/tmp/my-kb"))

    def test_default_when_unset(self):
        os.environ.pop(_vaultpath.ENV_VAR, None)
        self.assertEqual(_vaultpath.vault_root(), Path.home() / "KennisBank")

    def test_empty_env_var_falls_back_to_default(self):
        os.environ[_vaultpath.ENV_VAR] = ""
        self.assertEqual(_vaultpath.vault_root(), Path.home() / "KennisBank")

    def test_whitespace_env_var_falls_back_to_default(self):
        os.environ[_vaultpath.ENV_VAR] = "   "
        self.assertEqual(_vaultpath.vault_root(), Path.home() / "KennisBank")

    def test_tilde_is_expanded(self):
        os.environ[_vaultpath.ENV_VAR] = "~/some-vault"
        self.assertEqual(_vaultpath.vault_root(), Path.home() / "some-vault")

    def test_scripts_use_the_resolver(self):
        # Loading a script with the env var set must propagate to its vault paths.
        os.environ[_vaultpath.ENV_VAR] = "/tmp/kb-resolver-test"
        from _loader import load_script

        stale = load_script("stale-check.py")
        self.assertEqual(stale.VAULT_ROOT, Path("/tmp/kb-resolver-test"))
        self.assertEqual(stale.WIKI_DIR, Path("/tmp/kb-resolver-test") / "02-wiki")

        intake = load_script("intake-scan.py")
        self.assertEqual(
            intake.INBOX, Path("/tmp/kb-resolver-test") / "00-inbox"
        )

        crosslink = load_script("auto-crosslink.py")
        self.assertEqual(crosslink.VAULT_ROOT, Path("/tmp/kb-resolver-test"))

        tiling = load_script("semantic-tiling.py")
        self.assertEqual(tiling.WIKI_DIR, Path("/tmp/kb-resolver-test") / "02-wiki")


if __name__ == "__main__":
    unittest.main()

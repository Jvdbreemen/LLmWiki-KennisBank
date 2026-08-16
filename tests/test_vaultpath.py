"""Tests for the KENNISBANK_VAULT env-var resolver in scripts/_vaultpath.py.

Every script (the non-importers stale-check, semantic-tiling, auto-crosslink,
intake-scan AND the importers build-karpathy-index, import-cc-history,
import-claudeai-export, import-folder) used to hardcode
`Path.home() / "KennisBank"`. They now resolve the vault via the shared helper
vault_root(), which honors $KENNISBANK_VAULT and defaults to ~/KennisBank.
_vaultpath.py has no hyphen so it imports directly once scripts/ is on sys.path.

`test_no_script_hardcodes_the_vault` is the regression guard: it scans every
scripts/*.py and fails if any reintroduces the literal hardcode. This is the
test that would have caught the importer scripts shipping to the wrong vault.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
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

    def _load_vaultpath_copy(self, scripts_dir: Path):
        """Load a copy of the real _vaultpath.py from a constructed tree, so
        its __file__ points into that layout — the module under test is the
        real source text, no __file__ monkeypatching."""
        src = SCRIPTS_DIR / "_vaultpath.py"
        dst = scripts_dir / "_vaultpath.py"
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        spec = importlib.util.spec_from_file_location(
            f"_vaultpath_copy_{id(self)}", dst)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_checkout_layout_never_treats_repo_parent_as_vault(self):
        """TASK-181: in a checkout, parents[2] is the repo's PARENT (often
        $HOME). A .claude directory existing there does not make it a vault;
        the old existence check resolved to it AND stamped it into the env."""
        os.environ.pop(_vaultpath.ENV_VAR, None)
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td).resolve() / "fakehome"
            (fake_home / ".claude").mkdir(parents=True)
            scripts = fake_home / "repo" / "scripts"
            scripts.mkdir(parents=True)
            mod = self._load_vaultpath_copy(scripts)
            self.assertEqual(mod.vault_root(), mod.DEFAULT_VAULT)
            self.assertIsNone(os.environ.get(_vaultpath.ENV_VAR),
                              "a checkout must not export a vault root")

    def test_deployed_layout_resolves_own_vault_and_exports_it(self):
        """The deployed layout (<vault>/.claude/scripts/) must keep working,
        including the env export that detached warm-up children rely on."""
        os.environ.pop(_vaultpath.ENV_VAR, None)
        try:
            with tempfile.TemporaryDirectory() as td:
                vault = Path(td).resolve() / "vault"
                scripts = vault / ".claude" / "scripts"
                scripts.mkdir(parents=True)
                mod = self._load_vaultpath_copy(scripts)
                self.assertEqual(mod.vault_root(), vault)
                self.assertEqual(os.environ.get(_vaultpath.ENV_VAR), str(vault))
        finally:
            os.environ.pop(_vaultpath.ENV_VAR, None)

    def test_scripts_use_the_resolver(self):
        # Loading a script with the env var set must propagate to its vault paths.
        os.environ[_vaultpath.ENV_VAR] = "/tmp/kb-resolver-test"
        from tests._loader import load_script

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

    def test_importer_scripts_use_the_resolver(self):
        # The importer scripts expose VAULT_DEFAULT as the argparse default;
        # it must resolve via the env var, not a Path.home() hardcode.
        os.environ[_vaultpath.ENV_VAR] = "/tmp/kb-importer-test"
        from tests._loader import load_script

        for name in (
            "build-karpathy-index.py",
            "import-cc-history.py",
            "import-claudeai-export.py",
            "import-folder.py",
        ):
            mod = load_script(name)
            self.assertEqual(
                mod.VAULT_DEFAULT,
                Path("/tmp/kb-importer-test"),
                f"{name} ignores $KENNISBANK_VAULT",
            )

    def test_no_script_hardcodes_the_vault(self):
        # Regression guard: no script may reintroduce the literal hardcode.
        # _vaultpath.py is the single allowed place (it IS the fallback).
        import re

        pattern = re.compile(r"""home\(\)\s*/\s*['"]KennisBank['"]""")
        offenders = []
        for script in SCRIPTS_DIR.glob("*.py"):
            if script.name == "_vaultpath.py":
                continue
            if pattern.search(script.read_text(encoding="utf-8")):
                offenders.append(script.name)
        self.assertEqual(
            offenders, [], f"hardcoded vault default in: {offenders}; use vault_root()"
        )


if __name__ == "__main__":
    unittest.main()

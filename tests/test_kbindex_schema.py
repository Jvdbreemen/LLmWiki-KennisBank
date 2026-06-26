"""Tests voor scripts/_kbindex.py - verbinding + schema.

Gebruikt een echte sqlite-vec (pip-dep), maar geen embedmodel: vectoren zijn
fake. Vault naar temp via KENNISBANK_VAULT.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _kbindex  # noqa: E402


class KbIndexSchemaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-idx-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_index_path_under_claude(self):
        self.assertEqual(_kbindex.index_path(), self.vault / ".claude" / "kb-index.db")

    def test_connect_loads_sqlite_vec(self):
        conn = _kbindex.connect(":memory:")
        ver = conn.execute("select vec_version()").fetchone()[0]
        self.assertTrue(ver.startswith("v"))
        conn.close()

    def test_ensure_schema_idempotent_and_stores_meta(self):
        conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(conn, dim=8, embed_id="ollama:test")
        _kbindex.ensure_schema(conn, dim=8, embed_id="ollama:test")  # twice = no error
        self.assertEqual(_kbindex.meta_get(conn, "embed_id"), "ollama:test")
        self.assertEqual(_kbindex.meta_get(conn, "dim"), "8")
        tables = {r[0] for r in conn.execute(
            "select name from sqlite_master where type in ('table','view')")}
        self.assertIn("docs", tables)
        self.assertIn("meta", tables)
        conn.close()

    def test_is_valid_for(self):
        conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(conn, dim=8, embed_id="ollama:m1")
        self.assertTrue(_kbindex.is_valid_for(conn, "ollama:m1"))
        self.assertFalse(_kbindex.is_valid_for(conn, "ollama:m2"))
        conn.close()


if __name__ == "__main__":
    unittest.main()

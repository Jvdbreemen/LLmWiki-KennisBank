"""One embed model, in every surface that writes or reports one (TASK-182).

The v0.28.0 default flip (qwen3-embedding:8b -> 4b) shipped as bare literals
in three writers and left doctor.sh checking the OLD name — so on an affected
vault doctor said "installed" about a model recall no longer used, while
recall itself returned [] without a word. Mirrors
test_llm_model_default.py: the value lives once
(_embeddings.OLLAMA_DEFAULT_EMBED_MODEL), every writer aliases it, and the
stale previous default may not survive in any writer.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _embeddings  # noqa: E402
import _kbindex  # noqa: E402


def _load_installer():
    spec = importlib.util.spec_from_file_location(
        "install_agent_envs_embed_guard", str(SCRIPTS / "install-agent-envs.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class EmbedModelDefaultTest(unittest.TestCase):
    def setUp(self):
        self.m = _load_installer()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-embed-default-"))
        self._saved = {k: os.environ.get(k) for k in
                       ("KB_EMBED_PROVIDER", "KB_EMBED_MODEL",
                        "KB_EMBED_ENDPOINT", "KENNISBANK_VAULT")}
        for k in ("KB_EMBED_PROVIDER", "KB_EMBED_MODEL", "KB_EMBED_ENDPOINT"):
            os.environ.pop(k, None)
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)

    def tearDown(self):
        import shutil
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_definitions_are_one_value(self):
        self.assertEqual(_embeddings.OLLAMA_DEFAULT_EMBED_MODEL,
                         _embeddings._DEFAULTS["ollama"]["model"])
        self.assertEqual(self.m.KB_EMBED_MODEL_DEFAULT,
                         _embeddings.OLLAMA_DEFAULT_EMBED_MODEL)

    def test_fresh_vault_resolution_uses_it(self):
        cfg = self.m._resolve_embed_config(self.tmp)
        self.assertEqual(cfg["model"], self.m.KB_EMBED_MODEL_DEFAULT)

    def test_the_example_config_ships_the_same_model(self):
        # setup.sh copies this to the vault, where it OUTRANKS the code
        # default — a one-sided flip here is how upgraded vaults silently
        # stay behind (same trap test_llm_model_default.py documents).
        cfg = json.loads((REPO_ROOT / "kennisbank-embed.example.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(cfg["model"], _embeddings.OLLAMA_DEFAULT_EMBED_MODEL)

    def test_agent_instructions_name_it(self):
        block = self.m._agent_block("claude", self.tmp)
        self.assertIn(_embeddings.OLLAMA_DEFAULT_EMBED_MODEL, block)

    def test_no_stale_previous_default_survives_in_the_writers(self):
        # Scoped to WRITERS deliberately: tests/ pins :8b in config-pin
        # fixtures and docs/CHANGELOG record history — those are not writers.
        for rel in ("scripts/doctor.sh", "commands/sessielog.md"):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("qwen3-embedding:8b", text,
                             f"{rel} still names the pre-v0.28.0 default")

    def test_doctor_resolves_the_model_instead_of_hardcoding_one(self):
        text = (REPO_ROOT / "scripts" / "doctor.sh").read_text(encoding="utf-8")
        self.assertIn("--print-model", text)
        self.assertNotIn("OLLAMA_EMBED_MODEL:-qwen3-embedding", text)

    def test_setup_pulls_the_resolved_model(self):
        text = (REPO_ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertIn("ollama pull \"$EMBED_MODEL\"", text)
        self.assertIn("--print-model", text)

    def test_embed_mismatch_reports_and_respects_a_match(self):
        # embed_mismatch reads only the meta table; a plain sqlite file
        # suffices (no vec0 needed).
        db = self.tmp / "kb-index.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO meta VALUES ('embed_id', 'ollama:old-model')")
        conn.commit()
        self.assertEqual(_kbindex.embed_mismatch(conn, "ollama:new-model"),
                         ("ollama:old-model", "ollama:new-model"))
        self.assertIsNone(_kbindex.embed_mismatch(conn, "ollama:old-model"))
        conn.execute("DELETE FROM meta")
        conn.commit()
        # No stamp = legacy index, not a mismatch — never warn on those.
        self.assertIsNone(_kbindex.embed_mismatch(conn, "ollama:new-model"))
        conn.close()

    def test_print_model_resolves_through_the_config_chain(self):
        # The config pin must win over the code default — a pinned vault
        # stays untouched (AC#4), and the pull targets the RESOLVED model.
        (self.tmp / ".claude").mkdir(parents=True)
        (self.tmp / ".claude" / "kennisbank-embed.json").write_text(
            json.dumps({"provider": "ollama", "model": "pinned-model:1b"}),
            encoding="utf-8")
        import subprocess
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "_embeddings.py"), "--print-model"],
            capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(r.stdout.strip(), "pinned-model:1b")


if __name__ == "__main__":
    unittest.main()

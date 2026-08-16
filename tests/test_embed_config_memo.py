"""The embed config is memoized on (path, mtime_ns, size) — TASK-191.

embed_id() read and parsed kennisbank-embed.json twice per call, and an
index build calls it once per file: ~5000 redundant reads (~1.4s) per
build. The memo resolves the path at CALL time (TASK-196 lesson: never
freeze vault-derived state at import), so repointing KENNISBANK_VAULT or
editing the file invalidates it without any module reload.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _embeddings as emb  # noqa: E402


class ConfigMemoTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = {k: os.environ.get(k) for k in
                       ("KENNISBANK_VAULT", "KB_EMBED_PROVIDER",
                        "KB_EMBED_MODEL", "KB_EMBED_ENDPOINT")}
        for k in self._saved:
            os.environ.pop(k, None)
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    def _write(self, model):
        (self.vault / ".claude" / "kennisbank-embed.json").write_text(
            json.dumps({"provider": "ollama", "model": model}),
            encoding="utf-8")

    def test_the_memo_serves_the_same_object(self):
        self._write("model-a:1b")
        self.assertIs(emb._config(), emb._config())

    def test_editing_the_config_invalidates(self):
        self._write("model-a:1b")
        self.assertEqual(emb.embed_id(), "ollama:model-a:1b")
        # ander model, andere lengte: size verandert ook op grove mtime-fs
        self._write("model-b-langer:4b")
        self.assertEqual(emb.embed_id(), "ollama:model-b-langer:4b")

    def test_repointing_the_vault_invalidates(self):
        """TASK-196-regressiewacht: geen module-reload nodig na een
        env-wissel."""
        self._write("model-a:1b")
        self.assertEqual(emb.embed_id(), "ollama:model-a:1b")
        with tempfile.TemporaryDirectory() as other:
            (Path(other) / ".claude").mkdir(parents=True)
            (Path(other) / ".claude" / "kennisbank-embed.json").write_text(
                json.dumps({"provider": "ollama", "model": "elders:8b"}),
                encoding="utf-8")
            os.environ["KENNISBANK_VAULT"] = other
            self.assertEqual(emb.embed_id(), "ollama:elders:8b")

    def test_a_missing_config_is_empty_and_cached(self):
        self.assertEqual(emb._config(), {})
        self._write("model-a:1b")
        self.assertEqual(emb._config().get("model"), "model-a:1b")


if __name__ == "__main__":
    unittest.main()

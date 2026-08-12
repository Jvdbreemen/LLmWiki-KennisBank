"""One judge model, in every surface that writes one.

The judge/extraction model shares a GPU with the embedding model that serves the
retrieval hot path. Pin one that does not fit beside it and Ollama evicts the
embedder: the next recall pays a 30-60 s cold load against a 2 s budget, so
retrieval silently stops answering (TASK-139). The model therefore is not a free
choice per config writer -- it is one measured value.

Five places write it: _llm.py's own default, _copilot.py's pinned env, and the
Codex TOML, opencode plugin and opencode JSON that install-agent-envs.py
generates. Re-running the installer must not undo the fix, which is exactly what
happened before: the environment was corrected by hand while the installer still
carried the old model.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _copilot  # noqa: E402
import _llm  # noqa: E402


def _load_installer():
    spec = importlib.util.spec_from_file_location(
        "install_agent_envs_guard", str(SCRIPTS / "install-agent-envs.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class ModelDefaultTest(unittest.TestCase):
    def setUp(self):
        self.m = _load_installer()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-model-default-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude").mkdir(parents=True)
        self.model = _llm.OLLAMA_DEFAULT_MODEL

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_definitions_are_one_value(self):
        self.assertEqual(_copilot.KB_LLM_MODEL_DEFAULT, self.model)
        self.assertEqual(self.m.KB_LLM_MODEL_DEFAULT, self.model)
        self.assertEqual(_llm._DEFAULTS["ollama"]["model"], self.model)
        # The temporal Layer-3 fallback talks to Ollama directly (off by
        # default, and kept off the provider chain on purpose), but it loads a
        # model onto the same GPU, so it obeys the same size limit.
        import _activity
        self.assertEqual(_activity._LLM_MODEL, self.model)

    def test_copilot_env_pins_it(self):
        self.assertEqual(_copilot._kb_env(self.vault)["KB_LLM_MODEL"], self.model)

    def test_codex_mcp_block_pins_it(self):
        path = self.tmp / "config.toml"
        self.m._ensure_codex_mcp(path, self.vault)
        text = path.read_text(encoding="utf-8")
        self.assertIn(f'KB_LLM_MODEL = "{self.model}"', text)

    def test_opencode_plugin_and_config_pin_it(self):
        plugin = self.tmp / "plugin" / "kennisbank.js"
        plugin.parent.mkdir(parents=True, exist_ok=True)
        written = self.m._write_opencode_plugin(plugin, self.vault)
        self.assertIn(f'"{self.model}"', written.read_text(encoding="utf-8"))

        cfg = self.tmp / "opencode.json"
        self.m._ensure_opencode_config(cfg, self.vault, written)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        env = data["mcp"]["kennisbank"]["environment"]
        self.assertEqual(env["KB_LLM_MODEL"], self.model)

    def test_agent_instructions_name_it(self):
        self.assertIn(self.model, self.m._agent_block("codex", self.vault))

    def test_fresh_vault_config_and_resolution_use_it(self):
        cfg = self.m.configure_llm(self.vault, "ollama")
        self.assertEqual(cfg["model"], self.model)
        # And the resolver falls back to the same value with nothing configured.
        empty = self.tmp / "empty-vault"
        (empty / ".claude").mkdir(parents=True)
        saved = os.environ.pop("KB_LLM_MODEL", None)
        try:
            self.assertEqual(self.m._resolve_llm_config(empty)["model"], self.model)
        finally:
            if saved is not None:
                os.environ["KB_LLM_MODEL"] = saved

    def test_no_stale_model_literal_survives_in_the_writers(self):
        """A literal here is how the enumeration gets fixed and the rest stays.

        The measured combination is qwen3-embedding:4b (4.06 GB) + a ~4B judge
        (3.13 GB) on a 16 GB card; gemma4:12b costs 8.06 GB and evicts the
        embedder. If a bigger model is ever deliberately pinned, change
        _llm.OLLAMA_DEFAULT_MODEL -- not one writer.
        """
        for name in ("install-agent-envs.py", "_copilot.py"):
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            self.assertNotIn("gemma4", text, f"{name} still hardcodes a model")


if __name__ == "__main__":
    unittest.main()

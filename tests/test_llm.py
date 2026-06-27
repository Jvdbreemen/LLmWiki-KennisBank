"""Tests voor scripts/_llm.py - de model-router. Geen echt model/netwerk:
we monkeypatchen _call (de per-provider aanroep). Vault naar temp.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _llm  # noqa: E402


class LlmRouterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-llm-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved_env = {k: os.environ.get(k) for k in
                           ("KENNISBANK_VAULT", "KB_LLM_PROVIDERS", "KB_LLM_MODEL", "KB_LLM_ENDPOINT")}
        for k in ("KB_LLM_PROVIDERS", "KB_LLM_MODEL", "KB_LLM_ENDPOINT"):
            os.environ.pop(k, None)
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self._orig_call = _llm._call

    def tearDown(self):
        import shutil
        _llm._call = self._orig_call
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cfg(self, obj):
        import json
        (self.vault / ".claude" / "kennisbank-llm.json").write_text(
            json.dumps(obj), encoding="utf-8")

    def test_default_chain_is_ollama_local(self):
        self.assertEqual(_llm.providers(), ["ollama"])
        self.assertTrue(_llm.is_local())

    def test_generate_uses_first_provider(self):
        calls = []
        _llm._call = lambda prov, *a, **k: (calls.append(prov) or "OK van " + prov)
        self.assertEqual(_llm.generate("hi"), "OK van ollama")
        self.assertEqual(calls, ["ollama"])

    def test_chain_fallback_to_next_on_none(self):
        self._cfg({"providers": ["ollama", "openrouter"], "models": {"openrouter": "x"}})
        def fake(prov, *a, **k):
            return None if prov == "ollama" else "cloud-antwoord"
        _llm._call = fake
        buf = io.StringIO()
        with redirect_stderr(buf):
            out = _llm.generate("hi")
        self.assertEqual(out, "cloud-antwoord")
        # cloud-stap moet LUID loggen
        self.assertIn("cloud", buf.getvalue().lower())
        self.assertIn("openrouter", buf.getvalue())

    def test_all_fail_returns_none(self):
        self._cfg({"providers": ["ollama", "openrouter"]})
        _llm._call = lambda *a, **k: None
        self.assertIsNone(_llm.generate("hi"))

    def test_is_local_false_when_cloud_first(self):
        self._cfg({"providers": ["openrouter", "ollama"]})
        self.assertFalse(_llm.is_local())

    def test_env_overrides_providers(self):
        os.environ["KB_LLM_PROVIDERS"] = "ollama, claude-cli"
        self.assertEqual(_llm.providers(), ["ollama", "claude-cli"])


if __name__ == "__main__":
    unittest.main()

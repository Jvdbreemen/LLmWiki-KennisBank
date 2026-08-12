"""Reasoning must stay off, or the answer never arrives.

qwen3.5 is a reasoning model: it emits its chain-of-thought first and the answer
after, out of the same num_ctx budget. Measured on the reconcile prompt at
num_ctx 4096: 2106-3885 tokens of thinking, 30-56 s per call, and one call in
three came back with done_reason="length" and an EMPTY response — the reasoning
sat in a separate `thinking` field that no caller reads. With think=false the
same prompts took 1.6-1.7 s, spent 39-48 tokens, and all three parsed.

That failure is invisible without this guard. Every seam is fail-safe by design
(extract -> [], judge -> unverified, reconcile -> ADD), so a model that never
answers looks exactly like a model that answered "nothing to do here". A
refactor that drops the flag would degrade capture silently, which is why the
payload itself is pinned rather than the behaviour downstream of it.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _llm  # noqa: E402


class LlmThinkingTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self._orig = _llm._http_json
        _llm._http_json = lambda url, payload, headers, timeout: (
            self.sent.append((url, payload)) or {"response": "ok"})

    def tearDown(self):
        _llm._http_json = self._orig

    def test_generate_asks_the_model_not_to_think(self):
        _llm._call("ollama", "m", "http://localhost:11434", "", "p", "s", 10.0)
        self.assertEqual(len(self.sent), 1)
        url, payload = self.sent[0]
        self.assertTrue(url.endswith("/api/generate"))
        self.assertIn("think", payload)
        self.assertFalse(payload["think"])

    def test_the_context_window_is_still_pinned(self):
        """Without num_ctx Ollama uses the model's own default and the
        allocation grows; think=false does not replace that pin."""
        _llm._call("ollama", "m", "http://localhost:11434", "", "p", "s", 10.0)
        self.assertEqual(self.sent[0][1]["options"]["num_ctx"], _llm.OLLAMA_NUM_CTX)

    def test_thinking_is_off_by_default(self):
        self.assertFalse(_llm.OLLAMA_THINK)

    def test_it_can_be_turned_back_on(self):
        saved = os.environ.get("KB_LLM_THINK")
        os.environ["KB_LLM_THINK"] = "1"
        try:
            reloaded = importlib.reload(_llm)
            self.assertTrue(reloaded.OLLAMA_THINK)
        finally:
            if saved is None:
                os.environ.pop("KB_LLM_THINK", None)
            else:
                os.environ["KB_LLM_THINK"] = saved
            # Restore the module every other test in this session shares.
            importlib.reload(_llm)


class ActivityThinkingTest(unittest.TestCase):
    """The temporal fallback builds its own payload and needs the same flag.

    It is stricter than _llm's path: num_predict caps the answer at 128 tokens,
    so a thinking model spends the whole budget before it starts answering and
    returns an empty response every single time.
    """

    def test_temporal_fallback_asks_the_model_not_to_think(self):
        sys.path.insert(0, str(SCRIPTS))
        import _activity

        sent = {}

        class Resp:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return json.dumps({"response": "{}"}).encode("utf-8")

        import urllib.request
        orig = urllib.request.urlopen

        def fake(req, timeout=None):
            sent["payload"] = json.loads(req.data.decode("utf-8"))
            return Resp()

        urllib.request.urlopen = fake
        try:
            _activity._llm_call("prompt")
        finally:
            urllib.request.urlopen = orig

        self.assertIn("think", sent["payload"])
        self.assertFalse(sent["payload"]["think"])
        self.assertEqual(sent["payload"]["options"]["num_predict"], 128)


if __name__ == "__main__":
    unittest.main()

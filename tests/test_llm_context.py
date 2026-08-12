"""The judge call must pin its context window, and it must clear the chunk size.

Without an explicit num_ctx Ollama loads the model at its own default -- 16384
for qwen3.5:4b, which costs 3.6 GB of VRAM against 3.13 GB at 4096 on a 16 GB
card. That is half a gigabyte spent on context the judge never uses.

The lower bound matters more than the saving. memory-sweep chunks transcripts at
6000 characters before calling extract_candidates, so the prompt is roughly 1500
tokens plus a system prompt plus a JSON answer. Set the window under that and
Ollama truncates silently: the judge then answers about a transcript it only
partly saw, and nothing in the output says so.
"""
import os
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _llm  # noqa: E402
import _sweeputil as su  # noqa: E402


class TestJudgeContext(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self._orig = _llm._http_json
        _llm._http_json = lambda url, payload, headers, timeout: (
            self.sent.append(payload) or {"response": "ok"})
        self.saved = os.environ.get("KB_LLM_PROVIDERS")
        os.environ["KB_LLM_PROVIDERS"] = "ollama"

    def tearDown(self):
        _llm._http_json = self._orig
        if self.saved is None:
            os.environ.pop("KB_LLM_PROVIDERS", None)
        else:
            os.environ["KB_LLM_PROVIDERS"] = self.saved

    def test_generate_sends_a_context_window(self):
        _llm.generate("hello")
        self.assertEqual(self.sent[0]["options"]["num_ctx"], _llm.OLLAMA_NUM_CTX)

    def test_window_clears_the_sweep_chunk_size(self):
        """A chunk is 6000 characters; 4 characters per token is the rough rate."""
        chunk_tokens = su.chunk.__defaults__[0] // 4       # max_chars default
        self.assertGreater(_llm.OLLAMA_NUM_CTX, chunk_tokens * 2,
                           "context window leaves no room for a chunk plus its answer")


if __name__ == "__main__":
    unittest.main()

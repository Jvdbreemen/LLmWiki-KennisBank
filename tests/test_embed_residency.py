"""The embed call must pin the model in VRAM and cap its context.

Why this is tested. Ollama sizes an embedding model's allocation from the
context window, not from the document length, so the default 16384 context made
qwen3-embedding:4b claim 6.24 GB of VRAM against 2.5 GB of weights (measured on
a 16 GB RTX 3080). A judge model then no longer fitted beside it and Ollama
evicted the embedding model, after which every retrieval hook hit a 30-60 s cold
load against a 2 s budget and silently returned nothing.

Both halves of the fix are easy to drop during a refactor and neither fails
loudly: without num_ctx the allocation quietly triples, without keep_alive the
model unloads on a timer. Hence a test on the payload itself.
"""
import os
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _embeddings as emb  # noqa: E402


class TestEmbedResidency(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in
                      ("KB_EMBED_MODEL", "KB_EMBED_PROVIDER")}
        os.environ["KB_EMBED_PROVIDER"] = "ollama"
        os.environ["KB_EMBED_MODEL"] = "testmodel"
        self.sent = []
        self._orig = emb._http_json
        emb._http_json = lambda url, payload, headers, timeout: (
            self.sent.append(payload) or {"embedding": [0.1, 0.2]})

    def tearDown(self):
        emb._http_json = self._orig
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_context_is_capped(self):
        emb.embed("a question")
        self.assertEqual(self.sent[0]["options"]["num_ctx"], emb.OLLAMA_NUM_CTX)

    def test_context_leaves_room_for_the_longest_embedded_document(self):
        """doc_text caps a note at 1000 tokens; the window must clear that."""
        self.assertGreaterEqual(emb.OLLAMA_NUM_CTX, 1024)

    def test_model_is_pinned(self):
        """keep_alive -1 means never unload on a timer."""
        emb.embed("a question")
        self.assertEqual(self.sent[0]["keep_alive"], emb.OLLAMA_KEEP_ALIVE)
        self.assertEqual(emb.OLLAMA_KEEP_ALIVE, -1)


if __name__ == "__main__":
    unittest.main()

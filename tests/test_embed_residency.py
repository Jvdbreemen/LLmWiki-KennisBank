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


class TestIsResident(unittest.TestCase):
    """The tri-state contract of is_resident, against real /api/ps shapes.

    The session-start status line turns False into a user-visible "cold model"
    notice, so a wrong False is a false alarm about the exact hook that exists to
    remove false silence. None must stay reserved for "cannot tell".
    """

    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in
                      ("KB_EMBED_MODEL", "KB_EMBED_PROVIDER", "KB_EMBED_ENDPOINT")}
        os.environ["KB_EMBED_PROVIDER"] = "ollama"
        os.environ["KB_EMBED_MODEL"] = "testmodel"
        os.environ["KB_EMBED_ENDPOINT"] = "http://127.0.0.1:11434"
        self.calls = []

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _answer(self, payload=None, raise_with=None):
        """Stub urlopen; is_resident imports urllib.request inside the call."""
        import io
        import json as _json
        import urllib.request

        class Resp:
            def __init__(self, body):
                self._b = io.BytesIO(body)

            def read(self):
                return self._b.read()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake(req, timeout=None):
            self.calls.append((req.full_url, timeout))
            if raise_with is not None:
                raise raise_with
            return Resp(_json.dumps(payload).encode("utf-8"))

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake
        self.addCleanup(lambda: setattr(urllib.request, "urlopen", orig))

    def test_loaded_model_is_resident(self):
        self._answer({"models": [{"name": "testmodel", "size_vram": 4}]})
        self.assertIs(emb.is_resident(), True)
        self.assertTrue(self.calls[0][0].endswith("/api/ps"))

    def test_other_model_loaded_means_cold(self):
        self._answer({"models": [{"name": "somethingelse:9b"}]})
        self.assertIs(emb.is_resident(), False)

    def test_untagged_config_matches_the_latest_tag(self):
        """Ollama reports an untagged pull as "<name>:latest"."""
        self._answer({"models": [{"name": "testmodel:latest"}]})
        self.assertIs(emb.is_resident(), True)

    def test_a_differently_tagged_variant_is_not_the_same_model(self):
        """Embedding with "testmodel" would load :latest, not :4b."""
        self._answer({"models": [{"name": "testmodel:4b"}]})
        self.assertIs(emb.is_resident(), False)

    def test_nothing_loaded_means_cold(self):
        self._answer({"models": []})
        self.assertIs(emb.is_resident(), False)

    def test_missing_or_wrong_shaped_models_key_is_unknown(self):
        for payload in ({"models": None}, {}, [1, 2, 3], {"models": "nope"}):
            with self.subTest(payload=payload):
                self.calls.clear()
                self._answer(payload)
                self.assertIsNone(emb.is_resident())

    def test_junk_entries_do_not_crash(self):
        self._answer({"models": [None, "string", 7, {"name": None}, {"model": "testmodel"}]})
        self.assertIs(emb.is_resident(), True)

    def test_unreachable_ollama_is_unknown_not_cold(self):
        self._answer(raise_with=OSError("connection refused"))
        self.assertIsNone(emb.is_resident())

    def test_remote_endpoint_is_unknown_and_never_contacted(self):
        """A remote host cannot be bounded by the timeout: getaddrinfo ignores
        it and every resolved address gets it again. The hot path needs a
        ceiling, so a non-loopback endpoint answers None without a request."""
        os.environ["KB_EMBED_ENDPOINT"] = "http://ollama.example.com:11434"
        os.environ["KB_EMBED_ALLOW_REMOTE"] = "1"
        self.addCleanup(lambda: os.environ.pop("KB_EMBED_ALLOW_REMOTE", None))
        self._answer({"models": [{"name": "testmodel"}]})
        self.assertIsNone(emb.is_resident())
        self.assertEqual(self.calls, [])

    def test_other_provider_is_unknown(self):
        os.environ["KB_EMBED_PROVIDER"] = "openai"
        self._answer({"models": [{"name": "testmodel"}]})
        self.assertIsNone(emb.is_resident())
        self.assertEqual(self.calls, [])

    def test_timeout_is_passed_through(self):
        self._answer({"models": []})
        emb.is_resident(timeout=0.1)
        self.assertEqual(self.calls[0][1], 0.1)


if __name__ == "__main__":
    unittest.main()

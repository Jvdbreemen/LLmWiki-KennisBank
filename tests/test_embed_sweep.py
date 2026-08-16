"""embed-sweep's probe and its subprocesses measure the same backend.

TASK-190: ollama_embed POSTed to a hardcoded http://localhost:11434 while
the build/eval subprocesses resolved KB_EMBED_ENDPOINT / the vault config —
so with any non-default endpoint the latency probe measured a DIFFERENT
host than the quality runs, silently breaking the harness's comparability
claim. Both sides now resolve through _embeddings, and _env pins the
resolved endpoint into the subprocess environment by construction.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load():
    spec = importlib.util.spec_from_file_location(
        "embed_sweep_test", str(SCRIPTS / "embed-sweep.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class EndpointResolutionTest(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in
                       ("KB_EMBED_ENDPOINT", "KB_EMBED_PROVIDER",
                        "KB_EMBED_MODEL", "KENNISBANK_VAULT")}
        os.environ.pop("KB_EMBED_PROVIDER", None)
        os.environ.pop("KB_EMBED_MODEL", None)
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["KENNISBANK_VAULT"] = self._tmp.name
        self.m = _load()

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    def _fake_urlopen(self, seen):
        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        def fake(req, timeout=None):
            seen.append(req.full_url)
            return _Resp(json.dumps({"embedding": [0.1, 0.2]}).encode())
        return fake

    def test_the_probe_honors_the_configured_endpoint(self):
        os.environ["KB_EMBED_ENDPOINT"] = "http://127.0.0.1:29999"
        seen = []
        orig = self.m.urllib.request.urlopen
        self.m.urllib.request.urlopen = self._fake_urlopen(seen)
        try:
            ms, vec = self.m.ollama_embed("m", "x")
        finally:
            self.m.urllib.request.urlopen = orig
        self.assertEqual(seen, ["http://127.0.0.1:29999/api/embeddings"])
        self.assertEqual(vec, [0.1, 0.2])

    def test_the_default_stays_localhost(self):
        os.environ.pop("KB_EMBED_ENDPOINT", None)
        seen = []
        orig = self.m.urllib.request.urlopen
        self.m.urllib.request.urlopen = self._fake_urlopen(seen)
        try:
            self.m.ollama_embed("m", "x")
        finally:
            self.m.urllib.request.urlopen = orig
        self.assertEqual(seen, ["http://localhost:11434/api/embeddings"])

    def test_env_pins_the_resolved_endpoint_for_subprocesses(self):
        os.environ["KB_EMBED_ENDPOINT"] = "http://127.0.0.1:29999"
        e = self.m._env(Path(self._tmp.name), "m", {})
        self.assertEqual(e["KB_EMBED_ENDPOINT"], "http://127.0.0.1:29999")


if __name__ == "__main__":
    unittest.main()

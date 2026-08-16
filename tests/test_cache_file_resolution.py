"""The embeddings cache path follows the env at CALL time, not import time.

The module-level import below is DELIBERATE — it is the scenario under test
(TASK-196). Frozen at import, the cache path captured whatever
KENNISBANK_VAULT held during pytest collection; on a machine whose profile
exports the real vault, every later load_cache() parsed the real
multi-megabyte cache (measured: 2s -> 835s for two test files, purely on
import order). With cache_file() resolved per call, a setUp that points the
env at a temp vault is enough, whatever imported this module first.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _embeddings as emb  # noqa: E402  (deliberate: the freeze scenario)


class CacheFileResolutionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = self._tmp.name

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        self._tmp.cleanup()

    def test_the_cache_path_follows_the_env_set_after_import(self):
        self.assertEqual(emb.cache_file(),
                         Path(self._tmp.name) / ".claude" / "embeddings-cache.json")

    def test_load_and_save_use_the_env_of_the_moment(self):
        emb.save_cache({"k": {"hash": "h"}})
        on_disk = Path(self._tmp.name) / ".claude" / "embeddings-cache.json"
        self.assertTrue(on_disk.exists())
        self.assertEqual(emb.load_cache(), {"k": {"hash": "h"}})
        # switch vaults mid-process: the very next call must follow
        with tempfile.TemporaryDirectory() as other:
            os.environ["KENNISBANK_VAULT"] = other
            self.assertEqual(emb.load_cache(), {})
            emb.save_cache({"other": {}})
            self.assertTrue((Path(other) / ".claude" /
                             "embeddings-cache.json").exists())

    def test_the_warm_marker_lives_beside_the_cache(self):
        self.assertEqual(emb._warm_marker().parent, emb.cache_file().parent)

    def test_load_cache_returns_empty_on_a_corrupt_file(self):
        p = Path(self._tmp.name) / ".claude"
        p.mkdir(parents=True)
        (p / "embeddings-cache.json").write_text("not json", encoding="utf-8")
        self.assertEqual(emb.load_cache(), {})
        json_ok = json.dumps({"a": {}})
        (p / "embeddings-cache.json").write_text(json_ok, encoding="utf-8")
        self.assertEqual(emb.load_cache(), {"a": {}})


if __name__ == "__main__":
    unittest.main()

"""Tests for the L2 scene experiment driver (TASK-134).

The driver must not become a second scoring implementation: it delegates to
kb-eval's evaluate(). What it owns is the query-embedding cache and the flip
analysis, and both are tested here.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(filename):
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_").replace(".py", ""), str(SCRIPTS / filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class QueryCacheTest(unittest.TestCase):
    """Vectors are reused across arms, but never across embedding models."""

    def setUp(self):
        self.exp = _load("scene-experiment.py")
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "query-vectors.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_second_lookup_is_a_hit(self):
        calls = []

        def fake_embed(text, kind=None):
            calls.append(text)
            return [1.0, 0.0]

        cache = self.exp.QueryCache(self.path, "model-a")
        cache.get_or_embed("hello", fake_embed)
        cache.get_or_embed("hello", fake_embed)
        self.assertEqual(len(calls), 1)
        self.assertEqual((cache.hits, cache.misses), (1, 1))

    def test_cache_survives_a_reload(self):
        cache = self.exp.QueryCache(self.path, "model-a")
        cache.get_or_embed("hello", lambda t, kind=None: [1.0, 0.0])
        cache.save()
        reloaded = self.exp.QueryCache(self.path, "model-a")
        calls = []
        reloaded.get_or_embed("hello", lambda t, kind=None: calls.append(t))
        self.assertEqual(calls, [], "a warm cache must not re-embed")

    def test_a_different_model_invalidates_the_cache(self):
        """Mixing vector spaces would compare nonsense while looking healthy."""
        cache = self.exp.QueryCache(self.path, "model-a")
        cache.get_or_embed("hello", lambda t, kind=None: [1.0, 0.0])
        cache.save()
        other = self.exp.QueryCache(self.path, "model-b")
        calls = []

        def fake_embed(text, kind=None):
            calls.append(text)
            return [0.0, 1.0]

        other.get_or_embed("hello", fake_embed)
        self.assertEqual(calls, ["hello"])

    def test_a_corrupt_cache_file_is_ignored(self):
        self.path.write_text("{not json", encoding="utf-8")
        cache = self.exp.QueryCache(self.path, "model-a")
        self.assertEqual(cache.data, {})

    def test_a_failed_embedding_is_not_cached(self):
        cache = self.exp.QueryCache(self.path, "model-a")
        cache.get_or_embed("hello", lambda t, kind=None: None)
        self.assertEqual(cache.data, {})


class FlipsTest(unittest.TestCase):
    """Both directions, because an average hides displacement."""

    def setUp(self):
        self.exp = _load("scene-experiment.py")

    def _report(self, pairs):
        return {"results": [{"q": q, "expect": ["x"], "type": "feit", "rank": r,
                             "hits": []} for q, r in pairs]}

    def test_reports_gains_and_losses(self):
        base = self._report([("a", 2), ("b", 0)])
        arm = self._report([("a", 0), ("b", 3)])
        out = self.exp.flips(base, arm)
        self.assertEqual([x["q"] for x in out["gained"]], ["b"])
        self.assertEqual([x["q"] for x in out["lost"]], ["a"])

    def test_a_rank_change_within_the_top_five_is_not_a_flip(self):
        base = self._report([("a", 1)])
        arm = self._report([("a", 4)])
        out = self.exp.flips(base, arm)
        self.assertEqual(out, {"gained": [], "lost": []})

    def test_a_rank_beyond_five_counts_as_a_miss(self):
        base = self._report([("a", 3)])
        arm = self._report([("a", 7)])
        out = self.exp.flips(base, arm)
        self.assertEqual([x["q"] for x in out["lost"]], ["a"])

    def test_questions_absent_from_the_baseline_are_skipped(self):
        base = self._report([("a", 1)])
        arm = self._report([("a", 1), ("new", 1)])
        out = self.exp.flips(base, arm)
        self.assertEqual(out, {"gained": [], "lost": []})


class HitsFnTest(unittest.TestCase):
    """The driver must call the production recall route, prior included."""

    def setUp(self):
        self.exp = _load("scene-experiment.py")

    def test_passes_the_prior_and_the_memory_floor(self):
        seen = {}

        class FakeRecall:
            MEMORY_MIN_COS = 0.45

            @staticmethod
            def recall_hits(qv, **kw):
                seen.update(kw)
                return [{"path": "/vault/09-memory/a.md"}]

        tmp = tempfile.TemporaryDirectory()
        try:
            cache = self.exp.QueryCache(Path(tmp.name) / "c.json", "m")
            fn = self.exp.build_hits_fn(FakeRecall, cache,
                                        lambda t, kind=None: [1.0, 0.0],
                                        {"floor": 0.35, "boost": 0.05})
            stems = fn("question", 5)
        finally:
            tmp.cleanup()
        self.assertEqual(stems, ["a"])
        self.assertEqual(seen["layers"], ("memory",))
        self.assertEqual(seen["min_cos"], 0.45)
        self.assertEqual(seen["scene_prior"], {"floor": 0.35, "boost": 0.05})

    def test_no_prior_passes_none(self):
        seen = {}

        class FakeRecall:
            MEMORY_MIN_COS = 0.45

            @staticmethod
            def recall_hits(qv, **kw):
                seen.update(kw)
                return []

        tmp = tempfile.TemporaryDirectory()
        try:
            cache = self.exp.QueryCache(Path(tmp.name) / "c.json", "m")
            fn = self.exp.build_hits_fn(FakeRecall, cache,
                                        lambda t, kind=None: [1.0, 0.0], None)
            fn("question", 5)
        finally:
            tmp.cleanup()
        self.assertIsNone(seen["scene_prior"])


if __name__ == "__main__":
    unittest.main()

"""Tests voor scripts/kb-eval.py - recall@k eval-harnas.

Pure-function tests: hits_fn geinjecteerd, geen model, geen index.
De pariteitstests (TASK-86) stubben kb-recall en bewijzen dat het harnas
dezelfde expand/min_cos doorgeeft als de productie-hook resolvet.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._loader import SCRIPTS_DIR, load_script


def _ev():
    return load_script("kb-eval.py")


class TestLatency(unittest.TestCase):
    """--latency: p50/p95 per hits_fn-aanroep, alleen op verzoek in het rapport."""

    def setUp(self):
        self.ev = _ev()
        self.entries = [{"q": "v1", "expect": ["a"]}]

    def _fn(self, q, k):
        return ["a"]

    def test_latency_block_present_when_requested(self):
        r = self.ev.evaluate(self.entries, self._fn, measure_latency=True)
        self.assertIn("latency_ms", r)
        self.assertIn("p50", r["latency_ms"])
        self.assertIn("p95", r["latency_ms"])
        self.assertGreaterEqual(r["latency_ms"]["p95"], r["latency_ms"]["p50"])

    def test_latency_block_absent_by_default(self):
        r = self.ev.evaluate(self.entries, self._fn)
        self.assertNotIn("latency_ms", r)


class TestProductionParity(unittest.TestCase):
    """TASK-86: het harnas moet de productieroute meten, niet een kale variant.

    Vóór de fix riep _live_hits_fn recall_hits aan ZONDER expand= en min_cos=,
    terwijl kb-retrieve die wel meegeeft. Deze tests vergrendelen de pariteit:
    de doorgegeven knoppen moeten exact zijn wat kb-retrieve.retrieve_params
    over dezelfde config resolvet (wiki) c.q. MEMORY_MIN_COS (memory).
    """

    def setUp(self):
        self.ev = _ev()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        vault = Path(self.tmp.name) / "vault"
        (vault / ".claude").mkdir(parents=True)
        self._env = patch.dict(os.environ, {"KENNISBANK_VAULT": str(vault)}, clear=False)
        self._env.start()
        self.addCleanup(self._env.stop)
        # KB_RETRIEVE_*-env zou de defaults overschrijven; schoon voor de test.
        for var in ("KB_RETRIEVE_TOP_N", "KB_RETRIEVE_THRESHOLD", "KB_RETRIEVE_EXPAND"):
            os.environ.pop(var, None)
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        import _embeddings as emb
        self.emb = emb
        self._orig_embed = emb.embed
        emb.embed = lambda text, timeout=20.0, kind="": [0.1, 0.2]
        self.addCleanup(lambda: setattr(self.emb, "embed", self._orig_embed))
        self.real_retrieve = load_script("kb-retrieve.py")

    def _fake_modules(self, calls, memory_min_cos=0.60):
        def recall_hits(qv, query_text="", k=3, layers=("wiki", "memory"),
                        expand=False, min_cos=0.0, scene_prior=None):
            calls.append({"layers": tuple(layers), "expand": expand,
                          "min_cos": min_cos, "k": k,
                          "scene_prior": scene_prior})
            return []
        fake_recall = types.SimpleNamespace(recall_hits=recall_hits,
                                            MEMORY_MIN_COS=memory_min_cos)

        def load(name):
            return fake_recall if name == "kb-recall.py" else self.real_retrieve
        return load

    def _expected_params(self):
        cfg = self.real_retrieve.load_embed_cfg(self.ev.vault_root)
        return self.real_retrieve.retrieve_params(cfg)

    def test_wiki_passes_production_expand_and_min_cos(self):
        calls = []
        with patch.object(self.ev, "_load_by_path", side_effect=self._fake_modules(calls)):
            hits_fn, err = self.ev._live_hits_fn(layers=("wiki",))
            self.assertIsNone(err)
            hits_fn("een vraag", 5)
        expected = self._expected_params()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["layers"], ("wiki",))
        self.assertEqual(calls[0]["expand"], expected["expand"])
        self.assertEqual(calls[0]["min_cos"], expected["min_cos"])

    def test_wiki_respects_config_threshold(self):
        vault = Path(os.environ["KENNISBANK_VAULT"])
        (vault / ".claude" / "kennisbank-embed.json").write_text(
            json.dumps({"retrieve_threshold": 0.72, "retrieve_expand": 0}),
            encoding="utf-8")
        calls = []
        with patch.object(self.ev, "_load_by_path", side_effect=self._fake_modules(calls)):
            hits_fn, _ = self.ev._live_hits_fn(layers=("wiki",))
            hits_fn("een vraag", 5)
        self.assertEqual(calls[0]["min_cos"], 0.72)
        self.assertFalse(calls[0]["expand"])

    def test_memory_floor_resolves_through_retrieve_params(self):
        """TASK-188 parity: eval resolves the memory floor via exactly the
        resolver de hook gebruikt (retrieve_params), niet via een module-
        attribuut dat de hook niet leest."""
        vault = Path(os.environ["KENNISBANK_VAULT"])
        (vault / ".claude" / "kennisbank-embed.json").write_text(
            json.dumps({"memory_threshold": 0.61}), encoding="utf-8")
        calls = []
        with patch.object(self.ev, "_load_by_path",
                          side_effect=self._fake_modules(calls)):
            hits_fn, _ = self.ev._live_hits_fn(layers=("memory",))
            hits_fn("een vraag", 5)
        self.assertEqual(calls[0]["layers"], ("memory",))
        self.assertEqual(calls[0]["min_cos"], 0.61)
        self.assertIsNone(calls[0]["scene_prior"])  # toggle default OFF
        # productie expandeert het memory-blok niet
        self.assertFalse(calls[0]["expand"])

    def test_cli_expand_override_wins(self):
        calls = []
        with patch.object(self.ev, "_load_by_path", side_effect=self._fake_modules(calls)):
            hits_fn, _ = self.ev._live_hits_fn(layers=("wiki",), expand=False)
            hits_fn("een vraag", 5)
        self.assertFalse(calls[0]["expand"])


class TestRank(unittest.TestCase):
    def setUp(self):
        self.ev = _ev()

    def test_first_position(self):
        self.assertEqual(self.ev.rank_of_first_expected(["a", "b"], ["a"]), 1)

    def test_later_position(self):
        self.assertEqual(self.ev.rank_of_first_expected(["x", "y", "a"], ["a"]), 3)

    def test_not_found_is_zero(self):
        self.assertEqual(self.ev.rank_of_first_expected(["x", "y"], ["a"]), 0)

    def test_any_of_expected_counts(self):
        self.assertEqual(self.ev.rank_of_first_expected(["x", "b"], ["a", "b"]), 2)

    def test_a_bare_stem_and_none_are_tolerated(self):
        """TASK-190: de experiment-sets geven soms één losse stem of None;
        de geünificeerde helper draagt gold_ranks oude tolerantie. Een kale
        string mag NOOIT tot losse tekens ontleden."""
        self.assertEqual(self.ev.rank_of_first_expected(["a", "b"], "b"), 2)
        self.assertEqual(self.ev.rank_of_first_expected(["a"], None), 0)
        self.assertEqual(self.ev.rank_of_first_expected(["a", "b"], "ab"), 0)


class TestEvaluate(unittest.TestCase):
    def setUp(self):
        self.ev = _ev()
        self.entries = [
            {"q": "v1", "expect": ["a"], "type": "keyword"},
            {"q": "v2", "expect": ["b"], "type": "paraphrase"},
            {"q": "v3", "expect": ["c"], "type": "paraphrase"},
        ]
        # v1: rang 1; v2: rang 4; v3: niet gevonden
        self.hits = {"v1": ["a", "x", "y", "z", "w"],
                     "v2": ["x", "y", "z", "b", "w"],
                     "v3": ["x", "y", "z", "w", "v"]}

    def _fn(self, q, k):
        return self.hits[q][:k]

    def test_recall_at_k(self):
        r = self.ev.evaluate(self.entries, self._fn)
        self.assertEqual(r["recall"]["@1"], round(1 / 3, 3))
        self.assertEqual(r["recall"]["@3"], round(1 / 3, 3))
        self.assertEqual(r["recall"]["@5"], round(2 / 3, 3))

    def test_mrr(self):
        r = self.ev.evaluate(self.entries, self._fn)
        self.assertEqual(r["mrr"], round((1.0 + 0.25 + 0.0) / 3, 3))

    def test_by_type_breakdown(self):
        r = self.ev.evaluate(self.entries, self._fn)
        self.assertEqual(r["by_type"]["keyword"]["n"], 1)
        self.assertEqual(r["by_type"]["keyword"]["@1"], 1.0)
        self.assertEqual(r["by_type"]["paraphrase"]["n"], 2)
        self.assertEqual(r["by_type"]["paraphrase"]["@5"], 0.5)

    def test_results_carry_rank_and_hits(self):
        r = self.ev.evaluate(self.entries, self._fn)
        self.assertEqual([x["rank"] for x in r["results"]], [1, 4, 0])


class TestLoadSet(unittest.TestCase):
    def setUp(self):
        self.ev = _ev()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _write(self, obj) -> Path:
        p = Path(self.tmp.name) / "set.json"
        p.write_text(json.dumps(obj), encoding="utf-8")
        return p

    def test_valid_set_loads(self):
        p = self._write([{"q": "v", "expect": ["a"]}])
        self.assertEqual(len(self.ev.load_set(p)), 1)

    def test_empty_list_rejected(self):
        with self.assertRaises(ValueError):
            self.ev.load_set(self._write([]))

    def test_missing_expect_rejected(self):
        with self.assertRaises(ValueError):
            self.ev.load_set(self._write([{"q": "v"}]))

    def test_expect_must_be_list(self):
        with self.assertRaises(ValueError):
            self.ev.load_set(self._write([{"q": "v", "expect": "a"}]))


class TestLayerWiring(unittest.TestCase):
    def setUp(self):
        self.ev = _ev()

    def test_memory_set_constant_defined(self):
        # de geheugen-set moet een eigen default-pad hebben, los van de wiki-set
        self.assertTrue(self.ev.MEMORY_SET.endswith("kb-memory-eval-set.json"))
        self.assertNotEqual(self.ev.DEFAULT_SET, self.ev.MEMORY_SET)

    def test_run_one_reports_load_error_without_model(self):
        # _run_one faalt-soft op een onbruikbare set VOOR het model geraadpleegd
        # wordt (faalt bij load_set, geen embedding nodig).
        name, res = self.ev._run_one(Path("bestaat-niet-xyz.json"), "wiki")
        self.assertIsInstance(res, str)
        self.assertIn("niet bruikbaar", res)

    def test_repo_example_memory_set_is_valid(self):
        # de meegeleverde voorbeeld-geheugenset moet de schema-validatie passeren
        root = Path(__file__).resolve().parent.parent
        example = root / "kb-memory-eval-set.example.json"
        if example.exists():
            entries = self.ev.load_set(example)
            self.assertTrue(all("memory" not in e for e in entries))  # geen laag-veld nodig
            self.assertGreater(len(entries), 0)


if __name__ == "__main__":
    unittest.main()

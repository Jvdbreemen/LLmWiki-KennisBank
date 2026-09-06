"""Exact source hydration must not depend on embeddings or ranking."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str, filename: str):
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceExactHydrationContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        source = self.vault / "01-raw" / "transcripts" / "one.md"
        source.parent.mkdir(parents=True)
        source.write_text("alpha exact evidence omega", encoding="utf-8")
        (self.vault / ".claude").mkdir()
        (self.vault / "kennisbank-settings.json").write_text(
            json.dumps({"source_explicit_recall": True}), encoding="utf-8")
        self.saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.addCleanup(self._restore)

    def _restore(self):
        if self.saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self.saved

    def test_reconstruct_hydrates_a_ref_without_model_or_index(self):
        source_ref = _load("source_ref_hydration", "_source_ref.py")
        ref = source_ref.make_source_ref(
            self.vault, "01-raw/transcripts/one.md", start=6, end=20,
            chunk_id="chunk-0", captured_at="2026-09-04T00:00:00Z")
        gateway = _load("source_gateway_hydration", "kb-source-recall.py")

        def forbidden_embed(_text):
            raise AssertionError("exact hydration must not call embeddings")

        result = gateway.run(
            {"mode": "reconstruct", "source_ref": ref},
            embed_fn=forbidden_embed, vault=self.vault)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["hits"][0]["passage"], "exact evidence")
        self.assertEqual(result["hits"][0]["retrieval_route"], "exact_ref")

    def test_public_fallback_mode_is_policy_disabled(self):
        gateway = _load("source_gateway_policy", "kb-source-recall.py")
        result = gateway.run(
            {"mode": "fallback", "prompt": "anything", "primary_hits": []},
            embed_fn=lambda _text: [1.0], vault=self.vault)
        self.assertEqual(result["status"], "policy_disabled")
        self.assertEqual(result["hits"], [])

    def test_verify_exposes_stale_state_without_cached_passage(self):
        source_ref = _load("source_ref_verify", "_source_ref.py")
        source = self.vault / "01-raw" / "transcripts" / "one.md"
        ref = source_ref.make_source_ref(
            self.vault, "01-raw/transcripts/one.md", start=6, end=20,
            chunk_id="chunk-0")
        source.write_text("alpha changed source omega", encoding="utf-8")
        gateway = _load("source_gateway_verify", "kb-source-recall.py")

        result = gateway.run(
            {"mode": "verify", "source_ref": ref},
            embed_fn=lambda _text: (_ for _ in ()).throw(
                AssertionError("verify must not call a model")),
            vault=self.vault)

        self.assertEqual(result["status"], "evidence_unavailable")
        self.assertEqual(result["hits"][0]["source_state"], "stale")
        self.assertNotIn("passage", result["hits"][0])

    def test_explicit_search_is_lexical_best_effort_with_exact_provenance(self):
        source_module = _load("source_lexical_search", "_source_recall.py")
        source = self.vault / "01-raw" / "transcripts" / "one.md"
        conn = source_module.connect(self.vault / ".claude" / "kb-source.db")
        try:
            source_module.ensure_schema(conn)
            text = source.read_text(encoding="utf-8")
            source_module.upsert_source(
                conn, source_path="01-raw/transcripts/one.md",
                source_hash=source_module.sha256_file(source),
                chunks=source_module.chunk_text(text), metadata={})
        finally:
            conn.close()
        gateway = _load("source_gateway_lexical", "kb-source-recall.py")

        result = gateway.run(
            {"mode": "explicit", "prompt": "exact evidence", "k": 3},
            embed_fn=lambda _text: (_ for _ in ()).throw(
                AssertionError("explicit FTS must not call a model")),
            vault=self.vault)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["hits"][0]["retrieval_route"], "lexical_fts")
        self.assertTrue(result["hits"][0]["best_effort"])
        self.assertTrue(result["hits"][0]["fresh"])
        self.assertRegex(
            result["hits"][0]["source_ref_id"], r"^sr_[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()

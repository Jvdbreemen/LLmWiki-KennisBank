"""Public v1 recall exposes only the evidence-supported explicit routes."""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExplicitRecallPolicyContractTest(unittest.TestCase):
    def test_settings_split_capabilities_and_remove_unsafe_legacy_switches(self):
        settings = importlib.import_module("_settings")
        expected = {
            "experience_capture": False,
            "experience_projection": False,
            "experience_explicit_recall": False,
            "source_explicit_recall": False,
        }
        self.assertEqual({key: settings.DEFAULTS.get(key) for key in expected}, expected)
        self.assertNotIn("source_recall", settings.DEFAULTS)
        self.assertNotIn("experience_recall", settings.DEFAULTS)

    def test_source_product_code_has_no_embedding_or_vector_path(self):
        source_module = (SCRIPTS / "_source_recall.py").read_text(encoding="utf-8")
        source_builder = (SCRIPTS / "build-source-index.py").read_text(encoding="utf-8")
        source_gateway = (SCRIPTS / "kb-source-recall.py").read_text(encoding="utf-8")
        joined = "\n".join((source_module, source_builder, source_gateway))
        for forbidden in ("vec_docs", "_embeddings", "embed_fn", "query_vector"):
            self.assertNotIn(forbidden, joined)

    def test_experience_failure_mode_is_policy_disabled_before_backend_access(self):
        gateway = _load("experience_gateway_policy", "kb-experience-recall.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = gateway.run(
                {"mode": "failure", "prompt": "warn me"},
                embed_fn=lambda _text: (_ for _ in ()).throw(
                    AssertionError("disabled mode touched backend")),
                vault=Path(tmp))
            self.assertEqual(result["status"], "policy_disabled")

    def test_mcp_source_tool_accepts_a_structured_source_ref(self):
        mcp = _load("kb_mcp_contract", "kb-mcp.py")
        signature = inspect.signature(mcp.source_recall_tool)
        self.assertIn("source_ref", signature.parameters)

    def test_experience_gateway_labels_lexical_fallback(self):
        gateway = (SCRIPTS / "kb-experience-recall.py").read_text(encoding="utf-8")
        self.assertIn("lexical_fallback", gateway)

    def test_legacy_true_values_do_not_enable_new_gateway_semantics(self):
        source = _load("source_gateway_legacy_policy", "kb-source-recall.py")
        experience = _load("experience_gateway_legacy_policy", "kb-experience-recall.py")
        previous = os.environ.get("KENNISBANK_VAULT")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kennisbank-settings.json").write_text(json.dumps({
                "source_recall": True,
                "experience_recall": True,
            }), encoding="utf-8")
            os.environ["KENNISBANK_VAULT"] = tmp
            try:
                self.assertEqual(source.run(
                    {"mode": "explicit", "prompt": "evidence"},
                    vault=root)["status"], "disabled")
                self.assertEqual(experience.run(
                    {"mode": "explicit", "prompt": "lesson"},
                    vault=root)["status"], "disabled")
            finally:
                if previous is None:
                    os.environ.pop("KENNISBANK_VAULT", None)
                else:
                    os.environ["KENNISBANK_VAULT"] = previous

    def test_normal_retrieve_has_no_new_gateway_dependency(self):
        hot_path = (SCRIPTS / "kb-retrieve.py").read_text(encoding="utf-8")
        self.assertNotIn("kb-source-recall", hot_path)
        self.assertNotIn("kb-experience-recall", hot_path)

    def test_public_command_docs_show_split_flags_and_disabled_modes(self):
        settings = (ROOT / "commands" / "kennisbank" / "settings.md").read_text(
            encoding="utf-8")
        source = (ROOT / "commands" / "kennisbank" / "source-recall.md").read_text(
            encoding="utf-8")
        experience = (
            ROOT / "commands" / "kennisbank" / "experience-recall.md").read_text(
            encoding="utf-8")
        for key in ("experience_capture", "experience_projection",
                    "experience_explicit_recall", "source_explicit_recall"):
            self.assertIn(key, settings)
        self.assertIn("policy_disabled", source)
        self.assertIn("policy_disabled", experience)


if __name__ == "__main__":
    unittest.main()

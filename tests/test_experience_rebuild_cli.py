"""The production rebuild CLI targets split stores and degrades to lexical."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load():
    spec = importlib.util.spec_from_file_location(
        "experience_rebuild_cli", SCRIPTS / "rebuild-experience.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExperienceRebuildCliTest(unittest.TestCase):
    def test_default_paths_are_split_and_embedding_outage_uses_lexical(self):
        module = _load()
        captured = {}

        class Builder:
            @staticmethod
            def rebuild_experience_projection(ledger, projection, **kwargs):
                captured.update({"ledger": Path(ledger), "projection": Path(projection),
                                 **kwargs})
                return {"status": "ok", "vector_status": "lexical_fallback"}

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(module, "_builder", return_value=Builder), \
                mock.patch.dict(sys.modules, {"_embeddings": None}):
            code = module.main(["--vault", tmp])

        self.assertEqual(code, 0)
        self.assertEqual(captured["ledger"].name, "kb-experience-ledger.db")
        self.assertEqual(captured["projection"].name, "kb-experience-index.db")
        self.assertIsNone(captured["embed_fn"])


if __name__ == "__main__":
    unittest.main()

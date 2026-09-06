"""Reference latency gates for the lexical source projection."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _source_recall as source  # noqa: E402


def _load_benchmark():
    spec = importlib.util.spec_from_file_location(
        "benchmark_source_recall", SCRIPTS / "benchmark-source-recall.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceRecallLatencyTest(unittest.TestCase):
    def test_warm_search_and_exact_hydration_stay_within_product_budgets(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            raw = vault / "05-bronnen" / "synthetic.md"
            raw.parent.mkdir(parents=True)
            (vault / ".claude").mkdir()
            text = "".join(
                f"needle evidence item {index:04d} with deterministic filler.\n"
                for index in range(1200))
            raw.write_text(text, encoding="utf-8")
            chunks = source.chunk_text(text, size=256, overlap=32)
            conn = source.connect(vault / ".claude" / "kb-source.db")
            source.ensure_schema(conn)
            source.upsert_source(
                conn, source_path="05-bronnen/synthetic.md",
                source_hash=source.sha256_file(raw), chunks=chunks)
            conn.close()

            result = _load_benchmark().benchmark(
                vault, "needle deterministic", iterations=40, k=5)

        self.assertEqual(result["status"], "ok")
        self.assertLessEqual(result["search"]["p95_ms"], 250.0, result)
        self.assertLessEqual(result["exact_hydration"]["p95_ms"], 50.0, result)


if __name__ == "__main__":
    unittest.main()

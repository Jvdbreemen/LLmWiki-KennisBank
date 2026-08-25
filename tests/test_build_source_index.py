"""Builder contracts for the disposable raw-source index."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_source_index", SCRIPTS / "build-source-index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_embed(text: str):
    lower = text.lower()
    return [float("timeout" in lower), float("sqlite" in lower),
            float("source" in lower), 0.25]


class SourceBuilderContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        for rel in ("01-raw/transcripts", "05-bronnen", "08-archive", ".claude"):
            (self.vault / rel).mkdir(parents=True, exist_ok=True)
        (self.vault / "01-raw/transcripts/a.md").write_text(
            "A bounded timeout fixed the child process.", encoding="utf-8")
        (self.vault / "05-bronnen/b.txt").write_text(
            "SQLite keeps source evidence local.", encoding="utf-8")
        (self.vault / "08-archive/ignored.bin").write_bytes(b"not text")
        self.saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.addCleanup(self._restore)

    def _restore(self):
        if self.saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self.saved

    def test_collect_uses_only_approved_roots_and_text_types(self):
        builder = _load_builder()
        paths = {p.relative_to(self.vault).as_posix() for p in builder.collect_sources(self.vault)}
        self.assertEqual(paths, {"01-raw/transcripts/a.md", "05-bronnen/b.txt"})

    def test_build_is_rebuildable_and_incremental(self):
        builder = _load_builder()
        first = builder.build_source_index(
            self.vault, rebuild=True, embed_fn=_fake_embed, embed_id="fake:4")
        second = builder.build_source_index(
            self.vault, rebuild=False, embed_fn=_fake_embed, embed_id="fake:4")
        self.assertEqual(first["sources"], 2)
        self.assertGreaterEqual(first["indexed_chunks"], 2)
        self.assertEqual(second["indexed_chunks"], 0)
        self.assertEqual(second["unchanged_sources"], 2)

    def test_failed_rebuild_keeps_the_previous_index(self):
        builder = _load_builder()
        builder.build_source_index(
            self.vault, rebuild=True, embed_fn=_fake_embed, embed_id="fake:4")
        db = self.vault / ".claude" / "kb-source.db"
        before = db.read_bytes()
        failed = builder.build_source_index(
            self.vault, rebuild=True, embed_fn=lambda _text: None, embed_id="fake:4")
        self.assertGreater(failed["failed_chunks"], 0)
        self.assertEqual(db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()


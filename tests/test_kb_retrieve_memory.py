"""Tests voor de additieve memory-injectie in kb-retrieve.py.

Twee testklassen:

1. KbRetrieveMemoryTest — subprocess-guard tests (geen Ollama nodig).
   Draait de hook als subprocess met stdin-JSON (echt hook-contract). Toetst
   de twee invarianten zonder embedmodel:
     a. memory_recall=false -> output bevat NOOIT een memory-blok (byte-identiteit
        met wiki-only: geen 'KennisBank-geheugen'-regel).
     b. Een triviale/korte prompt -> geen output (bestaand gedrag, ongewijzigd).

2. KbRetrieveMemoryBlockTest — unit tests voor _memory_block (MINOR 2).
   Laadt kb-retrieve.py via importlib en injecteert een stub hits_fn zodat de
   gehele formatting- en hits-flow toetsbaar is zonder Ollama of kb-index.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
HOOK = SCRIPTS_DIR / "kb-retrieve.py"


def _load_kb_retrieve():
    spec = importlib.util.spec_from_file_location("kb_retrieve", str(HOOK))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class KbRetrieveMemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-ret-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self.env = dict(os.environ)
        self.env["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, prompt: str, settings: dict | None = None) -> str:
        if settings is not None:
            (self.vault / "kennisbank-settings.json").write_text(
                json.dumps(settings), encoding="utf-8")
        p = subprocess.run([sys.executable, str(HOOK)],
                           input=json.dumps({"prompt": prompt}),
                           capture_output=True, text=True, env=self.env, timeout=60)
        return p.stdout

    def test_trivial_prompt_no_output(self):
        self.assertEqual(self._run("ok").strip(), "")

    def test_memory_recall_off_no_memory_block(self):
        # geen index, geen cache -> hoogstens niets; cruciaal: nooit een memory-blok
        out = self._run("Een wat langere vraag over hooks en retrieval in dit project",
                        settings={"memory_recall": False})
        self.assertNotIn("KennisBank-geheugen", out)

    def test_memory_recall_on_without_index_still_no_crash(self):
        # memory aan maar geen kb-index.db -> fail-soft, geen memory-blok, geen crash
        out = self._run("Een wat langere vraag over hooks en retrieval in dit project",
                        settings={"memory_recall": True})
        self.assertNotIn("KennisBank-geheugen", out)  # index ontbreekt -> geen hits


class KbRetrieveMemoryBlockTest(unittest.TestCase):
    """Unit tests voor _memory_block met injectable hits_fn (geen Ollama nodig).

    Bewijst dat de formatting-logica en de hits-flow correct zijn zonder een
    echt embedmodel of kb-index.db te gebruiken (MINOR 2).
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-ret-blk-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.mod = _load_kb_retrieve()

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_memory_block_with_hits_returns_formatted_block(self):
        """Stub-hits resulteren in een blok met KennisBank-geheugen en [[stem]]."""
        fake_hits = [{"path": "/x/foo.md", "title": "Foo", "created": "2026-06-01",
                      "score": 0.9, "snippet": "iets"}]
        result = self.mod._memory_block(
            [0.1, 0.2], "test prompt", {}, hits_fn=lambda *a, **k: fake_hits)
        self.assertIn("KennisBank-geheugen", result)
        self.assertIn("[[foo]]", result)

    def test_memory_block_with_no_hits_returns_empty_string(self):
        """Lege hits_fn -> leeg resultaat (geen kopregels, geen ruis)."""
        result = self.mod._memory_block(
            [0.1, 0.2], "test prompt", {}, hits_fn=lambda *a, **k: [])
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()

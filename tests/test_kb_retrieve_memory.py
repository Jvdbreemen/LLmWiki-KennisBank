"""Tests voor de additieve memory-injectie in kb-retrieve.py.

Draait de hook als subprocess met stdin-JSON (echt hook-contract). Geen Ollama:
we monkeypatchen niet het subprocess, dus we testen de TWEE invarianten die
zonder embedmodel toetsbaar zijn:
  1. memory_recall=false  -> output bevat NOOIT een memory-blok (byte-identiteit
     met wiki-only: hier specifiek: geen 'KennisBank-geheugen'-regel).
  2. Een triviale/korte prompt -> geen output (bestaand gedrag, ongewijzigd).
Het volledige happy-path (memory-hits in context) wordt via de lib getest
(test_kb_recall) omdat dat een embedmodel vergt.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
HOOK = SCRIPTS_DIR / "kb-retrieve.py"


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


if __name__ == "__main__":
    unittest.main()

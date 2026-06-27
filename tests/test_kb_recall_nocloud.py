"""No-cloud-borging voor het recall-pad.

Twee guards:

1. Statische broncode-scan (NoCloudTest.test_no_external_hosts_in_recall_path):
   Scant de RECALL-PAD bronbestanden — kb-recall.py en _kbindex.py — op
   verdachte externe URLs/hosts. Alleen localhost/127.0.0.1 (Ollama) is
   toegestaan. Let op: _embeddings.py wordt hier NIET gescand; dat bestand
   bevat opt-in cloud-provider-endpoints (openai, voyage) die legitiem zijn
   als de gebruiker ze bewust configureert.

2. Provider-default-test (NoCloudTest.test_default_provider_is_local):
   Bewijst dat de DEFAULT embedding-provider ollama is (lokaal, geen cloud).
   In een schone omgeving zonder KB_EMBED_* env-vars en zonder
   kennisbank-embed.json moet provider() "ollama" teruggeven.

Beide guards groeien mee met het no-cloud-principe (#4).
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

FILES = ["kb-recall.py", "_kbindex.py"]
# toegestaan: localhost / 127.0.0.1 (Ollama). verboden: elke andere http(s)-host.
URL_RE = re.compile(r"https?://([A-Za-z0-9.\-]+)")
ALLOWED = {"localhost", "127.0.0.1"}


class NoCloudTest(unittest.TestCase):
    def test_no_external_hosts_in_recall_path(self):
        for name in FILES:
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            for host in URL_RE.findall(text):
                self.assertIn(host, ALLOWED,
                              f"{name}: externe host '{host}' in recall-pad (schendt no-cloud #4)")

    def test_default_provider_is_local(self):
        """De default embedding-provider is ollama — lokaal, nooit een cloud-provider.

        Valideert dat in een schone omgeving (geen KB_EMBED_* vars, geen
        kennisbank-embed.json) provider() "ollama" teruggeeft. Robuuster dan
        alleen static scanning: bewijst het werkelijke runtime-gedrag.
        """
        import _embeddings

        tmp = tempfile.mkdtemp(prefix="kb-nocloud-prov-")
        try:
            (Path(tmp) / ".claude").mkdir()
            saved_vault = os.environ.get("KENNISBANK_VAULT")
            saved_prov = os.environ.pop("KB_EMBED_PROVIDER", None)
            os.environ["KENNISBANK_VAULT"] = tmp
            try:
                self.assertEqual(
                    _embeddings.provider(), "ollama",
                    "default embedding-provider moet 'ollama' zijn (no-cloud #4)",
                )
            finally:
                if saved_vault is not None:
                    os.environ["KENNISBANK_VAULT"] = saved_vault
                else:
                    os.environ.pop("KENNISBANK_VAULT", None)
                if saved_prov is not None:
                    os.environ["KB_EMBED_PROVIDER"] = saved_prov
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

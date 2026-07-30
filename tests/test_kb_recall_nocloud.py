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

# De modules die daadwerkelijk een socket openen. kb-recall.py en _kbindex.py
# stonden hier alleen; die bevatten SAMEN nul URL's, dus de lus hieronder heeft
# nooit een assert uitgevoerd -- de guard slaagde leeg. _embeddings.py hoort er
# juist bij: dat is de enige module die kb-retrieve op ELKE prompt aanroept.
FILES = ["kb-recall.py", "_kbindex.py", "_embeddings.py", "_llm.py"]
# toegestaan: localhost / 127.0.0.1 (Ollama). verboden: elke andere http(s)-host.
URL_RE = re.compile(r"https?://([A-Za-z0-9.\-]+)")
# Cloud-endpoints mogen in de bron staan zolang ze opt-in zijn EN een API-key
# vereisen; ze zijn hier benoemd zodat de uitzondering zichtbaar is in plaats
# van impliciet, en zodat een nieuwe host de test rood maakt.
ALLOWED = {"localhost", "127.0.0.1"}
OPT_IN_CLOUD = {"api.openai.com", "api.voyageai.com", "openrouter.ai"}


class NoCloudTest(unittest.TestCase):
    def test_scan_is_not_vacuous(self):
        """Een host-scan over bestanden zonder URL's bewijst niets.

        Deze meta-assertie bestaat omdat precies dat gebeurde: de scanlijst
        bevatte twee bestanden met nul URL's, dus test_no_external_hosts liep
        altijd groen zonder ooit iets te toetsen."""
        found = [h for name in FILES
                 for h in URL_RE.findall((SCRIPTS / name).read_text(encoding="utf-8"))]
        self.assertTrue(found, "no-cloud-scan vond geen enkele URL - de guard slaapt")

    def test_no_unexpected_external_hosts(self):
        for name in FILES:
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            for host in URL_RE.findall(text):
                self.assertIn(
                    host, ALLOWED | OPT_IN_CLOUD,
                    f"{name}: onbekende externe host '{host}' (schendt no-cloud #4)")

    def test_remote_endpoint_for_a_local_provider_is_refused(self):
        """Runtime, niet statisch: een configbestand mag ollama niet omleiden.

        De statische scan kan dit per definitie niet zien - het endpoint staat
        niet in de broncode maar in kennisbank-embed.json. Eén schrijfactie
        daarin stuurde elke prompt naar een willekeurige host, zonder API-key
        en zonder waarschuwing."""
        import _embeddings

        self.assertFalse(_embeddings.endpoint_allowed("ollama", "http://198.51.100.9:11434"))
        self.assertTrue(_embeddings.endpoint_allowed("ollama", "http://127.0.0.1:11434"))
        self.assertTrue(_embeddings.endpoint_allowed("ollama", "http://localhost:11434"))

    def test_hostname_spoofs_do_not_pass_as_local(self):
        import _embeddings

        for spoof in ("http://localhost.evil.com/x",
                      "http://evil.com/?h=127.0.0.1",
                      "http://127.0.0.1.evil.com"):
            self.assertFalse(_embeddings.is_local_endpoint(spoof), spoof)

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

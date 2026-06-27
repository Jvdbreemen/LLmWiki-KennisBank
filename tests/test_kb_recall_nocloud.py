"""No-cloud-borging voor het recall-pad: kb-recall + de kb-retrieve-helpers
mogen alleen localhost (Ollama) en lokale SQLite raken — nooit een externe host.

We scannen de broncode statisch op verdachte externe URLs/hosts. Dit is een
goedkope, deterministische guard die meegroeit met het no-cloud-principe (#4).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
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


if __name__ == "__main__":
    unittest.main()

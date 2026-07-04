"""Tests voor kb-mcp.capture_tool + de instructions-nudge (TASK-22).

Ollama-vrij: capture_tool schrijft via _memory.write() naar een tmp-vault en
raakt geen model. Bewijst governance-conformiteit: een capture landt als
status=unverified, evidence_basis=agent (mens/sweep promoot later)."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load(mod_name, filename):
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(mod_name, str(SCRIPTS_DIR / filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CaptureToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-cap-"))
        (self.tmp / ".claude").mkdir(parents=True, exist_ok=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        self.mcp = _load("kb_mcp", "kb-mcp.py")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _memory_files(self):
        return list((self.tmp / "09-memory").rglob("*.md"))

    def test_capture_writes_unverified_agent_memory(self):
        out = self.mcp.capture_tool("Test titel", "Een herbruikbaar feit.",
                                    memory_type="feit", importance=4)
        self.assertIn("Vastgelegd", out)
        files = self._memory_files()
        self.assertEqual(len(files), 1)
        text = files[0].read_text(encoding="utf-8")
        self.assertIn("status: unverified", text)
        self.assertIn("evidence_basis: agent", text)
        self.assertIn("importance: 4", text)
        self.assertIn("Een herbruikbaar feit.", text)

    def test_empty_title_or_body_writes_nothing(self):
        self.assertIn("vereist", self.mcp.capture_tool("", "body"))
        self.assertIn("vereist", self.mcp.capture_tool("titel", "   "))
        self.assertEqual(self._memory_files(), [])

    def test_capture_failsoft_on_bad_memory_type(self):
        # coerce_memory_type normaliseert onbekende types; nooit een crash/traceback
        out = self.mcp.capture_tool("Titel", "Body", memory_type="onzin")
        self.assertNotIn("Traceback", out)
        # er is óf netjes geschreven, óf een nette foutmelding -- geen exception
        self.assertTrue(out)

    def test_instructions_text_mentions_recall_and_capture(self):
        self.assertIn("recall", self.mcp.INSTRUCTIONS_TEXT)
        self.assertIn("capture", self.mcp.INSTRUCTIONS_TEXT)
        self.assertIn("lokaal", self.mcp.INSTRUCTIONS_TEXT.lower())


if __name__ == "__main__":
    unittest.main()

"""Three clients write three transcript formats; capture must read all three.

`transcript_text()` understood Claude Code's shape only. Measured on the live
archive: it returned NOTHING for 39 of 299 transcripts, 94 MB of session content,
including single Codex sessions of 21 and 26 MB. Nothing downstream reports that
— an unreadable transcript is swept, marked in the watermark, and produces zero
memories, which is indistinguishable from a session in which nothing happened.

The formats differ structurally, so a shape check is the guard: a client that
changes its layout must fail here rather than silently stop being captured.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _sweepstate as ss  # noqa: E402


def _write(tmp: Path, name: str, records: list) -> Path:
    p = tmp / name
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return p


class TranscriptFormatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-transcripts-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_claude_code_shape(self):
        p = _write(self.tmp, "claude.jsonl", [
            {"type": "summary", "summary": "geen bericht, moet worden overgeslagen"},
            {"message": {"role": "user", "content": [{"type": "text", "text": "de vraag"}]}},
            {"message": {"role": "assistant", "content": [{"type": "text", "text": "het antwoord"}]}},
            {"message": {"role": "system", "content": [{"type": "text", "text": "systeemruis"}]}},
        ])
        text = ss.transcript_text(p)
        self.assertIn("user: de vraag", text)
        self.assertIn("assistant: het antwoord", text)
        self.assertNotIn("systeemruis", text)

    def test_codex_shape(self):
        """Codex nests the conversation under payload and surrounds it with tools."""
        p = _write(self.tmp, "codex.jsonl", [
            {"timestamp": "t", "type": "session_meta", "payload": {"session_id": "x"}},
            {"timestamp": "t", "type": "response_item",
             "payload": {"type": "message", "role": "developer",
                         "content": [{"type": "input_text", "text": "AGENTS.md instructies"}]}},
            {"timestamp": "t", "type": "response_item",
             "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "de codex-vraag"}]}},
            {"timestamp": "t", "type": "response_item",
             "payload": {"type": "message", "role": "assistant",
                         "content": [{"type": "output_text", "text": "het codex-antwoord"}]}},
            {"timestamp": "t", "type": "response_item",
             "payload": {"type": "reasoning", "content": [{"type": "text", "text": "gedachtegang"}]}},
            {"timestamp": "t", "type": "response_item",
             "payload": {"type": "function_call", "name": "shell"}},
            {"timestamp": "t", "type": "event_msg",
             "payload": {"type": "agent_message", "message": "het codex-antwoord"}},
        ])
        text = ss.transcript_text(p)
        self.assertIn("user: de codex-vraag", text)
        self.assertIn("assistant: het codex-antwoord", text)
        self.assertNotIn("gedachtegang", text)
        self.assertNotIn("AGENTS.md instructies", text,
                         "developer is het ingespoten instructieblok, geen gesprek")
        self.assertEqual(text.count("het codex-antwoord"), 1,
                         "event_msg herhaalt het antwoord en mag niet dubbeltellen")

    def test_copilot_shape(self):
        """Copilot logs hook events: message is a STRING, role sits beside it."""
        p = _write(self.tmp, "copilot.jsonl", [
            {"event": "sessionStart", "role": "session", "message": "sessionStart"},
            {"event": "userPromptSubmitted", "role": "user",
             "message": "userPromptSubmitted: de copilot-vraag"},
            {"event": "preToolUse", "role": "tool_use",
             "message": 'preToolUse skill: {"skill": "graphify"}'},
        ])
        text = ss.transcript_text(p)
        self.assertIn("user: de copilot-vraag", text)
        self.assertNotIn("userPromptSubmitted:", text,
                         "de eventnaam is metadata, geen kennis")
        self.assertNotIn("graphify", text)
        self.assertNotIn("sessionStart", text)

    def test_an_unreadable_transcript_is_empty_not_an_exception(self):
        """Capture is fail-soft by contract: a broken file must not stop a sweep."""
        p = self.tmp / "junk.jsonl"
        p.write_text("dit is geen json\n{kapot\n", encoding="utf-8")
        self.assertEqual(ss.transcript_text(p), "")
        self.assertEqual(ss.transcript_text(self.tmp / "bestaat-niet.jsonl"), "")

    def test_mixed_file_reads_every_shape(self):
        """One archive holds all three; the parser must not need to be told which."""
        p = _write(self.tmp, "mixed.jsonl", [
            {"message": {"role": "user", "content": [{"type": "text", "text": "claude-regel"}]}},
            {"timestamp": "t", "type": "response_item",
             "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "codex-regel"}]}},
            {"event": "userPromptSubmitted", "role": "user",
             "message": "userPromptSubmitted: copilot-regel"},
        ])
        text = ss.transcript_text(p)
        for expected in ("claude-regel", "codex-regel", "copilot-regel"):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()

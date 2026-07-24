# tests/test_strip_transcript.py
"""Tests voor de transcript-stripper (_transcript.py + strip-transcript.py CLI).

Bewijst dat het strippen van een Claude Code-transcript alleen user+assistant-
tekst overhoudt en thinking / tool_use / tool_result / isSidechain wegvalt.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script, SCRIPTS_DIR

_t = load_script("_transcript.py")

# Synthetisch transcript: één regel per turn/record.
RECORDS = [
    {"type": "user", "message": {"role": "user", "content": "ECHTE PROMPT van user"},
     "timestamp": "2026-07-24T09:00:00Z"},
    {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "GEHEIME THINKING"},
        # Non-ASCII (pijl + accent) om Windows cp1252-stdout-regressies te vangen.
        {"type": "text", "text": "ASSISTANT ANTWOORD → café"},
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls-geheim"}},
    ]}},
    {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "content": "TOOL OUTPUT ruis"},
    ]}},
    {"type": "assistant", "isSidechain": True, "message": {"role": "assistant", "content": [
        {"type": "text", "text": "SIDECHAIN RUIS"},
    ]}},
    {"type": "file-history-snapshot", "messageId": "x"},
]


def _write_jsonl(tmpdir: Path, name: str = "t.jsonl") -> Path:
    p = tmpdir / name
    p.write_text("\n".join(json.dumps(r) for r in RECORDS) + "\n", encoding="utf-8")
    return p


class ExtractTextParamTest(unittest.TestCase):
    def test_tool_result_included_by_default(self):
        # import-cc-history leunt op dit gedrag; default moet ongewijzigd blijven.
        self.assertEqual(
            _t.extract_text([{"type": "tool_result", "content": "X"}]), "X")

    def test_tool_result_excluded_when_flagged(self):
        self.assertEqual(
            _t.extract_text([{"type": "tool_result", "content": "X"}],
                            include_tool_result=False), "")

    def test_text_kept_thinking_and_tooluse_dropped(self):
        content = [
            {"type": "thinking", "thinking": "T"},
            {"type": "text", "text": "Y"},
            {"type": "tool_use", "name": "Bash", "input": {"command": "c"}},
        ]
        self.assertEqual(_t.extract_text(content, include_tool_result=False), "Y")

    def test_string_content_passthrough(self):
        self.assertEqual(_t.extract_text("plain prompt"), "plain prompt")


class StripToTextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-strip-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_keeps_only_user_and_assistant_text(self):
        p = _write_jsonl(self.tmp)
        out = _t.strip_to_text(p)
        self.assertIn("ECHTE PROMPT van user", out)
        self.assertIn("ASSISTANT ANTWOORD", out)
        # Ruis moet weg zijn:
        self.assertNotIn("GEHEIME THINKING", out)
        self.assertNotIn("TOOL OUTPUT ruis", out)
        self.assertNotIn("SIDECHAIN RUIS", out)
        self.assertNotIn("ls-geheim", out)

    def test_marks_roles(self):
        p = _write_jsonl(self.tmp)
        out = _t.strip_to_text(p)
        self.assertIn("USER", out)
        self.assertIn("ASSISTANT", out)

    def test_empty_turns_are_skipped(self):
        # Een user tool_result-only turn levert geen tekst en mag geen lege
        # USER-kop achterlaten.
        p = _write_jsonl(self.tmp)
        out = _t.strip_to_text(p)
        # Exact één USER-kop (de echte prompt), de tool_result-turn valt weg.
        self.assertEqual(out.count("### USER"), 1)
        self.assertEqual(out.count("### ASSISTANT"), 1)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-strip-cli-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "strip-transcript.py"), *args],
            capture_output=True, text=True, encoding="utf-8")

    def test_cli_path_to_stdout(self):
        p = _write_jsonl(self.tmp)
        res = self._run(str(p))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("ECHTE PROMPT van user", res.stdout)
        self.assertIn("ASSISTANT ANTWOORD", res.stdout)
        # Non-ASCII moet de stdout-encoding overleven (cp1252-regressie).
        self.assertIn("→ café", res.stdout)
        self.assertNotIn("TOOL OUTPUT ruis", res.stdout)

    def test_cli_missing_file_errors(self):
        res = self._run(str(self.tmp / "bestaat-niet.jsonl"))
        self.assertNotEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()

"""Tests for the Copilot rawlog importer (scripts/import-copilot.py, TASK-26.8).

Covers normal session, tool event, malformed lines, duplicate re-import,
active-log skip, and an end-to-end temporal-recall smoke (capture hook ->
importer -> build-activity-index -> query_events), which also closes TASK-26.6
DoD#1 (a synthetic hook event is findable as an activity source).
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IMPORTER = REPO_ROOT / "scripts" / "import-copilot.py"
CAPTURE = REPO_ROOT / "scripts" / "kb-copilot-capture.py"
ACTIVITY = REPO_ROOT / "scripts" / "_activity.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass in the module can resolve cls.__module__.
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


class CopilotImportTest(unittest.TestCase):
    def setUp(self):
        self.m = _load(IMPORTER, "import_copilot")
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-cimport-"))
        self.vault = self.tmp / "Kluis"
        (self.vault / ".claude" / "copilot-events").mkdir(parents=True)
        (self.vault / "01-raw" / "transcripts").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _staging(self, sid, events, mtime=None):
        p = self.vault / ".claude" / "copilot-events" / f"{sid}.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        if mtime is not None:
            os.utime(p, (mtime, mtime))
        return p

    def _transcript(self, sid):
        return self.vault / "01-raw" / "transcripts" / f"copilot-{sid}.jsonl"

    def _read(self, path):
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_imports_tool_and_prompt_events(self):
        old = time.time() - 10_000  # not active
        self._staging("sess1", [
            {"schema": "kb-copilot-event/1", "source": "copilot-hooks", "agent": "github-copilot-cli",
             "event": "userPromptSubmitted", "session_id": "sess1", "timestamp": "2026-07-10T10:00:00+02:00",
             "role": "user", "message": "userPromptSubmitted: fix TASK-99"},
            {"schema": "kb-copilot-event/1", "source": "copilot-hooks", "agent": "github-copilot-cli",
             "event": "preToolUse", "session_id": "sess1", "timestamp": "2026-07-10T10:01:00+02:00",
             "tool": "bash", "role": "tool_use", "message": "preToolUse bash: ls -la"},
        ], mtime=old)
        report = self.m.import_hooks(self.vault, active_window=120, include_active=False)
        self.assertEqual(report["events"], 2)
        self.assertEqual(report["sessions"], 1)
        tp = self._transcript("sess1")
        self.assertTrue(tp.is_file())
        evs = self._read(tp)
        self.assertEqual(len(evs), 2)
        self.assertTrue(all(e["agent"] == "github-copilot-cli" for e in evs))
        self.assertTrue(all("id" in e for e in evs))

    def test_dedupe_on_reimport(self):
        old = time.time() - 10_000
        self._staging("s2", [
            {"session_id": "s2", "event": "preToolUse", "timestamp": "2026-07-10T10:00:00+02:00",
             "role": "tool_use", "message": "preToolUse bash: ls"},
        ], mtime=old)
        r1 = self.m.import_hooks(self.vault, active_window=120, include_active=False)
        r2 = self.m.import_hooks(self.vault, active_window=120, include_active=False)
        self.assertEqual(r1["events"], 1)
        self.assertEqual(r2["events"], 0)
        self.assertEqual(r2["duplicates"], 1)
        self.assertEqual(len(self._read(self._transcript("s2"))), 1)

    def test_active_session_skipped(self):
        self._staging("live", [
            {"session_id": "live", "event": "preToolUse", "timestamp": "2026-07-10T10:00:00+02:00",
             "role": "tool_use", "message": "preToolUse bash: ls"},
        ], mtime=time.time())  # fresh -> active
        r = self.m.import_hooks(self.vault, active_window=120, include_active=False)
        self.assertEqual(r["skipped_active"], 1)
        self.assertEqual(r["events"], 0)
        self.assertFalse(self._transcript("live").exists())
        # with include_active it is imported
        r2 = self.m.import_hooks(self.vault, active_window=120, include_active=True)
        self.assertEqual(r2["events"], 1)

    def test_malformed_lines_ignored(self):
        p = self.vault / ".claude" / "copilot-events" / "s3.jsonl"
        p.write_text('{"session_id":"s3","event":"preToolUse","role":"tool_use","message":"ok bash"}\n'
                     "}{ not json\n"
                     "\n"
                     '{"also":"valid but no message"}\n', encoding="utf-8")
        os.utime(p, (time.time() - 10_000, time.time() - 10_000))
        r = self.m.import_hooks(self.vault, active_window=120, include_active=False)
        self.assertGreaterEqual(r["events"], 1)

    def test_end_to_end_capture_import_recall(self):
        activity = _load(ACTIVITY, "_activity")
        # 1) capture via the real hook script (subprocess, stdin payload)
        env = {**os.environ, "KENNISBANK_VAULT": str(self.vault)}
        payload = {"sessionId": "e2e", "cwd": "/w", "timestamp": "2026-07-10T09:30:00+02:00",
                   "toolName": "bash", "toolArgs": '{"command":"git commit -m TASK-77"}'}
        out = subprocess.run([sys.executable, str(CAPTURE), "--event", "preToolUse"],
                             input=json.dumps(payload).encode(), capture_output=True, env=env)
        self.assertEqual(out.returncode, 0)
        # make the staging file non-active
        sp = self.vault / ".claude" / "copilot-events" / "e2e.jsonl"
        os.utime(sp, (time.time() - 10_000, time.time() - 10_000))
        # 2) import to rawlog
        rep = self.m.import_hooks(self.vault, active_window=120, include_active=False)
        self.assertGreaterEqual(rep["events"], 1)
        # 3) build the activity index
        stats = activity.build_activity_index(self.vault, full=True, verbose=False)
        self.assertGreaterEqual(stats["copilot_events"], 1, "copilot events must be counted")
        # 4) temporal recall finds it with a source reference
        period = activity.parse_period("2026-07-10")
        items, warnings = activity.query_events(self.vault, period)
        copilot_items = [i for i in items if i.get("agent") == "github-copilot-cli"]
        self.assertTrue(copilot_items, f"recall found no copilot event (warnings={warnings})")
        ref = copilot_items[0]["source"]["ref"]
        self.assertIn("01-raw/transcripts/copilot-", ref)


if __name__ == "__main__":
    unittest.main()

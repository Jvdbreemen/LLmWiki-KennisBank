"""Vault orientation at session start (TASK-80).

Guards the three ways this could silently regress:
1. The hook path injects while the opt-in toggle is off.
2. The summary needs an embedding call or crashes without the databases.
3. The backlog scan counts closed tasks as open.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tests._loader import load_script  # noqa: E402


class OrientationBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        (self.vault / ".claude").mkdir()
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.mod = load_script("kb-orientation.py")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        self._tmp.cleanup()

    def _make_index(self):
        db = self.vault / ".claude" / "kb-index.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE docs (doc_id INTEGER PRIMARY KEY, path TEXT, "
                     "layer TEXT, status TEXT, hash TEXT, title TEXT, created TEXT)")
        rows = [("a.md", "wiki", "Artikel A", "2026-07-20"),
                ("b.md", "wiki", "Artikel B", "2026-07-25"),
                ("m.md", "memory", "Memory M", "2026-07-01")]
        for path, layer, title, created in rows:
            conn.execute("INSERT INTO docs (path, layer, title, created) "
                         "VALUES (?, ?, ?, ?)", (path, layer, title, created))
        conn.commit()
        conn.close()


class SummaryTest(OrientationBase):
    def test_counts_and_recent_from_index(self):
        self._make_index()
        text = self.mod.orientation(self.vault, self.vault)
        self.assertIn("1 memory", text)
        self.assertIn("2 wiki", text)
        # Most recent first.
        self.assertLess(text.index("Artikel B"), text.index("Artikel A"))

    def test_empty_vault_yields_empty_summary(self):
        self.assertEqual(self.mod.orientation(self.vault, self.vault), "")

    def test_backlog_counts_only_open_tasks(self):
        tasks = self.vault / "backlog" / "tasks"
        tasks.mkdir(parents=True)
        for name, status in (("task-1 - a.md", "To Do"),
                             ("task-2 - b.md", "In Progress"),
                             ("task-3 - c.md", "Done")):
            (tasks / name).write_text(f"---\nid: x\nstatus: {status}\n---\n",
                                      encoding="utf-8")
        (line,) = self.mod.backlog_lines(self.vault)
        self.assertIn("1 in progress", line)
        self.assertIn("1 to do", line)


class HookGatingTest(OrientationBase):
    def _run_hook(self, capsys_buffer=None):
        import io
        import contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.mod.main(["--hook"])
        return out.getvalue()

    def test_hook_silent_when_toggle_off(self):
        self._make_index()
        self.assertEqual(self._run_hook(), "")

    def test_hook_emits_context_when_toggle_on(self):
        self._make_index()
        (self.vault / "kennisbank-settings.json").write_text(
            json.dumps({"orientation": True}), encoding="utf-8")
        payload = json.loads(self._run_hook())
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("2 wiki", ctx)

    def test_manifest_and_coordinator_carry_the_job(self):
        source = (SCRIPTS / "kb-session-start.py").read_text(encoding="utf-8")
        self.assertIn('Job("kb-orientation.py", ("--hook",)', source)
        import _settings
        self.assertIs(_settings.DEFAULTS.get("orientation"), False)


if __name__ == "__main__":
    unittest.main()

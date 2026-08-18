"""TASK-201: one shared current_focus block, so three clients stop feeling
like three systems.

Adopted from the Eaves review with its scoping inverted: Eaves keeps focus
blocks per agent because its agents are different personas; KennisBank has one
subject, so the block is shared. The discipline these tests enforce is the
scope limit the task names as the risk: this is a transient working-state
block, not a second memory layer. No retrieval, no index entry, no rank
factor, no history.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script  # noqa: E402


class FocusWriteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-focus-"))
        self.vault = self.tmp / "vault"
        (self.vault / "01-raw" / "sessies").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        import _focus
        import _llm
        self.focus, self._llm = _focus, _llm
        self._orig = _llm.generate

    def tearDown(self):
        self._llm.generate = self._orig
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _log(self, name, body="## Doel\nIets bouwen.\n## Vervolgacties\n- [ ] afmaken\n",
             days_ago=0):
        from datetime import date, timedelta
        d = (date.today() - timedelta(days=days_ago)).isoformat()
        p = self.vault / "01-raw" / "sessies" / f"raw-sessie-{d}-{name}.md"
        p.write_text(f"---\ntitle: {name}\ntype: raw\ncreated: {d}\n---\n\n{body}",
                     encoding="utf-8")
        return p

    def test_writes_one_capped_file_wholesale(self):
        """AC#1+#3: one file, hard cap, replaced not appended."""
        self._log("werk")
        self._llm.generate = lambda *a, **k: "Bezig met X. Volgende stap: Y. " * 200
        self.focus.update_focus()
        out = self.focus.focus_path().read_text(encoding="utf-8")
        self.assertLessEqual(len(out), self.focus.FOCUS_MAX_CHARS)
        # tweede run met andere inhoud VERVANGT
        self._llm.generate = lambda *a, **k: "Nu iets anders."
        self.focus.update_focus()
        out2 = self.focus.focus_path().read_text(encoding="utf-8")
        self.assertEqual(out2.strip(), "Nu iets anders.")
        self.assertNotIn("Bezig met X", out2)

    def test_no_recent_sessions_means_an_empty_block(self):
        """AC#4 write side: nothing active -> empty file, and the model is
        not even consulted (nothing to summarise, principle #4)."""
        self._log("oud", days_ago=30)
        called = []
        self._llm.generate = lambda *a, **k: called.append(1) or "iets"
        self.focus.update_focus()
        self.assertEqual(self.focus.read_focus(), "")
        self.assertEqual(called, [], "model consulted with nothing to summarise")

    def test_a_dead_model_keeps_the_previous_block(self):
        """Fail-soft: an outage may not erase working state."""
        self._log("werk")
        self._llm.generate = lambda *a, **k: "Actieve focus."
        self.focus.update_focus()
        self._llm.generate = lambda *a, **k: ""
        self.focus.update_focus()
        self.assertEqual(self.focus.read_focus().strip(), "Actieve focus.")

    def test_refusal_text_is_not_written(self):
        self._log("werk")
        self._llm.generate = lambda *a, **k: "I cannot summarize this content."
        self.focus.update_focus()
        self.assertEqual(self.focus.read_focus(), "")

    def test_the_block_lives_outside_every_indexed_tree(self):
        """AC#5: not indexed, not retrievable. The file lives under .claude/,
        which no index builder scans -- pin the path so a refactor cannot
        silently move it into 02-wiki or 09-memory."""
        rel = self.focus.focus_path().relative_to(self.vault)
        self.assertEqual(rel.parts[0], ".claude")


class FocusNotifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-focusnotify-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = load_script("focus-notify.py")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.m.main()
        return buf.getvalue()

    def test_absent_and_empty_yield_no_output_at_all(self):
        """AC#4: silence when there is nothing active, in every client."""
        self.assertEqual(self._run(), "")
        (self.vault / ".claude" / "current-focus.md").write_text("  \n", encoding="utf-8")
        self.assertEqual(self._run(), "")

    def test_content_is_emitted_as_sessionstart_context(self):
        """AC#2: surfaced through the existing notification payload."""
        (self.vault / ".claude" / "current-focus.md").write_text(
            "Bezig met de reranker-meting.", encoding="utf-8")
        out = self._run()
        data = json.loads(out)
        ctx = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Bezig met de reranker-meting.", ctx)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertTrue(data["suppressOutput"])


class FocusWiringTest(unittest.TestCase):
    def test_focus_notify_is_a_notification_job(self):
        """AC#2: in NOTIFICATIONS, so TASK-202's per-client gate delivers it
        to every client, not only the first."""
        m = load_script("kb-session-start.py")
        self.assertIn("focus-notify.py", {j.script for j in m.NOTIFICATIONS})

    def test_sweep_calls_update_focus_off_the_hot_path(self):
        """AC#1: written by the sweep. Grep-proof the call site; the sweep is
        the existing off-hot-path vehicle."""
        src = (SCRIPTS / "memory-sweep.py").read_text(encoding="utf-8")
        self.assertIn("_focus", src)
        self.assertIn("update_focus", src)

    def test_no_rank_factor_and_no_index_entry(self):
        """AC#5 grep-proof: the scope-discipline line in the task. If _rank or
        an index builder ever names the focus block, it has become a second
        memory layer and this design is the wrong home for it."""
        for f in ("_rank.py", "build-kb-index.py", "kb-recall.py", "kb-retrieve.py"):
            src = (SCRIPTS / f).read_text(encoding="utf-8")
            self.assertNotIn("current-focus", src, f"{f} references the focus block")
            self.assertNotIn("_focus", src.replace("_focus_", ""), f"{f} imports _focus")


if __name__ == "__main__":
    unittest.main()

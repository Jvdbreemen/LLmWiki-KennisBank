import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("register_hooks", SCRIPTS / "register-hooks.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class RegisterHooksTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-rh-"))
        self.settings = self.tmp / "settings.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_interpreter_per_platform(self):
        orig = os.name
        try:
            os.name = "nt"
            self.assertEqual(self.m.interpreter(), "py -3")
            os.name = "posix"
            self.assertEqual(self.m.interpreter(), "python3")
        finally:
            os.name = orig

    def test_append_with_matcher(self):
        s = {}
        self.assertTrue(self.m.ensure_hook(s, "PreToolUse", "/v/.claude/scripts/kb-presearch.py",
                                           matcher="WebSearch|WebFetch"))
        group = s["hooks"]["PreToolUse"][0]
        self.assertEqual(group["matcher"], "WebSearch|WebFetch")
        self.assertIn("kb-presearch.py", group["hooks"][0]["command"])

    def test_selfheal_preserves_py3_interpreter(self):
        # bestaande hook met py -3 en een STALE pad -> pad ververst, prefix blijft py -3
        s = {"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": 'py -3 "/oud/.claude/scripts/kb-retrieve.py"'}]}]}}
        changed = self.m.ensure_hook(s, "SessionStart", "/nieuw/.claude/scripts/kb-retrieve.py")
        self.assertTrue(changed)
        cmd = s["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        self.assertEqual(cmd, 'py -3 "/nieuw/.claude/scripts/kb-retrieve.py"')

    def test_idempotent_no_change_second_time(self):
        s = {}
        self.m.ensure_hook(s, "SessionStart", "/v/.claude/scripts/build-kb-index.py")
        self.assertFalse(self.m.ensure_hook(s, "SessionStart", "/v/.claude/scripts/build-kb-index.py"))

    def test_register_manifest_full_set(self):
        s = {}
        self.m.register_manifest(s, "/v")
        cmds = [h["command"] for ev in s["hooks"].values() for g in ev for h in g["hooks"]]
        joined = " ".join(cmds)
        for need in ("build-kb-index.py", "sweep-launch.py", "memory-notify.py", "kb-presearch.py"):
            self.assertIn(need, joined)
        pre = s["hooks"]["PreToolUse"][0]
        self.assertEqual(pre.get("matcher"), "WebSearch|WebFetch")

    def test_corrupt_json_refused(self):
        self.settings.write_text("{not json", encoding="utf-8")
        rc = self.m.main([str(self.settings), "--manifest", "/v"])
        self.assertEqual(rc, 1)
        self.assertEqual(self.settings.read_text(encoding="utf-8"), "{not json")

    def test_selfheal_adds_missing_matcher_to_existing_matcherless_group(self):
        # F2: bestaande PreToolUse-entry ZONDER matcher -> re-run met matcher= moet
        # de matcher toevoegen (anders blijft kb-presearch op elk tool-call vuren).
        s = {"hooks": {"PreToolUse": [
            {"hooks": [{"type": "command",
                        "command": 'py -3 "/oud/.claude/scripts/kb-presearch.py"'}]}
        ]}}
        changed = self.m.ensure_hook(
            s, "PreToolUse", "/oud/.claude/scripts/kb-presearch.py",
            matcher="WebSearch|WebFetch",
        )
        # pad is niet veranderd maar matcher is toegevoegd -> changed=True
        self.assertTrue(changed, "ensure_hook must return True when matcher is added")
        group = s["hooks"]["PreToolUse"][0]
        self.assertEqual(group.get("matcher"), "WebSearch|WebFetch",
                         "ensure_hook must add the missing matcher to the existing group")

    def test_selfheal_preserves_python3_interpreter(self):
        # F8: bestaande hook met python3 en STALE pad -> pad ververst, prefix blijft python3
        s = {"hooks": {"SessionStart": [
            {"hooks": [{"type": "command",
                        "command": 'python3 "/oud/.claude/scripts/kb-retrieve.py"'}]}]}}
        changed = self.m.ensure_hook(s, "SessionStart", "/nieuw/.claude/scripts/kb-retrieve.py")
        self.assertTrue(changed)
        cmd = s["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        self.assertEqual(cmd, 'python3 "/nieuw/.claude/scripts/kb-retrieve.py"',
                         "python3 prefix must be preserved on self-heal, path must be updated")


if __name__ == "__main__":
    unittest.main()

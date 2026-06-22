"""Tests for scripts/register-hooks.py — idempotent settings.json hook merger.

setup.sh calls this to register the SessionStart (build-embed-index.py) and
UserPromptSubmit (kb-retrieve.py) hooks into the user's ~/.claude/settings.json.
These tests pin the contract: create-when-absent, preserve existing content,
idempotent on re-run, self-heal a moved vault path, and never clobber an
existing-but-unparseable settings file.

Pure stdlib, no network, no Claude Code: a temp settings file is the only I/O.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._loader import load_script


def _m():
    return load_script("register-hooks.py")


def _commands(settings: dict, event: str):
    """All hook command strings registered under `event`."""
    out = []
    for group in settings.get("hooks", {}).get(event, []):
        for h in group.get("hooks", []):
            cmd = h.get("command")
            if cmd is not None:
                out.append(cmd)
    return out


class BuildCommandTest(unittest.TestCase):
    def test_command_uses_python3_and_quotes_path(self):
        m = _m()
        cmd = m.build_command("/vault/.claude/scripts/build-embed-index.py")
        self.assertIn("python3", cmd)
        self.assertIn("build-embed-index.py", cmd)
        # Path is quoted so spaces in the vault path survive.
        self.assertIn('"/vault/.claude/scripts/build-embed-index.py"', cmd)


class EnsureHookTest(unittest.TestCase):
    def test_adds_hook_when_event_absent(self):
        m = _m()
        settings = {}
        changed = m.ensure_hook(settings, "SessionStart", "/v/.claude/scripts/build-embed-index.py")
        self.assertTrue(changed)
        self.assertEqual(len(_commands(settings, "SessionStart")), 1)
        self.assertIn("build-embed-index.py", _commands(settings, "SessionStart")[0])

    def test_idempotent_same_path_no_duplicate(self):
        m = _m()
        settings = {}
        path = "/v/.claude/scripts/build-embed-index.py"
        first = m.ensure_hook(settings, "SessionStart", path)
        second = m.ensure_hook(settings, "SessionStart", path)
        self.assertTrue(first)
        self.assertFalse(second)  # second run is a no-op
        self.assertEqual(len(_commands(settings, "SessionStart")), 1)

    def test_self_heals_stale_path(self):
        m = _m()
        # Pre-existing entry points at an old vault location.
        settings = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command",
                                "command": 'python3 "/old/.claude/scripts/build-embed-index.py"'}]}
                ]
            }
        }
        changed = m.ensure_hook(settings, "SessionStart", "/new/.claude/scripts/build-embed-index.py")
        self.assertTrue(changed)
        cmds = _commands(settings, "SessionStart")
        self.assertEqual(len(cmds), 1)            # updated in place, not duplicated
        self.assertIn("/new/", cmds[0])
        self.assertNotIn("/old/", cmds[0])

    def test_preserves_unrelated_hook_in_same_event(self):
        m = _m()
        settings = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "echo other-tool"}]}
                ]
            }
        }
        m.ensure_hook(settings, "SessionStart", "/v/.claude/scripts/build-embed-index.py")
        cmds = _commands(settings, "SessionStart")
        self.assertIn("echo other-tool", cmds)
        self.assertTrue(any("build-embed-index.py" in c for c in cmds))


class LoadSettingsTest(unittest.TestCase):
    def test_missing_file_returns_empty_dict(self):
        m = _m()
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(m.load_settings(Path(d) / "nope.json"), {})

    def test_empty_file_returns_empty_dict(self):
        m = _m()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text("   \n", encoding="utf-8")
            self.assertEqual(m.load_settings(p), {})

    def test_invalid_json_raises(self):
        m = _m()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                m.load_settings(p)


class MainTest(unittest.TestCase):
    def _run(self, argv):
        return _m().main(argv)

    def test_creates_settings_with_both_hooks(self):
        with tempfile.TemporaryDirectory() as d:
            settings = Path(d) / "settings.json"
            rc = self._run([
                str(settings),
                "SessionStart", "/v/.claude/scripts/build-embed-index.py",
                "UserPromptSubmit", "/v/.claude/scripts/kb-retrieve.py",
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(settings.is_file())
            data = json.loads(settings.read_text(encoding="utf-8"))
            self.assertTrue(any("build-embed-index.py" in c for c in _commands(data, "SessionStart")))
            self.assertTrue(any("kb-retrieve.py" in c for c in _commands(data, "UserPromptSubmit")))

    def test_preserves_existing_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as d:
            settings = Path(d) / "settings.json"
            settings.write_text(json.dumps({
                "permissions": {"allow": ["Bash(ls:*)"]},
                "env": {"FOO": "bar"},
            }), encoding="utf-8")
            self._run([
                str(settings),
                "SessionStart", "/v/.claude/scripts/build-embed-index.py",
                "UserPromptSubmit", "/v/.claude/scripts/kb-retrieve.py",
            ])
            data = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(data["permissions"], {"allow": ["Bash(ls:*)"]})
            self.assertEqual(data["env"], {"FOO": "bar"})
            self.assertTrue(any("build-embed-index.py" in c for c in _commands(data, "SessionStart")))

    def test_rerun_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            settings = Path(d) / "settings.json"
            argv = [
                str(settings),
                "SessionStart", "/v/.claude/scripts/build-embed-index.py",
                "UserPromptSubmit", "/v/.claude/scripts/kb-retrieve.py",
            ]
            self._run(argv)
            self._run(argv)
            data = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(len(_commands(data, "SessionStart")), 1)
            self.assertEqual(len(_commands(data, "UserPromptSubmit")), 1)

    def test_refuses_to_clobber_invalid_json(self):
        with tempfile.TemporaryDirectory() as d:
            settings = Path(d) / "settings.json"
            settings.write_text("{ broken", encoding="utf-8")
            rc = self._run([
                str(settings),
                "SessionStart", "/v/.claude/scripts/build-embed-index.py",
            ])
            self.assertNotEqual(rc, 0)
            # Original content is left untouched.
            self.assertEqual(settings.read_text(encoding="utf-8"), "{ broken")


if __name__ == "__main__":
    unittest.main()

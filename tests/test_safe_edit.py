"""Tests for scripts/safe-edit.py — the vault safe-edit engine.

Pure-function tests (no git) and CLI integration tests against a temp git repo.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from tests._loader import load_script  # noqa: E402


def _se():
    """Load (or reload) the safe-edit module."""
    return load_script("safe-edit.py")


# ---------------------------------------------------------------------------
# Pure unit tests — classify()
# ---------------------------------------------------------------------------

class TestClassify(unittest.TestCase):

    def setUp(self):
        self.se = _se()

    def test_identical_text_is_klein(self):
        text = "# Heading\n\nbody line\n"
        self.assertEqual(self.se.classify(text, text), "klein")

    def test_two_line_typo_fix_is_klein(self):
        old = "# Heading\n\nThis is a boddy line.\nAnother line.\n"
        new = "# Heading\n\nThis is a body line.\nAnother line.\n"
        self.assertEqual(self.se.classify(old, new), "klein")

    def test_removing_heading_is_groot(self):
        old = "# Title\n\n## Section\n\nbody\n"
        new = "# Title\n\nbody\n"
        self.assertEqual(self.se.classify(old, new), "groot")

    def test_adding_30_lines_is_groot(self):
        old = "# Title\n\nbody\n"
        new = old + "\n".join(f"new line {i}" for i in range(30)) + "\n"
        self.assertEqual(self.se.classify(old, new), "groot")

    def test_dropping_5_nonblank_body_lines_is_groot(self):
        lines = ["body line {}\n".format(i) for i in range(10)]
        old = "# Title\n\n" + "".join(lines)
        # Drop 5 lines from the middle
        new = "# Title\n\n" + "".join(lines[:5])
        self.assertEqual(self.se.classify(old, new), "groot")

    def test_empty_target_is_groot(self):
        old = "# Title\n\nbody\n"
        new = ""
        self.assertEqual(self.se.classify(old, new), "groot")

    def test_small_addition_within_limits_is_klein(self):
        old = "# Title\n\nbody\n"
        new = "# Title\n\nbody\nextra line\n"
        self.assertEqual(self.se.classify(old, new), "klein")


# ---------------------------------------------------------------------------
# Pure unit tests — unified()
# ---------------------------------------------------------------------------

class TestUnified(unittest.TestCase):

    def setUp(self):
        self.se = _se()

    def test_unified_returns_string(self):
        result = self.se.unified("old\n", "new\n", "test/file.md")
        self.assertIsInstance(result, str)

    def test_unified_contains_path(self):
        result = self.se.unified("old\n", "new\n", "test/file.md")
        self.assertIn("test/file.md", result)

    def test_unified_shows_changes(self):
        result = self.se.unified("line1\nline2\n", "line1\nchanged\n", "f.md")
        self.assertIn("-line2", result)
        self.assertIn("+changed", result)

    def test_unified_identical_is_empty(self):
        result = self.se.unified("same\n", "same\n", "f.md")
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# CLI integration tests — temp git repo
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):

    SCRIPT = REPO_ROOT / "scripts" / "safe-edit.py"

    def make_repo(self):
        d = Path(tempfile.mkdtemp(prefix="kb-se-"))
        subprocess.run(["git", "init", "-q", str(d)], check=True)
        subprocess.run(["git", "-C", str(d), "config", "user.email", "t@t.t"], check=True)
        subprocess.run(["git", "-C", str(d), "config", "user.name", "t"], check=True)
        art = d / "02-wiki" / "a.md"
        art.parent.mkdir(parents=True)
        art.write_text("# A\n\nbody line\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(d), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(d), "commit", "-qm", "seed"], check=True)
        return d, art

    def _run(self, d, art, new_content, extra_args=None):
        cmd = [sys.executable, str(self.SCRIPT), str(art), "--new", "-"]
        if extra_args:
            cmd.extend(extra_args)
        result = subprocess.run(
            cmd,
            input=new_content,
            text=True,
            capture_output=True,
        )
        return result

    def _commit_count(self, d):
        r = subprocess.run(
            ["git", "-C", str(d), "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return int(r.stdout.strip())

    # -- small edit applied without --confirm --

    def test_small_edit_applied_and_committed(self):
        d, art = self.make_repo()
        try:
            before_count = self._commit_count(d)
            new_content = "# A\n\nbody line fixed\n"
            result = self._run(d, art, new_content)
            self.assertEqual(result.returncode, 0, result.stderr)
            # File changed
            self.assertEqual(art.read_text(encoding="utf-8"), new_content)
            # Exactly one new commit
            self.assertEqual(self._commit_count(d), before_count + 1)
            # JSON report
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(report["action"], "applied")
            self.assertEqual(report["size"], "klein")
            self.assertIn("commit", report)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    # -- large edit without --confirm -> exit code 2, file unchanged --

    def test_large_edit_without_confirm_exits_2(self):
        d, art = self.make_repo()
        try:
            before_count = self._commit_count(d)
            original_text = art.read_text(encoding="utf-8")
            # Remove the heading -> groot
            new_content = "\nbody line\n"
            result = self._run(d, art, new_content)
            self.assertEqual(result.returncode, 2, result.stderr)
            # File unchanged
            self.assertEqual(art.read_text(encoding="utf-8"), original_text)
            # No new commit
            self.assertEqual(self._commit_count(d), before_count)
            # Report
            report_line = result.stdout.strip().splitlines()[-1]
            report = json.loads(report_line)
            self.assertEqual(report["action"], "needs-confirm")
            self.assertEqual(report["size"], "groot")
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    # -- large edit WITH --confirm -> applied --

    def test_large_edit_with_confirm_applied(self):
        d, art = self.make_repo()
        try:
            before_count = self._commit_count(d)
            new_content = "\nbody line\n"
            result = self._run(d, art, new_content, extra_args=["--confirm"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(art.read_text(encoding="utf-8"), new_content)
            self.assertEqual(self._commit_count(d), before_count + 1)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(report["action"], "applied")
            self.assertEqual(report["size"], "groot")
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    # -- dirty-tree guard --

    def test_dirty_tree_exits_3(self):
        d, art = self.make_repo()
        try:
            # Create an untracked/unrelated file
            unrelated = d / "b.md"
            unrelated.write_text("unrelated\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(d), "add", str(unrelated)], check=True)
            # staged but not committed = dirty
            new_content = "# A\n\nbody line fixed\n"
            result = self._run(d, art, new_content)
            self.assertEqual(result.returncode, 3, result.stderr)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    def test_dirty_tree_with_force_succeeds(self):
        d, art = self.make_repo()
        try:
            unrelated = d / "b.md"
            unrelated.write_text("unrelated\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(d), "add", str(unrelated)], check=True)
            new_content = "# A\n\nbody line fixed\n"
            result = self._run(d, art, new_content, extra_args=["--force"])
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    # -- Critical 1: dirty-tree substring-match bug --

    def test_dirty_tree_superstring_path_exits_3(self):
        """A dirty file whose path is a superstring of the target path must trigger exit 3.

        Target: 02-wiki/a.md  Dirty: 02-wiki/a.md.bak
        The old substring check wrongly treated a.md.bak as "the target itself"
        because str(target_rel) is contained in the dirty line string.
        Correct behaviour: a.md.bak != a.md -> dirty-tree guard fires -> exit 3.
        """
        d, art = self.make_repo()
        try:
            bak = d / "02-wiki" / "a.md.bak"
            bak.write_text("backup\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(d), "add", str(bak)], check=True)
            # staged but not committed -> dirty; no --force
            new_content = "# A\n\nbody line fixed\n"
            result = self._run(d, art, new_content)
            self.assertEqual(result.returncode, 3, result.stderr)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    def test_dirty_tree_superstring_path_with_force_succeeds(self):
        """--force must skip the dirty-tree guard even with the superstring path."""
        d, art = self.make_repo()
        try:
            bak = d / "02-wiki" / "a.md.bak"
            bak.write_text("backup\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(d), "add", str(bak)], check=True)
            new_content = "# A\n\nbody line fixed\n"
            result = self._run(d, art, new_content, extra_args=["--force"])
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    # -- Critical 2: no-op detection --

    def test_noop_edit_does_not_commit(self):
        """If proposed content is identical to current content, report no-op and don't commit."""
        d, art = self.make_repo()
        try:
            before_count = self._commit_count(d)
            original_text = art.read_text(encoding="utf-8")
            # Feed back the exact same content -> no-op
            result = self._run(d, art, original_text)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(report["action"], "no-op")
            # Commit count must not have changed
            self.assertEqual(self._commit_count(d), before_count)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    # -- KB_EDIT_MAX_LINES env var --

    def test_kb_edit_max_lines_env_lowers_threshold(self):
        """KB_EDIT_MAX_LINES=1 makes a 'klein' edit (few changed lines) classify as groot -> exit 2."""
        d, art = self.make_repo()
        try:
            original_text = art.read_text(encoding="utf-8")
            # Two lines added: diff_line_count = 2, which is klein at default (2 <= 20)
            # but groot at KB_EDIT_MAX_LINES=1 (2 > 1).
            new_content = "# A\n\nbody line\nextra line A\nextra line B\n"
            # Sanity: without env override, this is klein -> exit 0
            result_default = subprocess.run(
                [sys.executable, str(self.SCRIPT), str(art), "--new", "-"],
                input=new_content, text=True, capture_output=True,
            )
            self.assertEqual(result_default.returncode, 0, result_default.stderr)
            # Commit happened; reset the file for the next sub-test
            art.write_text(original_text, encoding="utf-8")
            subprocess.run(["git", "-C", str(d), "add", str(art)], check=True)
            subprocess.run(["git", "-C", str(d), "commit", "-qm", "reset"], check=True)

            # With KB_EDIT_MAX_LINES=1 the same edit exceeds the threshold -> exit 2
            env = {**os.environ, "KB_EDIT_MAX_LINES": "1"}
            result_strict = subprocess.run(
                [sys.executable, str(self.SCRIPT), str(art), "--new", "-"],
                input=new_content, text=True, capture_output=True, env=env,
            )
            self.assertEqual(result_strict.returncode, 2, result_strict.stderr)
            report_line = result_strict.stdout.strip().splitlines()[-1]
            report = json.loads(report_line)
            self.assertEqual(report["action"], "needs-confirm")
            self.assertEqual(report["size"], "groot")
            # File unchanged
            self.assertEqual(art.read_text(encoding="utf-8"), original_text)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    # -- new-file case --

    def test_new_file_small_is_applied(self):
        d, art = self.make_repo()
        try:
            before_count = self._commit_count(d)
            new_file = d / "02-wiki" / "new.md"
            content = "# New\n\nsmall body\n"
            cmd = [sys.executable, str(self.SCRIPT), str(new_file), "--new", "-"]
            result = subprocess.run(cmd, input=content, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(new_file.exists())
            self.assertEqual(self._commit_count(d), before_count + 1)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)


class TestCommitFailureRollback(unittest.TestCase):
    """De write gaat vooraf aan `git add`/`commit`.

    Faalt de commit (pre-commit hook, onschrijfbare index, lockfile), dan stond
    het artikel overschreven én staged achter zonder rollback -- en weigerde
    elke volgende aanroep zonder --force wegens vuile boom, terwijl
    commands/wiki.md en commands/reconcile.md --force verbieden. Eén mislukte
    commit blokkeerde daarmee het hele /wiki-schrijfpad.
    """

    # Hergebruik de harness van TestCLI zonder ervan te erven: erven zou al
    # zijn tests een tweede keer laten draaien.
    SCRIPT = TestCLI.SCRIPT
    make_repo = TestCLI.make_repo
    _run = TestCLI._run
    _commit_count = TestCLI._commit_count

    def _break_commit(self, d):
        hook = d / ".git" / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\necho 'hook says no'\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        return hook

    def test_failed_commit_restores_exact_bytes(self):
        d, art = self.make_repo()
        try:
            original = art.read_bytes()
            self._break_commit(d)
            result = self._run(d, art, "# A\n\nbody line fixed\n")
            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(report["action"], "error")
            self.assertEqual(report["reason"], "git-commit-failed")
            self.assertTrue(report["rolled_back"])
            # stdout van de hook moet in detail staan: stderr is hier leeg.
            self.assertIn("hook says no", report["detail"])
            self.assertEqual(art.read_bytes(), original,
                             "artikel niet byte-identiek teruggezet")
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    def test_failed_commit_removes_a_newly_created_file(self):
        d, art = self.make_repo()
        try:
            self._break_commit(d)
            new_file = d / "02-wiki" / "brand-new.md"
            cmd = [sys.executable, str(self.SCRIPT), str(new_file), "--new", "-"]
            result = subprocess.run(cmd, input="# New\n\nsmall body\n",
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            self.assertFalse(new_file.exists(),
                             "nieuw bestand bleef achter na mislukte commit")
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    def test_write_path_recovers_once_the_cause_is_gone(self):
        d, art = self.make_repo()
        try:
            hook = self._break_commit(d)
            first = self._run(d, art, "# A\n\nbody line fixed\n")
            self.assertEqual(first.returncode, 4, first.stdout + first.stderr)
            hook.unlink()
            before_count = self._commit_count(d)
            second = self._run(d, art, "# A\n\nbody line fixed\n")
            self.assertEqual(second.returncode, 0,
                             "vervolgbewerking geblokkeerd door achtergebleven "
                             "vuile boom: " + second.stdout + second.stderr)
            self.assertEqual(self._commit_count(d), before_count + 1)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)


class TestDirtyGuardPathHandling(unittest.TestCase):
    """De dirty-guard laat het doelbestand zelf vuil zijn -- behalve op Windows.

    Het doelpad werd met de OS-scheidingsteken opgebouwd (`02-wiki\\a.md`)
    terwijl `git status --porcelain` altijd forward slashes emit, dus de
    zelf-uitzondering matchte nooit en een boom waarin alleen het doel vuil is
    werd geweigerd met exit 3. Daarnaast quote git niet-ASCII paden tenzij
    core.quotepath=false, en ging de uitvoer door de platform-default codec.
    """

    SCRIPT = TestCLI.SCRIPT
    _run = TestCLI._run
    _commit_count = TestCLI._commit_count

    def make_repo(self, name="a.md"):
        d = Path(tempfile.mkdtemp(prefix="kb-se-path-"))
        subprocess.run(["git", "init", "-q", str(d)], check=True)
        subprocess.run(["git", "-C", str(d), "config", "user.email", "t@t.t"], check=True)
        subprocess.run(["git", "-C", str(d), "config", "user.name", "t"], check=True)
        art = d / "02-wiki" / name
        art.parent.mkdir(parents=True, exist_ok=True)
        art.write_text("# A\n\nbody line\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(d), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(d), "commit", "-qm", "seed"], check=True)
        return d, art

    def test_only_target_dirty_is_allowed(self):
        d, art = self.make_repo()
        try:
            art.write_text("# A\n\nbody line uncommitted\n", encoding="utf-8")
            result = self._run(d, art, "# A\n\nbody line fixed\n")
            self.assertEqual(result.returncode, 0,
                             "alleen het doelbestand is vuil, dat hoort te mogen: "
                             + result.stdout + result.stderr)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    def test_only_target_dirty_is_allowed_with_a_nonascii_name(self):
        d, art = self.make_repo(name="ideeen-met-trema-ë.md")
        try:
            art.write_text("# A\n\nbody line uncommitted\n", encoding="utf-8")
            result = self._run(d, art, "# A\n\nbody line fixed\n")
            self.assertEqual(result.returncode, 0,
                             result.stdout + result.stderr)
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)

    def test_dirty_nonascii_other_file_refuses_with_parseable_json(self):
        d, art = self.make_repo()
        try:
            # Cyrillisch: buiten cp1252, dus dit trof de encoding-fout.
            other = d / "02-wiki" / "заметка.md"
            other.write_text("nieuw en ongecommit\n", encoding="utf-8")
            result = self._run(d, art, "# A\n\nbody line fixed\n")
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertTrue(result.stdout.strip(),
                            "lege stdout: UnicodeEncodeError i.p.v. een rapport")
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(report["reason"], "dirty-tree")
            self.assertTrue(any("заметка" in line
                                for line in report["dirty"]),
                            f"niet-ASCII pad ontbreekt of is gequote: {report['dirty']}")
        finally:
            import shutil; shutil.rmtree(str(d), ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

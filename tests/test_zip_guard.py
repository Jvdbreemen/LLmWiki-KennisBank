"""Tests for the zip-slip / symlink guard in import-claudeai-export.py.

The guard validates every zip member before extraction: it must reject absolute
paths, '..' traversal, and symlink members, and accept a normal member. The
validation currently lives inline inside main(); these tests drive the real
main() end-to-end on tiny in-memory zips (built with stdlib zipfile/io) so the
actual shipped code path is exercised. A faithful replica of the inline rule is
also unit-tested as a focused, fast check of the validation logic itself.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from _loader import load_script


def _zip_bytes(members):
    """Build a zip in memory.

    members: list of (arcname, data, is_symlink). For a symlink member, `data`
    is the link target string and the member gets S_IFLNK in external_attr.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, data, is_symlink in members:
            info = zipfile.ZipInfo(arcname)
            if is_symlink:
                # 0o120000 == S_IFLNK; shifted into the upper 16 bits.
                info.external_attr = (0o120000 | 0o777) << 16
            else:
                info.external_attr = (0o100644) << 16
            zf.writestr(info, data)
    return buf.getvalue()


class TestZipGuardReplica(unittest.TestCase):
    """Focused unit test of the validation rule, mirroring main()'s inline logic."""

    @staticmethod
    def _validate(zf, tmpdir):
        """Faithful replica of the inline guard in import-claudeai-export.main().

        Raises ValueError on a disallowed member; returns None when all members
        are safe.
        """
        tmpdir_abs = os.path.abspath(tmpdir)
        for member in zf.namelist():
            info = zf.getinfo(member)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"refused: zip member is a symlink: {member!r}")
            member_path = os.path.abspath(os.path.join(tmpdir_abs, member))
            if not (
                member_path == tmpdir_abs
                or member_path.startswith(tmpdir_abs + os.sep)
            ):
                raise ValueError(f"refused: zip member escapes target dir: {member!r}")

    def _check(self, members):
        data = _zip_bytes(members)
        with tempfile.TemporaryDirectory() as td:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                self._validate(zf, td)

    def test_accepts_normal_member(self):
        # Should not raise.
        self._check([("conversations.json", "[]", False)])
        self._check([("sub/dir/file.json", "{}", False)])

    def test_rejects_absolute_path(self):
        with self.assertRaises(ValueError) as ctx:
            self._check([("/etc/passwd", "x", False)])
        self.assertIn("escapes target dir", str(ctx.exception))

    def test_rejects_parent_traversal(self):
        with self.assertRaises(ValueError) as ctx:
            self._check([("../../../etc/passwd", "x", False)])
        self.assertIn("escapes target dir", str(ctx.exception))

    def test_rejects_symlink_member(self):
        with self.assertRaises(ValueError) as ctx:
            self._check([("link", "/etc/passwd", True)])
        self.assertIn("symlink", str(ctx.exception))


class TestZipGuardEndToEnd(unittest.TestCase):
    """Drive the real import-claudeai-export.main() on built zips."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_script("import-claudeai-export.py")

    def _run(self, zip_bytes, vault):
        zip_path = Path(vault) / "export.zip"
        zip_path.write_bytes(zip_bytes)
        argv = ["--input", str(zip_path), "--vault", str(vault)]
        out, err = io.StringIO(), io.StringIO()
        old_argv = list(__import__("sys").argv)
        import sys as _sys
        _sys.argv = ["import-claudeai-export.py", *argv]
        try:
            with redirect_stdout(out), redirect_stderr(err):
                rc = self.mod.main()
        finally:
            _sys.argv = old_argv
        return rc, out.getvalue(), err.getvalue()

    def test_absolute_path_member_is_refused(self):
        with tempfile.TemporaryDirectory() as vault:
            z = _zip_bytes([("/etc/passwd", "x", False)])
            rc, _out, err = self._run(z, vault)
            self.assertEqual(rc, 2)
            self.assertIn("refused", err)
            self.assertIn("escapes target dir", err)

    def test_traversal_member_is_refused(self):
        with tempfile.TemporaryDirectory() as vault:
            z = _zip_bytes([("../../evil.json", "x", False)])
            rc, _out, err = self._run(z, vault)
            self.assertEqual(rc, 2)
            self.assertIn("refused", err)
            self.assertIn("escapes target dir", err)

    def test_symlink_member_is_refused(self):
        with tempfile.TemporaryDirectory() as vault:
            z = _zip_bytes([("link", "/etc/passwd", True)])
            rc, _out, err = self._run(z, vault)
            self.assertEqual(rc, 2)
            self.assertIn("refused", err)
            self.assertIn("symlink", err)

    def test_normal_member_is_accepted_and_imported(self):
        # A clean zip with a valid conversations.json must extract without any
        # 'refused' message and import one session successfully (rc 0).
        conv = [
            {
                "uuid": "abc12345-0000-0000-0000-000000000000",
                "name": "Test conversation",
                "created_at": "2026-01-02T03:04:05Z",
                "chat_messages": [
                    {"sender": "human", "text": "Hello there", "created_at": "2026-01-02T03:04:05Z"},
                    {"sender": "assistant", "text": "Hi back", "created_at": "2026-01-02T03:04:06Z"},
                ],
            }
        ]
        with tempfile.TemporaryDirectory() as vault:
            z = _zip_bytes([("conversations.json", json.dumps(conv), False)])
            rc, _out, err = self._run(z, vault)
            self.assertNotIn("refused", err)
            self.assertEqual(rc, 0)
            written = list((Path(vault) / "01-raw" / "sessies").glob("*.md"))
            self.assertEqual(len(written), 1)


if __name__ == "__main__":
    unittest.main()

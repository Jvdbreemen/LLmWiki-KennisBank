# tests/test_archive_transcript.py
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script

mod = load_script("archive-transcript.py")


def _make_transcript(dir_: Path, name: str, n_records: int) -> Path:
    p = dir_ / name
    lines = []
    for i in range(n_records):
        lines.append(json.dumps({
            "type": "user", "sessionId": "ABCDEF1234567890",
            "cwd": "/home/u/myproject",
            "timestamp": "2026-06-24T10:00:00Z",
            "message": {"role": "user", "content": f"turn {i} with enough text to pass the size floor"},
        }))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-arch-"))
        self.vault = self.tmp / "vault"
        self.src_dir = self.tmp / "src"
        self.src_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dest_path_shape(self):
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        hook = {"transcript_path": str(src), "session_id": "ABCDEF1234567890",
                "cwd": "/home/u/myproject"}
        dst = mod.dest_path(self.vault, hook, src)
        self.assertEqual(dst.parent, self.vault / "01-raw" / "transcripts")
        self.assertTrue(dst.name.endswith("-myproject-abcdef12.jsonl"), dst.name)

    def test_archive_copies_file(self):
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        hook = {"transcript_path": str(src), "session_id": "ABCDEF1234567890",
                "cwd": "/home/u/myproject"}
        res = mod.archive(hook, self.vault)
        self.assertEqual(res["status"], "archived")
        self.assertTrue(Path(res["dest"]).is_file())

    def test_archive_idempotent_same_session(self):
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        hook = {"transcript_path": str(src), "session_id": "ABCDEF1234567890",
                "cwd": "/home/u/myproject"}
        mod.archive(hook, self.vault)
        res2 = mod.archive(hook, self.vault)
        self.assertEqual(res2["status"], "skipped-uptodate")
        files = list((self.vault / "01-raw" / "transcripts").glob("*.jsonl"))
        self.assertEqual(len(files), 1)

    def test_archive_overwrites_when_source_grew(self):
        # Dekt de 'transcript groeit'-tak en de session-gekeyde dedup: een
        # gegroeide bron overschrijft DEZELFDE archieffile (1 bestand), ook al
        # zou de datum-prefix bij een dagovergang anders zijn.
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        hook = {"transcript_path": str(src), "session_id": "ABCDEF1234567890",
                "cwd": "/home/u/myproject"}
        mod.archive(hook, self.vault)
        _make_transcript(self.src_dir, "session.jsonl", 60)  # bron groeit
        res2 = mod.archive(hook, self.vault)
        self.assertEqual(res2["status"], "archived")
        files = list((self.vault / "01-raw" / "transcripts").glob("*.jsonl"))
        self.assertEqual(len(files), 1)

    def test_archive_skips_empty(self):
        src = self.src_dir / "tiny.jsonl"
        src.write_text("{}\n", encoding="utf-8")
        hook = {"transcript_path": str(src), "session_id": "X", "cwd": "/x"}
        res = mod.archive(hook, self.vault)
        self.assertEqual(res["status"], "skipped-empty")

    def test_archive_missing_source_is_error_not_raise(self):
        hook = {"transcript_path": str(self.src_dir / "nope.jsonl"),
                "session_id": "X", "cwd": "/x"}
        res = mod.archive(hook, self.vault)
        self.assertEqual(res["status"], "error")

    def test_main_exit_zero_on_garbage_stdin(self):
        import io
        old = sys.stdin
        sys.stdin = io.StringIO("not json at all")
        try:
            self.assertEqual(mod.main(), 0)
        finally:
            sys.stdin = old

    def _hook_stdin(self, src):
        return json.dumps({"transcript_path": str(src),
                           "session_id": "ABCDEF1234567890",
                           "cwd": "/home/u/myproject"})

    def _run_main(self, stdin_text):
        import io, os
        old_in, old_env = sys.stdin, os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        sys.stdin = io.StringIO(stdin_text)
        try:
            return mod.main()
        finally:
            sys.stdin = old_in
            if old_env is None:
                os.environ.pop("KENNISBANK_VAULT", None)
            else:
                os.environ["KENNISBANK_VAULT"] = old_env

    def test_main_skips_when_auto_archive_off(self):
        # Geen settings-bestand -> auto_archive default False -> niets archiveren.
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        rc = self._run_main(self._hook_stdin(src))
        self.assertEqual(rc, 0)
        tdir = self.vault / "01-raw" / "transcripts"
        self.assertEqual(list(tdir.glob("*.jsonl")) if tdir.exists() else [], [])

    def test_main_archives_when_auto_archive_on(self):
        (self.vault).mkdir(parents=True, exist_ok=True)
        (self.vault / "kennisbank-settings.json").write_text(
            '{"auto_archive": true}', encoding="utf-8")
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        rc = self._run_main(self._hook_stdin(src))
        self.assertEqual(rc, 0)
        files = list((self.vault / "01-raw" / "transcripts").glob("*.jsonl"))
        self.assertEqual(len(files), 1)


if __name__ == "__main__":
    unittest.main()

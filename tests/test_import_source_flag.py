# tests/test_import_source_flag.py
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script

mod = load_script("import-cc-history.py")


class CollectJsonlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-imp-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_flat_glob_finds_top_level_jsonl(self):
        (self.tmp / "a.jsonl").write_text("{}\n", encoding="utf-8")
        (self.tmp / "b.jsonl").write_text("{}\n", encoding="utf-8")
        found = mod.collect_jsonl(self.tmp, flat=True)
        self.assertEqual(len(found), 2)

    def test_nested_glob_finds_project_layout(self):
        proj = self.tmp / "project-x"
        proj.mkdir()
        (proj / "s.jsonl").write_text("{}\n", encoding="utf-8")
        found = mod.collect_jsonl(self.tmp, flat=False)
        self.assertEqual(len(found), 1)

    def test_flat_glob_ignores_nested(self):
        proj = self.tmp / "project-x"
        proj.mkdir()
        (proj / "s.jsonl").write_text("{}\n", encoding="utf-8")
        found = mod.collect_jsonl(self.tmp, flat=True)
        self.assertEqual(len(found), 0)


class SourceImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-imp2-"))
        self.archive = self.tmp / "transcripts"
        self.archive.mkdir(parents=True)
        self.vault = self.tmp / "vault"
        rec = json.dumps({
            "type": "user", "sessionId": "FEED0000",
            "cwd": "/home/u/proj", "timestamp": "2026-06-24T09:00:00Z",
            "message": {"role": "user", "content": "Hoe werkt de archiefhook precies?"},
        })
        (self.archive / "2026-06-24-proj-feed0000.jsonl").write_text(rec + "\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_source_flag_imports_flat_archive(self):
        old = sys.argv
        sys.argv = ["import-cc-history.py", "--source", str(self.archive),
                    "--vault", str(self.vault)]
        try:
            rc = mod.main()
        finally:
            sys.argv = old
        self.assertEqual(rc, 0)
        out = list((self.vault / "01-raw" / "sessies").glob("raw-sessie-*.md"))
        self.assertEqual(len(out), 1, out)


if __name__ == "__main__":
    unittest.main()

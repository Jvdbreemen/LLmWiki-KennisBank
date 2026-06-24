# tests/test_distill_notify.py
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script

mod = load_script("distill-notify.py")


class DistillNotifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-dn-"))
        self.vault = self.tmp / "vault"
        self.tdir = self.vault / "01-raw" / "transcripts"
        self.tdir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _add(self, name):
        (self.tdir / name).write_text("{}\n", encoding="utf-8")

    def test_pending_lists_unmarked(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self._add("2026-06-24-b-bbbb2222.jsonl")
        self.assertEqual(len(mod.pending(self.vault)), 2)

    def test_mark_marks_only_given(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self._add("2026-06-24-b-bbbb2222.jsonl")
        n = mod.mark(self.vault, ["2026-06-24-a-aaaa1111"])
        self.assertEqual(n, 1)
        self.assertEqual(mod.pending(self.vault), ["2026-06-24-b-bbbb2222"])

    def test_mark_is_append_not_overwrite(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self._add("2026-06-24-b-bbbb2222.jsonl")
        mod.mark(self.vault, ["2026-06-24-a-aaaa1111"])
        mod.mark(self.vault, ["2026-06-24-b-bbbb2222"])
        self.assertEqual(mod.pending(self.vault), [])

    def test_mark_dedups(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self.assertEqual(mod.mark(self.vault, ["2026-06-24-a-aaaa1111"]), 1)
        self.assertEqual(mod.mark(self.vault, ["2026-06-24-a-aaaa1111"]), 0)

    def test_new_file_after_mark_is_pending(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        mod.mark(self.vault, ["2026-06-24-a-aaaa1111"])
        self._add("2026-06-24-c-cccc3333.jsonl")
        self.assertEqual(len(mod.pending(self.vault)), 1)

    def _run_main(self, argv, stdin="{}"):
        """Roep main() aan met gepatchte argv/stdin/stdout en herstel ALLES,
        inclusief de KENNISBANK_VAULT-env (anders lekt die naar latere tests)."""
        import os
        out = io.StringIO()
        old_out, old_in, old_argv = sys.stdout, sys.stdin, sys.argv
        old_env = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        sys.stdout, sys.stdin, sys.argv = out, io.StringIO(stdin), argv
        try:
            rc = mod.main()
        finally:
            sys.stdout, sys.stdin, sys.argv = old_out, old_in, old_argv
            if old_env is None:
                os.environ.pop("KENNISBANK_VAULT", None)
            else:
                os.environ["KENNISBANK_VAULT"] = old_env
        return rc, out.getvalue()

    def test_main_notify_emits_context_when_pending(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        rc, out = self._run_main(["distill-notify.py"])
        self.assertEqual(rc, 0)
        # NB: deze JSON-vorm wordt geassert tegen de eigen impl, niet tegen een
        # extern SessionStart-contract. Kruis het echte hook-outputformaat een
        # keer met de docs voor productie (zie kb-retrieve.py voor het UserPromptSubmit-precedent).
        payload = json.loads(out)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("1", payload["hookSpecificOutput"]["additionalContext"])

    def test_main_notify_silent_when_none(self):
        rc, out = self._run_main(["distill-notify.py"])
        self.assertEqual(out.strip(), "")

    def test_main_list_pending_outputs_stems(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        rc, out = self._run_main(["distill-notify.py", "--list-pending"])
        self.assertEqual(out.strip(), "2026-06-24-a-aaaa1111")

    def test_main_mark_via_cli(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self._run_main(["distill-notify.py", "--mark", "2026-06-24-a-aaaa1111"])
        self.assertEqual(mod.pending(self.vault), [])


if __name__ == "__main__":
    unittest.main()

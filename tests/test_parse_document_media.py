from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

import _media_transcript  # noqa: E402
from _loader import load_script  # noqa: E402


class OfflineParserTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-offline-"))
        self.vault = self.tmp / "vault"
        self.vault.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_srt_keeps_timestamps_and_multiline_cues(self):
        source = self.tmp / "interview.srt"
        source.write_text(
            "1\n00:00:01,200 --> 00:00:03,400\nAlice: first line\ncontinued\n\n"
            "2\n00:01:23.400 --> 00:01:24.000\nBob: second\n",
            encoding="utf-8",
        )
        parsed = _media_transcript.parse_subtitle(source)[0]
        self.assertEqual(parsed.unit_count, 2)
        self.assertIn("[00:00:01.200] Alice: first line\ncontinued", parsed.text)
        self.assertIn("[00:01:23.400] Bob: second", parsed.text)

    def test_vtt_keeps_voice_labels_and_ignores_notes(self):
        source = self.tmp / "interview.vtt"
        source.write_text(
            "WEBVTT\n\nNOTE ignored\n\n"
            "cue-1\n00:01.000 --> 00:02.000 align:start\n"
            "<v Alice>Hello &amp; welcome</v>\n",
            encoding="utf-8",
        )
        parsed = _media_transcript.parse_subtitle(source)[0]
        self.assertIn("[00:00:01.000] Alice: Hello & welcome", parsed.text)

    def test_eml_headers_are_metadata_and_body_is_text(self):
        source = self.tmp / "mail.eml"
        message = EmailMessage()
        message["From"] = "Alice <alice@example.org>"
        message["To"] = "bob@example.org"
        message["Cc"] = "carol@example.org"
        message["Subject"] = "Interview follow-up"
        message["Date"] = "Tue, 25 Sep 2026 10:00:00 +0200"
        message["Message-ID"] = "<mail-1@example.org>"
        message.set_content("First line\n\nSecond line")
        source.write_bytes(message.as_bytes())
        parsed = _media_transcript.parse_mail(source)[0]
        self.assertEqual(parsed.metadata["from"], "Alice <alice@example.org>")
        self.assertEqual(parsed.metadata["cc"], "carol@example.org")
        self.assertIn("Second line", parsed.text)
        rendered = _media_transcript.render_offline_markdown(source, parsed)
        self.assertIn("from: ", rendered)
        self.assertIn("subject: Interview follow-up", rendered)
        self.assertIn("parse_engine: stdlib-email", rendered)

    def test_mbox_splits_messages_in_order(self):
        source = self.tmp / "archive.mbox"
        first = EmailMessage()
        first["From"] = "a@example.org"
        first["To"] = "b@example.org"
        first["Subject"] = "First"
        first["Message-ID"] = "<one@example.org>"
        first.set_content("One")
        second = EmailMessage()
        second["From"] = "c@example.org"
        second["To"] = "d@example.org"
        second["Subject"] = "Second"
        second["Message-ID"] = "<two@example.org>"
        second.set_content("Two")
        source.write_bytes(b"From a@example.org Mon Jan  1 00:00:00 2024\n"
                           + first.as_bytes() + b"\nFrom c@example.org Mon Jan  1 00:01:00 2024\n"
                           + second.as_bytes())
        parsed = _media_transcript.parse_mail(source)
        self.assertEqual([item.title for item in parsed], ["First", "Second"])
        self.assertEqual([item.message_index for item in parsed], [1, 2])
        self.assertNotIn("From a@example.org", parsed[0].text)

    def test_cli_writes_one_markdown_file_per_mbox_message(self):
        source = self.tmp / "archive.mbox"
        first = EmailMessage()
        first["From"] = "a@example.org"
        first["Subject"] = "First"
        first.set_content("One")
        second = EmailMessage()
        second["From"] = "b@example.org"
        second["Subject"] = "Second"
        second.set_content("Two")
        source.write_bytes(b"From a@example.org Mon Jan  1 00:00:00 2024\n"
                           + first.as_bytes() + b"\nFrom b@example.org Mon Jan  1 00:01:00 2024\n"
                           + second.as_bytes())
        module = load_script("parse-document.py")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = module.main([str(source), "--vault", str(self.vault), "--json"])
        summary = json.loads(output.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(summary["imported"], 2)
        self.assertEqual(len(summary["files"]), 2)
        for target in summary["files"]:
            text = Path(target).read_text(encoding="utf-8")
            self.assertIn("type: bron", text)
            self.assertIn("source: offline-parser", text)
        self.assertNotIn("From a@example.org", Path(summary["files"][0]).read_text(encoding="utf-8"))

    def test_mbox_dry_run_reports_all_targets_without_writing(self):
        source = self.tmp / "archive.mbox"
        message = EmailMessage()
        message["Subject"] = "One"
        message.set_content("One")
        source.write_bytes(b"From a@example.org Mon Jan  1 00:00:00 2024\n"
                           + message.as_bytes() + b"\nFrom b@example.org Mon Jan  1 00:01:00 2024\n"
                           + message.as_bytes())
        module = load_script("parse-document.py")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = module.main([str(source), "--vault", str(self.vault), "--dry-run", "--json"])
        summary = json.loads(output.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(summary["imported"], 2)
        self.assertEqual(len(list((self.vault / "05-bronnen" / "liteparse").glob("*.md"))), 0)

    def test_intake_routes_subtitles_and_mail_to_offline_parser(self):
        intake = load_script("intake-scan.py")
        self.assertEqual(intake.detect_type(Path("interview.srt")), "subtitle")
        self.assertEqual(intake.detect_type(Path("interview.vtt")), "subtitle")
        self.assertEqual(intake.detect_type(Path("message.eml")), "mail")
        self.assertEqual(intake.detect_type(Path("archive.mbox")), "mail")
        for name in ("interview.srt", "interview.vtt", "message.eml", "archive.mbox"):
            self.assertEqual(
                intake.suggested_action(intake.detect_type(Path(name)), Path(name)),
                "parse_with_offline_parser",
            )

    def test_command_documents_all_offline_formats(self):
        text = (Path(__file__).resolve().parent.parent / "commands" / "intake.md").read_text(
            encoding="utf-8")
        for suffix in (".srt", ".vtt", ".eml", ".mbox"):
            self.assertIn(suffix, text)

    def test_generated_source_link_passes_kb_lint(self):
        source = self.tmp / "mail.eml"
        message = EmailMessage()
        message["Subject"] = "Provenance"
        message.set_content("Evidence")
        source.write_bytes(message.as_bytes())
        parsed = _media_transcript.parse_mail(source)[0]
        target = _media_transcript.offline_output_path(self.vault, source)
        target.parent.mkdir(parents=True)
        target.write_text(
            _media_transcript.render_offline_markdown(source, parsed),
            encoding="utf-8",
        )
        article = self.vault / "02-wiki" / "article.md"
        article.parent.mkdir(parents=True)
        article.write_text(
            "# Article\n\n## Sessie-herkomst\n\n"
            f"[[{target.relative_to(self.vault).with_suffix('').as_posix()}]]\n",
            encoding="utf-8",
        )
        lint = load_script("kb-lint.py")
        self.assertEqual(lint.lint_article(article, set(), self.vault), [])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

import _liteparse  # noqa: E402
from _loader import load_script  # noqa: E402


class TestLiteParseHelpers(unittest.TestCase):
    def test_supported_document_extensions_cover_intake_targets(self):
        for name in ("a.pdf", "a.docx", "a.pptx", "a.xlsx", "a.png"):
            self.assertTrue(_liteparse.is_supported_document(Path(name)))
        self.assertFalse(_liteparse.is_supported_document(Path("a.md")))

    def test_default_output_path_uses_bronnen_liteparse(self):
        with TemporaryDirectory() as td:
            src = Path(td) / "Report Final.pdf"
            src.write_bytes(b"%PDF")
            out = _liteparse.default_output_path(Path(td) / "vault", src, prefix="acme")
            self.assertEqual(out.parent, Path(td) / "vault" / "05-bronnen" / "liteparse")
            self.assertTrue(out.name.startswith("bron-"))
            self.assertTrue(out.name.endswith("-acme-report-final.md"))

    def test_parse_document_uses_liteparse_lazily(self):
        calls = {}

        class FakeLiteParse:
            def __init__(self, **kwargs):
                calls["kwargs"] = kwargs

            def parse(self, source):
                calls["source"] = source
                page = types.SimpleNamespace(page_num=1)
                return types.SimpleNamespace(text="Parsed body", pages=[page])

        fake = types.ModuleType("liteparse")
        fake.LiteParse = FakeLiteParse
        fake.__version__ = "2.0.0-test"
        old = sys.modules.get("liteparse")
        sys.modules["liteparse"] = fake
        try:
            with TemporaryDirectory() as td:
                src = Path(td) / "doc.pdf"
                src.write_bytes(b"%PDF")
                parsed = _liteparse.parse_document(
                    src,
                    ocr_enabled=False,
                    target_pages="1",
                    max_pages=2,
                    dpi=200,
                )
            self.assertEqual(parsed.text, "Parsed body")
            self.assertEqual(parsed.page_count, 1)
            self.assertEqual(calls["source"], src)
            self.assertEqual(calls["kwargs"]["output_format"], "markdown")
            self.assertFalse(calls["kwargs"]["ocr_enabled"])
            self.assertEqual(calls["kwargs"]["target_pages"], "1")
            self.assertEqual(calls["kwargs"]["max_pages"], 2)
            self.assertEqual(calls["kwargs"]["dpi"], 200)
        finally:
            if old is None:
                sys.modules.pop("liteparse", None)
            else:
                sys.modules["liteparse"] = old

    def test_render_source_markdown_is_citeable_bron(self):
        with TemporaryDirectory() as td:
            src = Path(td) / "paper.pdf"
            src.write_bytes(b"%PDF")
            parsed = _liteparse.ParsedDocument("Body", 3, "2.0.0")
            text = _liteparse.render_source_markdown(source=src, parsed=parsed)
        self.assertIn("type: bron", text)
        self.assertIn("source: liteparse", text)
        self.assertIn("parse_engine_version: 2.0.0", text)
        self.assertIn("## Content\nBody", text)

    def test_clean_liteparse_text_removes_tesseract_noise(self):
        text = "\n".join(
            [
                "Useful text",
                "Error opening data file tessdata/eng.traineddata",
                "Tesseract couldn't load any languages!",
                "[ocr] failed for page 1: Failed to initialize Tesseract",
            ]
        )
        self.assertEqual(_liteparse.clean_liteparse_text(text), "Useful text")


class TestIntakeLiteParseRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.intake = load_script("intake-scan.py")

    def test_pdf_and_office_route_to_liteparse(self):
        self.assertEqual(self.intake.detect_type(Path("x.pdf")), "pdf")
        self.assertEqual(self.intake.detect_type(Path("x.docx")), "document")
        self.assertEqual(
            self.intake.suggested_action("pdf", Path("x.pdf")),
            "parse_with_liteparse",
        )
        self.assertEqual(
            self.intake.suggested_action("document", Path("x.docx")),
            "parse_with_liteparse",
        )

    def test_images_keep_description_fallback(self):
        self.assertEqual(self.intake.detect_type(Path("scan.png")), "image")
        self.assertEqual(
            self.intake.suggested_action("image", Path("scan.png")),
            "parse_with_liteparse_or_describe",
        )


class TestParseDocumentCli(unittest.TestCase):
    def test_dry_run_directory_reports_supported_documents(self):
        mod = load_script("parse-document.py")
        with TemporaryDirectory() as td:
            root = Path(td)
            vault = root / "vault"
            docs = root / "docs"
            docs.mkdir()
            (docs / "a.pdf").write_bytes(b"%PDF")
            (docs / "ignore.md").write_text("x", encoding="utf-8")
            with redirect_stdout(StringIO()):
                rc = mod.main([str(docs), "--vault", str(vault), "--dry-run", "--json"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

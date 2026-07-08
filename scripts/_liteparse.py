#!/usr/bin/env python3
"""LiteParse integration helpers for local document intake.

The KennisBank core stays markdown-first. This module is the narrow bridge from
binary/source documents to auditable markdown source files under 05-bronnen/.
LiteParse is imported lazily so the rest of the vault keeps failing open when
the optional parser dependency is not installed yet.
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from _common import _today_iso, _utcnow_iso, slugify
except ImportError:  # pragma: no cover - direct execution fallback
    from scripts._common import _today_iso, _utcnow_iso, slugify  # type: ignore


PDF_EXTENSIONS = {".pdf"}
OFFICE_EXTENSIONS = {
    ".doc",
    ".docx",
    ".docm",
    ".odt",
    ".rtf",
    ".pages",
    ".ppt",
    ".pptx",
    ".pptm",
    ".odp",
    ".key",
    ".xls",
    ".xlsx",
    ".xlsm",
    ".ods",
    ".csv",
    ".tsv",
    ".numbers",
}
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
    ".svg",
}
SUPPORTED_DOCUMENT_EXTENSIONS = PDF_EXTENSIONS | OFFICE_EXTENSIONS | IMAGE_EXTENSIONS


class LiteParseUnavailable(RuntimeError):
    """Raised when the optional LiteParse dependency is not importable."""


class DocumentParseError(RuntimeError):
    """Raised when LiteParse cannot parse a document into useful text."""


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    page_count: int
    engine_version: str


TESSERACT_NOISE_PREFIXES = (
    "Error opening data file ",
    "Please make sure the TESSDATA_PREFIX environment variable",
    "Failed loading language ",
    "Tesseract couldn't load any languages!",
    "[ocr] failed for page ",
)


def is_supported_document(path: Path | str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_DOCUMENT_EXTENSIONS


def file_date(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
    except OSError:
        return _today_iso()


def liteparse_version() -> str:
    try:
        return importlib.metadata.version("liteparse")
    except importlib.metadata.PackageNotFoundError:
        try:
            import liteparse  # type: ignore

            return str(getattr(liteparse, "__version__", "unknown"))
        except Exception:
            return "unknown"


def default_output_path(vault: Path, source: Path, prefix: str = "") -> Path:
    date_str = file_date(source)
    slug = slugify(f"{prefix}-{source.stem}" if prefix else source.stem)
    return vault / "05-bronnen" / "liteparse" / f"bron-{date_str}-{slug}.md"


def parse_document(
    source: Path,
    *,
    output_format: str = "markdown",
    ocr_enabled: bool | None = False,
    ocr_language: str | None = None,
    dpi: float | None = None,
    target_pages: str | None = None,
    max_pages: int | None = None,
    password: str | None = None,
    quiet: bool = True,
) -> ParsedDocument:
    if not source.exists():
        raise FileNotFoundError(f"source not found: {source}")
    if not source.is_file():
        raise DocumentParseError(f"source is not a file: {source}")
    if not is_supported_document(source):
        raise DocumentParseError(f"unsupported document extension: {source.suffix}")

    try:
        from liteparse import LiteParse  # type: ignore
    except Exception as exc:
        raise LiteParseUnavailable(
            'LiteParse is not installed; run: python3 -m pip install "liteparse>=2.0,<3"'
        ) from exc

    kwargs: dict = {
        "output_format": output_format,
        "quiet": quiet,
    }
    if ocr_enabled is not None:
        kwargs["ocr_enabled"] = ocr_enabled
    if ocr_language:
        kwargs["ocr_language"] = ocr_language
    if dpi is not None:
        kwargs["dpi"] = dpi
    if target_pages:
        kwargs["target_pages"] = target_pages
    if max_pages is not None:
        kwargs["max_pages"] = max_pages
    if password:
        kwargs["password"] = password

    try:
        result = LiteParse(**kwargs).parse(source)
    except Exception as exc:
        raise DocumentParseError(str(exc)) from exc

    text = clean_liteparse_text(str(getattr(result, "text", "") or ""))
    if not text:
        raise DocumentParseError("LiteParse returned no text")
    pages = getattr(result, "pages", None) or []
    return ParsedDocument(
        text=text,
        page_count=len(pages),
        engine_version=liteparse_version(),
    )


def clean_liteparse_text(text: str) -> str:
    """Remove known OCR backend diagnostics that LiteParse 2.0 can mix into text."""
    lines = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if any(stripped.startswith(prefix) for prefix in TESSERACT_NOISE_PREFIXES):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def yaml_escape(value: str) -> str:
    if value == "":
        return '""'
    if any(c in value for c in [":", "#", '"', "'", "\n", "\\", "[", "]", "{", "}", ",", "&", "*", "!", "|", ">", "%", "@", "`"]):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def render_source_markdown(
    *,
    source: Path,
    parsed: ParsedDocument,
    title: str | None = None,
    prefix: str = "",
) -> str:
    resolved = str(source.resolve())
    doc_title = title or source.stem
    tags = ["bron", "liteparse", "document"]
    if source.suffix.lower() in IMAGE_EXTENSIONS:
        tags.append("ocr")
    fm = {
        "title": doc_title,
        "type": "bron",
        "source": "liteparse",
        "source_id": resolved,
        "source_path": resolved,
        "source_format": source.suffix.lower().lstrip(".") or "unknown",
        "parse_engine": "liteparse",
        "parse_engine_version": parsed.engine_version,
        "page_count": str(parsed.page_count),
        "created": file_date(source),
        "parsed_at": _utcnow_iso(),
        "tags": tags,
        "status": "raw",
    }
    if prefix:
        fm["import_prefix"] = prefix

    lines = ["---"]
    for key, value in fm.items():
        if isinstance(value, list):
            inner = ", ".join(yaml_escape(str(item)) for item in value)
            lines.append(f"{key}: [{inner}]")
        else:
            lines.append(f"{key}: {yaml_escape(str(value))}")
    lines.extend(
        [
            "---",
            "",
            f"# {doc_title}",
            "",
            "## Source",
            f"- Original: `{resolved}`",
            f"- Parsed with: LiteParse {parsed.engine_version}",
            "",
            "## Content",
            parsed.text.lstrip(),
        ]
    )
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text

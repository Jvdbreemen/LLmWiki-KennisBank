#!/usr/bin/env python3
"""Parse source documents into KennisBank markdown with LiteParse.

Default output lives under ``<vault>/05-bronnen/liteparse/`` so parsed PDFs,
Office files, and document-like images become citeable source material without
pretending to be session logs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import print_summary, slugify  # noqa: E402
from _liteparse import (  # noqa: E402
    DocumentParseError,
    LiteParseUnavailable,
    default_output_path,
    is_supported_document,
    parse_document,
    render_source_markdown,
)
from _vaultpath import vault_root  # noqa: E402

VAULT_DEFAULT = vault_root()


def _iter_sources(source: Path, recursive: bool) -> list[Path]:
    if source.is_file():
        return [source] if is_supported_document(source) else []
    if not source.is_dir():
        return []
    iterator = source.rglob("*") if recursive else source.iterdir()
    return sorted(p for p in iterator if p.is_file() and is_supported_document(p))


def _target_for(vault: Path, source: Path, output: Path | None, prefix: str) -> Path:
    if output is None:
        return default_output_path(vault, source, prefix=prefix)
    if output.suffix.lower() == ".md":
        return output
    slug = slugify(f"{prefix}-{source.stem}" if prefix else source.stem)
    return output / f"{slug}.md"


def _parse_one(args: argparse.Namespace, source: Path, imported_at: list[str]) -> dict:
    target = _target_for(args.vault, source, args.output, args.prefix)
    if target.exists() and not args.force:
        return {"status": "skipped", "target": str(target), "reason": "exists"}
    if args.dry_run:
        return {"status": "parsed", "target": str(target), "dry_run": True}

    parsed = parse_document(
        source,
        output_format=args.format,
        ocr_enabled=args.ocr and not args.no_ocr,
        ocr_language=args.ocr_language,
        dpi=args.dpi,
        target_pages=args.target_pages,
        max_pages=args.max_pages,
        password=args.password,
        quiet=not args.verbose,
    )
    text = render_source_markdown(
        source=source,
        parsed=parsed,
        title=args.title if len(imported_at) == 1 else None,
        prefix=args.prefix,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return {
        "status": "parsed",
        "target": str(target),
        "pages": parsed.page_count,
        "engine_version": parsed.engine_version,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse PDF/Office/image documents to KennisBank source markdown via LiteParse."
    )
    parser.add_argument("source", type=Path, help="Document file or directory.")
    parser.add_argument("--vault", type=Path, default=VAULT_DEFAULT,
                        help=f"Vault root (default: {VAULT_DEFAULT})")
    parser.add_argument("--output", type=Path,
                        help="Output .md file or directory. Default: <vault>/05-bronnen/liteparse/.")
    parser.add_argument("--prefix", default="", help="Prefix for generated filenames.")
    parser.add_argument("--title", default="", help="Title override for a single input file.")
    parser.add_argument("--recursive", action="store_true",
                        help="When source is a directory, scan it recursively.")
    parser.add_argument("--format", choices=("markdown", "text"), default="markdown")
    parser.add_argument("--ocr", action="store_true",
                        help="Enable OCR. Default is off to avoid Tesseract/tessdata noise on native-text PDFs.")
    parser.add_argument("--no-ocr", action="store_true",
                        help="Keep OCR disabled. Retained for explicit command readability.")
    parser.add_argument("--ocr-language", default=None, help="Tesseract language code, e.g. eng or nld.")
    parser.add_argument("--dpi", type=float, default=None, help="Render DPI for OCR.")
    parser.add_argument("--target-pages", default=None, help='Pages to parse, e.g. "1-5,10".')
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum pages per document.")
    parser.add_argument("--password", default=None, help="Password for protected documents.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    source = args.source
    if not source.exists():
        print(f"[error] source bestaat niet: {source}", file=sys.stderr)
        return 2

    files = _iter_sources(source, args.recursive)
    if not files:
        print(f"[error] geen ondersteunde LiteParse-documenten gevonden: {source}", file=sys.stderr)
        return 2

    imported = skipped = errors = 0
    files_out: list[str] = []
    errors_detail: list[dict] = []
    imported_at = [str(p) for p in files]

    for fp in files:
        try:
            result = _parse_one(args, fp, imported_at)
            if result["status"] == "skipped":
                skipped += 1
                if args.verbose or not args.json:
                    print(f"[skip] exists: {result['target']}")
                continue
            imported += 1
            files_out.append(result["target"])
            if not args.json:
                action = "dry-run" if args.dry_run else "parsed"
                print(f"[+] {action} {fp} -> {result['target']}")
        except (LiteParseUnavailable, DocumentParseError, OSError, FileNotFoundError) as exc:
            errors += 1
            errors_detail.append({"path": str(fp), "stage": "parse", "error": str(exc)})
            if args.verbose or not args.json:
                print(f"[err] parse {fp}: {exc}", file=sys.stderr)

    summary = {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "files": files_out,
        "errors_detail": errors_detail,
    }
    print_summary(summary, args.json)
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

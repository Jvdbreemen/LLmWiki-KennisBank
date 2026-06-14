#!/usr/bin/env python3
"""
intake-scan.py — Scant ~/KennisBank/00-inbox/ en produceert een JSON-rapport.

Gebruik: python3 intake-scan.py
"""

import json
import sys
from pathlib import Path

INBOX = Path.home() / "KennisBank" / "00-inbox"

FRONTMATTER_MARKER = "---"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def detect_type(path: Path) -> str:
    """Detecteer het bestandstype op basis van inhoud en extensie."""
    ext = path.suffix.lower()

    # URL-detectie: bestand bevat één regel die begint met http of https.
    # Alleen tekstuele/onbekende extensies lezen, nooit binaire (pdf, images).
    if ext in ("", ".txt", ".url", ".md") and ext not in {
        ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".gif"
    }:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            lines = [l for l in text.splitlines() if l.strip()]
            if len(lines) == 1 and (
                lines[0].startswith("http://") or lines[0].startswith("https://")
            ):
                return "url"
        except (OSError, PermissionError):
            pass

    if ext == ".md":
        return "markdown"
    if ext == ".txt":
        return "text"
    if ext == ".pdf":
        return "pdf"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "other"


def has_frontmatter(path: Path) -> bool:
    """Controleer of een markdown-bestand YAML frontmatter heeft."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        return len(lines) >= 1 and lines[0].strip() == FRONTMATTER_MARKER
    except (OSError, PermissionError):
        return False


def suggested_action(file_type: str, path: Path) -> str:
    """Bepaal de aanbevolen actie op basis van type en frontmatter."""
    if file_type == "url":
        return "fetch_and_convert"
    if file_type == "markdown":
        return "move_to_raw" if has_frontmatter(path) else "add_frontmatter"
    if file_type == "text":
        return "convert_to_markdown"
    if file_type == "pdf":
        return "extract_text"
    if file_type == "image":
        return "describe_and_tag"
    return "review_manually"


def first_line(path: Path) -> str | None:
    """Geeft de eerste niet-lege regel van een tekstbestand, of None."""
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:200]
    except (OSError, PermissionError):
        pass
    return None


def extract_url(path: Path) -> str | None:
    """Haal de URL op uit een url-bestand."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        lines = [l for l in text.splitlines() if l.strip()]
        if lines:
            return lines[0].strip()
    except (OSError, PermissionError):
        pass
    return None


def scan() -> dict:
    if not INBOX.exists():
        return {"files": [], "total": 0, "empty": True, "error": f"00-inbox niet gevonden: {INBOX}"}

    # Alleen directe bestanden, geen submappen
    paths = sorted(
        p for p in INBOX.iterdir() if p.is_file() and not p.name.startswith(".")
    )

    if not paths:
        return {"files": [], "total": 0, "empty": True}

    files = []
    for path in paths:
        file_type = detect_type(path)
        entry: dict = {
            "path": str(path),
            "type": file_type,
            "size_bytes": path.stat().st_size,
        }

        if file_type == "url":
            url = extract_url(path)
            if url:
                entry["url"] = url
        elif file_type in ("markdown", "text"):
            fl = first_line(path)
            if fl:
                entry["first_line"] = fl

        entry["suggested_destination"] = "01-raw/"
        entry["suggested_action"] = suggested_action(file_type, path)

        files.append(entry)

    return {"files": files, "total": len(files), "empty": False}


if __name__ == "__main__":
    report = scan()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0)

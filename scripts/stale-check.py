#!/usr/bin/env python3
"""
stale-check.py — Detecteer verouderde wiki-artikelen in de KennisBank.

Gebruik: python3 stale-check.py [--days 60]
"""

import argparse
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _frontmatter import parse_frontmatter as _parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

VAULT_ROOT = vault_root()
WIKI_DIR = VAULT_ROOT / "02-wiki"
SESSIES_DIR = VAULT_ROOT / "01-raw" / "sessies"
SESSIE_DATE_RE = re.compile(r"raw-sessie-(\d{4}-\d{2}-\d{2})")


def parse_frontmatter(text: str) -> dict:
    """Extraheer YAML frontmatter uit een markdown-bestand (eenvoudige key: value parser)."""
    data, _ = _parse_frontmatter(text)
    return data


def parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def load_sessie_dates() -> list[tuple[date, Path]]:
    """Geef lijst van (datum, pad) voor alle sessielogs."""
    result = []
    if not SESSIES_DIR.exists():
        return result
    for f in SESSIES_DIR.glob("raw-sessie-*.md"):
        m = SESSIE_DATE_RE.search(f.name)
        if m:
            d = parse_date(m.group(1))
            if d:
                result.append((d, f))
    return result


def mentions_article(sessie_path: Path, stem: str, title: str) -> bool:
    """Check of het sessiebestand de wiki-stem of titel noemt."""
    try:
        text = sessie_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    stem_lower = stem.lower()
    title_lower = title.lower()
    text_lower = text.lower()
    return stem_lower in text_lower or (title_lower and title_lower in text_lower)


def main():
    parser = argparse.ArgumentParser(description="Detecteer verouderde KennisBank wiki-artikelen.")
    parser.add_argument("--days", type=int, default=60, help="Drempelwaarde in dagen (default: 60)")
    args = parser.parse_args()

    threshold = args.days
    today = date.today()

    if not WIKI_DIR.exists():
        print(f"Wiki-directory niet gevonden: {WIKI_DIR}", file=sys.stderr)
        sys.exit(1)

    sessie_dates = load_sessie_dates()

    stale_with_sessies = []
    stale_without_sessies = []

    for wiki_file in sorted(WIKI_DIR.glob("*.md")):
        if wiki_file.name.startswith("_") or wiki_file.name == "index.md":
            continue

        text = wiki_file.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)

        updated_raw = fm.get("updated") or fm.get("date") or ""
        updated = parse_date(updated_raw) if updated_raw else None
        if updated is None:
            continue

        age = (today - updated).days
        if age <= threshold:
            continue

        title = fm.get("title", "")
        stem = wiki_file.stem

        # Zoek sessielogs die nieuwer zijn dan `updated` en het artikel noemen
        newer_sessies = [
            (d, p) for d, p in sessie_dates
            if d > updated and mentions_article(p, stem, title)
        ]
        newer_sessies.sort(key=lambda x: x[0])

        entry = {
            "filename": wiki_file.name,
            "age": age,
            "updated": updated.isoformat(),
            "sessies": [p.name for _, p in newer_sessies],
        }

        if newer_sessies:
            stale_with_sessies.append(entry)
        else:
            stale_without_sessies.append(entry)

    # Sorteer op leeftijd (oudste eerst)
    stale_with_sessies.sort(key=lambda e: e["age"], reverse=True)
    stale_without_sessies.sort(key=lambda e: e["age"], reverse=True)

    total = len(stale_with_sessies) + len(stale_without_sessies)

    print(f"## Verouderde wiki-artikelen (>{threshold} dagen, {today})\n")

    if total == 0:
        print(f"Geen verouderde artikelen gevonden.")
        return

    if stale_with_sessies:
        print("### Heeft nieuwere sessielogs:")
        for e in stale_with_sessies:
            print(f"- {e['filename']} ({e['age']} dagen oud, updated: {e['updated']})")
            sessie_list = ", ".join(e["sessies"])
            print(f"  Sessies: {sessie_list}")
        print()

    if stale_without_sessies:
        print("### Geen recente sessielogs:")
        for e in stale_without_sessies:
            print(f"- {e['filename']} ({e['age']} dagen oud, updated: {e['updated']})")

    print(f"\nTotaal: {total} verouderd ({len(stale_with_sessies)} met sessielogs, {len(stale_without_sessies)} zonder)")


if __name__ == "__main__":
    main()

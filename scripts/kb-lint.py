#!/usr/bin/env python3
"""
kb-lint.py — Provenance-lint voor KennisBank wiki-artikelen.

Valideert dat elk wiki-artikel in 02-wiki/ herleidbare sessie-herkomst heeft.
Een gecompileerd artikel zonder werkende link naar zijn raw-sessie(s) is niet
auditeerbaar: een hallucinatie tijdens destillatie wordt dan een duurzaam
"feit" dat nooit meer tegen de bron te checken is.

Checks per artikel:

1. **missing** — geen enkele verwijzing naar een raw-sessie
   (geen ``[[raw-sessie-...]]``-wikilink en geen pad-tekst).
2. **dangling** — een ``[[raw-sessie-...]]``-wikilink waarvan het bestand niet
   bestaat in ``01-raw/sessies/`` of ``08-archive/``.
3. **path-only** — de enige herkomst is een pad-tekst zoals
   ``01-raw/sessies/raw-sessie-....md`` (backticks of proza). Pad-tekst is
   onzichtbaar voor Obsidian-backlinks en de kennisgraaf; maak er een
   wikilink van.

Herkomst telt in twee vormen: een ``[[raw-sessie-...]]``-wikilink (sessie-
herkomst) of een expliciete ``[[05-bronnen/...]]``-wikilink (bron-herkomst,
voor artikelen die uit een import komen in plaats van uit een sessie).
Verwijzingen naar memories of andere artikelen zijn verbanden, geen bron.
``index.md`` en ``log.md`` zijn structuurbestanden en worden overgeslagen.

Gebruik: python3 kb-lint.py [--json]

Exit codes (zelfde conventie als een evaluator):
  0 = alle artikelen schoon
  1 = fout (vault of wiki-directory niet gevonden)
  2 = waarschuwingen gevonden
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

SKIP_FILES = {"index.md", "log.md"}
SESSION_PREFIX = "raw-sessie-"

# [[target]], [[target|alias]], [[pad/naar/target#kop]]
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
# Pad-tekst naar een sessielog buiten een wikilink om (backticks of proza).
PATH_REF_RE = re.compile(r"01-raw[/\\]sessies[/\\](raw-sessie-[\w.-]+)")


def normalize_target(target: str) -> str:
    """Herleid een wikilink-target tot de kale bestandsstam.

    Strips alias (``|``), kop-anker (``#``), pad-prefix en ``.md``-extensie,
    zodat ``[[01-raw/sessies/raw-sessie-x.md|bron]]`` en ``[[raw-sessie-x]]``
    dezelfde stam opleveren.
    """
    target = target.split("|", 1)[0].split("#", 1)[0].strip()
    target = target.replace("\\", "/").rsplit("/", 1)[-1]
    if target.endswith(".md"):
        target = target[:-3]
    return target


#: Directories die nooit sessielogs bevatten (tooling/index-output).
SKIP_DIRS = {".claude", ".git", ".obsidian", "graphify-out"}


def collect_session_stems(root: Path) -> set[str]:
    """Verzamel de bestandsstammen van alle bekende raw-sessies.

    Vault-breed (zoals Obsidian wikilinks op bestandsnaam resolvet): actieve
    sessies staan in ``01-raw/sessies/``, maar verplaatste of gearchiveerde
    sessies (``01-raw/debug/``, ``08-archive/``, ...) blijven geldige
    herkomst zolang het bestand ergens in de vault bestaat.
    """
    stems: set[str] = set()
    for f in root.rglob(f"{SESSION_PREFIX}*.md"):
        # Alleen de directories BINNEN de vault tellen; f.parents zou ook
        # ancestors boven de vault-root meenemen (een vault die zelf onder
        # een .claude/ of graphify-out/ pad ligt zou anders nul stems krijgen).
        try:
            rel_dirs = f.relative_to(root).parts[:-1]
        except ValueError:
            rel_dirs = ()
        if SKIP_DIRS.isdisjoint(rel_dirs):
            stems.add(f.stem)
    return stems


def _clean_target(target: str) -> str:
    """Strip alias en kop-anker van een wikilink-target, behoud het pad."""
    return target.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/")


def resolving_bron_links(text: str, root: Path) -> tuple[list, list]:
    """(resolvend, dangling) voor expliciete [[05-bronnen/...]]-wikilinks.

    Bron-herkomst voor artikelen die uit een import (bv. Evernote) komen in
    plaats van uit een sessie. Alleen path-stijl links die met ``05-bronnen/``
    beginnen tellen; kale artikel-links blijven verbanden.
    """
    ok, dead = [], []
    for t in WIKILINK_RE.findall(text):
        target = _clean_target(t)
        if not target.startswith("05-bronnen/"):
            continue
        p = root / target
        if p.exists() or (not target.endswith(".md")
                          and (root / (target + ".md")).exists()):
            ok.append(target)
        else:
            dead.append(target)
    return ok, dead


def lint_article(path: Path, stems: set[str], root: Path) -> list[dict]:
    """Lint één artikel. Geeft een lijst findings terug (leeg = schoon).

    Elke finding is ``{"file": str, "type": str, "detail": str}`` met type
    ``missing`` | ``dangling`` | ``path-only``.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [{"file": path.name, "type": "unreadable", "detail": str(exc)}]

    session_links = [
        normalize_target(t)
        for t in WIKILINK_RE.findall(text)
        if normalize_target(t).startswith(SESSION_PREFIX)
    ]
    bron_ok, bron_dead = resolving_bron_links(text, root)
    resolving = [t for t in session_links if t in stems] + bron_ok
    dangling = [t for t in session_links if t not in stems] + bron_dead

    # Pad-verwijzingen buiten wikilinks om: eerst alle wikilinks wegknippen,
    # dan pas naar losse pad-tekst zoeken.
    text_without_links = WIKILINK_RE.sub("", text)
    path_refs = PATH_REF_RE.findall(text_without_links)

    findings: list[dict] = []
    for target in dangling:
        findings.append({
            "file": path.name,
            "type": "dangling",
            "detail": f"dode herkomst-link [[{target}]]: bestand niet gevonden in de vault",
        })
    if not resolving:
        if path_refs:
            findings.append({
                "file": path.name,
                "type": "path-only",
                "detail": "herkomst alleen als pad-tekst (onzichtbaar voor backlinks en de kennisgraaf); maak er een [[raw-sessie-...]]-wikilink van",
            })
        elif not dangling:
            findings.append({
                "file": path.name,
                "type": "missing",
                "detail": "geen herkomst: geen [[raw-sessie-...]]- of [[05-bronnen/...]]-verwijzing",
            })
    return findings


def lint_vault(root: Path) -> dict:
    """Lint alle wiki-artikelen onder ``root``. Geeft het rapport-dict terug."""
    wiki_dir = root / "02-wiki"
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"wiki-directory niet gevonden: {wiki_dir}")

    stems = collect_session_stems(root)
    warnings: list[dict] = []
    articles = 0
    for f in sorted(wiki_dir.glob("*.md")):
        if f.name in SKIP_FILES:
            continue
        articles += 1
        warnings.extend(lint_article(f, stems, root))

    warned_files = {w["file"] for w in warnings}
    return {
        "articles": articles,
        "clean": articles - len(warned_files),
        "warned": len(warned_files),
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provenance-lint voor KennisBank wiki-artikelen."
    )
    parser.add_argument(
        "--json", action="store_true",
        help="machine-leesbare JSON-uitvoer (voor doctor.sh)",
    )
    args = parser.parse_args()

    root = vault_root()
    try:
        report = lint_vault(root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        for w in report["warnings"]:
            print(f"[WARN] 02-wiki/{w['file']}: {w['detail']}")
        print(
            f"Samenvatting: {report['articles']} artikelen, "
            f"{report['warned']} met waarschuwingen, {report['clean']} schoon"
        )

    return 2 if report["warnings"] else 0


if __name__ == "__main__":
    sys.exit(main())

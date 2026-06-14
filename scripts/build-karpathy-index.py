#!/usr/bin/env python3
"""
build-karpathy-index.py — Bouw een Karpathy-format `index.md` en `log.md` voor de
KennisBank-vault zodat Understand-Anything's `/understand-knowledge` skill
(parse-knowledge-base.py) de wiki herkent als een drie-laags Karpathy LLM-wiki.

Karpathy LLM-wiki pattern (kort):
- index.md met `## Section` headings, en daaronder `[[wikilink]]`-regels die naar
  artikel-bestanden wijzen (bestandsnamen zonder `.md`, case-insensitive resolve).
  De parser leidt zijn topic-categorieen rechtstreeks af uit deze headings.
- log.md met regels in het format `## [YYYY-MM-DD] OPERATION | Title` (een
  chronologisch overzicht van wijzigingen / sessie-events).
- Beide bestanden moeten naast de wiki-artikelen leven (in onze vault dus in
  `<vault-root>/02-wiki/`).

Pipeline-positie:
  /wiki  →  build-karpathy-index.py  →  /understand-knowledge

Draai dit script nadat `/wiki` nieuwe artikelen heeft toegevoegd (of na grote
hernoeming) en voor je Understand-Anything's `/understand-knowledge` aanroept,
zodat parse-knowledge-base.py de meest recente structuur ziet.

Gebruik:
  python3 build-karpathy-index.py                       # default vault, met veiligheids-check
  python3 build-karpathy-index.py --dry-run             # print samenvatting + preview, schrijf niets
  python3 build-karpathy-index.py --force               # overschrijf bestaande index.md/log.md (.bak backup)
  python3 build-karpathy-index.py --vault-root /pad/naar/KennisBank
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Optionele PyYAML — gebruik indien beschikbaar voor robuuste frontmatter-parsing.
try:  # pragma: no cover - import-resolutie alleen
    import yaml  # type: ignore

    _HAS_YAML = True
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore
    _HAS_YAML = False


VAULT_DEFAULT = Path.home() / "KennisBank"
WIKI_SUBDIR_DEFAULT = "02-wiki"
SESSIES_SUBDIR_DEFAULT = "01-raw/sessies"

# Bestanden die nooit als artikel meetellen (infra of conventie).
SKIP_FILENAMES = {"index.md", "log.md", "readme.md"}

# Generieke tags die we niet als categorie willen gebruiken.
GENERIC_TAGS = {
    "wiki",
    "kennisbank",
    "actief",
    "concept",
    "index",
    "snapshot",
    "claude-memory",
}

# Regex voor sessie-bestandsnamen: raw-sessie-YYYY-MM-DD-<slug>.md
SESSIE_RE = re.compile(r"^raw-sessie-(\d{4}-\d{2}-\d{2})-(.+)\.md$", re.IGNORECASE)

# ----------------------------------------------------------------------------
# Categorie-regels: lijst van (categorienaam, set van tag-keywords).
# Volgorde bepaalt prioriteit; eerst-matchende wint per artikel. Categorienamen
# in NL — gekozen omdat de bestaande vault overwegend Nederlandse tags heeft.
# ----------------------------------------------------------------------------
CATEGORY_RULES: list[tuple[str, set[str]]] = [
    (
        "Claude Code: workflow, skills en subagents",
        {
            "claude-code",
            "skills",
            "skill",
            "subagent",
            "subagents",
            "agent",
            "agents",
            "slash-commands",
            "commands",
            "autoresearch",
            "anatomy",
            "cozempic",
            "openwolf",
            "scheduling",
            "cron",
            "routines",
            "lazy-hierarchy",
        },
    ),
    (
        "Claude Code: configuratie en model-infrastructuur",
        {
            "ccr",
            "ollama",
            "jsonl",
            "mcp",
            "statusline",
            "claude-code-router",
            "api-key",
            "max-api-key",
            "ingest",
            "data-locaties",
            "claude-projects",
        },
    ),
    (
        "Vault, Atelier en kennisbank-architectuur",
        {
            "vault",
            "vault-app",
            "atelier",
            "kennisbank",
            "kennismanagement",
            "rag",
            "cag",
            "graphify",
            "knowledge-management",
            "monorepo",
            "three-way-merge",
            "embeddings",
            "retrieval",
            "obsidian",
            "notion",
            "memory-palace",
            "mempalace",
        },
    ),
    (
        "Quartz, Hugo en static-site publicatie",
        {
            "quartz",
            "hugo",
            "static-site",
            "static-sites",
            "ftp",
            "deploy",
            "publicatie",
            "weboke",
        },
    ),
    (
        "Frontend, design en visuele systemen",
        {
            "frontend",
            "design",
            "design-system",
            "design-tokens",
            "tailwind",
            "css",
            "oklch",
            "react",
            "codemirror",
            "gsap",
            "d3",
            "svg",
            "glassmorphism",
            "typografie",
            "design-dtp",
            "scrollytelling",
            "scrolly",
            "ui",
            "ux",
        },
    ),
    (
        "Journalistiek: methode, redactie en onderzoek",
        {
            "journalistiek",
            "ai-journalistiek",
            "eindredactie",
            "tekstredactie",
            "factcheck",
            "interview",
            "interviewvoorbereiding",
            "publieksonderzoek",
            "journalistieke-formats",
            "lokale-journalistiek",
            "research",
            "fieldwork",
            "redactie",
            "auteursrecht",
            "publiekstheorie",
        },
    ),
    (
        "Tooling, devops en systeembeheer",
        {
            "tooling",
            "devops",
            "systeembeheer",
            "macos",
            "python",
            "pipx",
            "fastmcp",
            "docker",
            "github",
            "gh-cli",
            "tauri",
            "cli-first",
            "automation",
            "pre-publicatie",
            "secrets",
            "lightpanda",
            "headless-browsers",
            "remotion",
            "openwolf",
        },
    ),
    (
        "AV, fotografie en lokale praktijk",
        {
            "av-tooling",
            "fotografie",
            "foto",
            "audio",
            "video",
            "camera",
            "hasselblad",
            "lokaal",
            "arnhem",
            "blackhole",
            "yt-dlp",
            "after-effects",
            "kdenlive",
            "openmontage",
            "fujifilm",
        },
    ),
    (
        "ADR en architectuurbeslissingen",
        {
            "adr",
            "architectuur",
            "decision",
            "decisions",
            "architecturele-keuzes",
            "documentatie",
        },
    ),
]

# Filename-prefix → categorie (laatste vangnet voor wiki-<domain>-... patterns).
PREFIX_HINTS: dict[str, str] = {
    "wiki-cc-": "Claude Code: workflow, skills en subagents",
    "wiki-claude-code-": "Claude Code: configuratie en model-infrastructuur",
    "wiki-claude-": "Claude Code: configuratie en model-infrastructuur",
    "wiki-vault-": "Vault, Atelier en kennisbank-architectuur",
    "wiki-atelier-": "Vault, Atelier en kennisbank-architectuur",
    "wiki-kennisbank-": "Vault, Atelier en kennisbank-architectuur",
    "wiki-quartz-": "Quartz, Hugo en static-site publicatie",
    "wiki-hugo-": "Quartz, Hugo en static-site publicatie",
    "wiki-design-": "Frontend, design en visuele systemen",
    "wiki-journalistiek": "Journalistiek: methode, redactie en onderzoek",
    "wiki-foto-": "AV, fotografie en lokale praktijk",
    "wiki-av-": "AV, fotografie en lokale praktijk",
    "wiki-adr-": "ADR en architectuurbeslissingen",
}

OVERIG_NL = "Overig"
OVERIG_EN = "Other"
MEMORY_CATEGORY = "Memory-snapshots"


# ----------------------------------------------------------------------------
# Frontmatter-parsing
# ----------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Geef (frontmatter_block, rest) terug; lege frontmatter als geen match."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def _minimal_yaml_parse(block: str) -> dict[str, Any]:
    """Zeer beperkte YAML-parser: alleen `key: value` en `key: [a, b, c]` lijsten.

    Voor complexere frontmatter (nested, multiline) — gebruik PyYAML als
    beschikbaar. Deze fallback is robuust genoeg voor onze vault-conventie.
    """
    out: dict[str, Any] = {}
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        # Lijst-literaal `[a, b, c]`
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                out[key] = []
            else:
                items = [
                    p.strip().strip('"').strip("'")
                    for p in inner.split(",")
                ]
                out[key] = [it for it in items if it]
            continue
        # Quoted string strippen
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        out[key] = value
    return out


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse YAML-frontmatter; gebruik PyYAML indien aanwezig, anders minimal parser."""
    block, _ = _split_frontmatter(text)
    if not block:
        return {}
    if _HAS_YAML:
        try:
            data = yaml.safe_load(block)  # type: ignore[union-attr]
            if isinstance(data, dict):
                return data
            return {}
        except Exception as e:  # pragma: no cover - log + fallback
            print(f"[warn] PyYAML parse-error, fallback minimal: {e}", file=sys.stderr)
    return _minimal_yaml_parse(block)


# ----------------------------------------------------------------------------
# Categorisatie
# ----------------------------------------------------------------------------

def _normalize_tag(tag: str) -> str:
    return tag.strip().lower()


def _tags_from_frontmatter(fm: dict[str, Any]) -> list[str]:
    raw = fm.get("tags")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [_normalize_tag(str(t)) for t in raw if str(t).strip()]
    if isinstance(raw, str):
        # `tag1, tag2, tag3` of `[tag1, tag2]`-string
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        parts = [p.strip().strip('"').strip("'") for p in s.split(",")]
        return [_normalize_tag(p) for p in parts if p]
    return []


def _category_from_tags(tags: list[str]) -> str | None:
    """Match tags tegen CATEGORY_RULES; retourneer eerste hit."""
    tag_set = {t for t in tags if t and t not in GENERIC_TAGS}
    for category, keywords in CATEGORY_RULES:
        if tag_set & keywords:
            return category
    return None


def _category_from_prefix(filename: str) -> str | None:
    fn_lower = filename.lower()
    # Langste prefix eerst — sorteer reverse op lengte.
    for prefix in sorted(PREFIX_HINTS, key=len, reverse=True):
        if fn_lower.startswith(prefix):
            return PREFIX_HINTS[prefix]
    return None


def categorize(filename: str, fm: dict[str, Any], language: str) -> tuple[str, bool]:
    """Bepaal categorie voor een artikel.

    Returns (category_name, is_memory_snapshot).
    Prioriteit: (1) frontmatter `category` veld, (2) tag-match, (3) filename-prefix,
    (4) Overig/Other.
    Memory-snapshots worden altijd in de aparte sectie geplaatst, ongeacht andere matches.
    """
    is_memory = str(fm.get("type", "")).strip().lower() == "wiki-memory"
    if is_memory:
        return MEMORY_CATEGORY, True

    explicit = fm.get("category")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip(), False

    tags = _tags_from_frontmatter(fm)
    cat = _category_from_tags(tags)
    if cat:
        return cat, False

    cat = _category_from_prefix(filename)
    if cat:
        return cat, False

    return (OVERIG_NL if language == "nl" else OVERIG_EN), False


# ----------------------------------------------------------------------------
# Taaldetectie (heuristiek op tags-corpus)
# ----------------------------------------------------------------------------

NL_HINTS = {
    "kennisbank",
    "redactie",
    "journalistiek",
    "werkwijze",
    "lokaal",
    "publicatie",
    "ontwerp",
    "tekstredactie",
    "actief",
    "wiki",
}


def detect_language(all_tags: list[str]) -> str:
    """Sniff dominante taal van het tag-corpus. Default NL voor onze vault."""
    nl = sum(1 for t in all_tags if t in NL_HINTS)
    return "nl" if nl >= 1 else "en"


# ----------------------------------------------------------------------------
# Wiki-scanner
# ----------------------------------------------------------------------------

def humanize_slug(slug: str) -> str:
    parts = slug.replace("_", "-").split("-")
    return " ".join(p.capitalize() for p in parts if p)


def scan_wiki(wiki_dir: Path) -> tuple[list[dict[str, Any]], str]:
    """Scan `wiki_dir` (niet-recursief) voor artikelen.

    Returns (articles, language). Elk article is een dict met keys:
        filename, stem, title, category, is_memory.
    """
    articles: list[dict[str, Any]] = []
    all_tags: list[str] = []

    if not wiki_dir.is_dir():
        print(f"[error] wiki-directory bestaat niet: {wiki_dir}", file=sys.stderr)
        return articles, "nl"

    md_files = sorted(p for p in wiki_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md")
    for fp in md_files:
        if fp.name.lower() in SKIP_FILENAMES:
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"[warn] kan niet lezen {fp}: {e}", file=sys.stderr)
            continue

        try:
            fm = parse_frontmatter(text)
        except Exception as e:
            print(f"[warn] frontmatter parse-error in {fp.name}: {e}", file=sys.stderr)
            fm = {}

        all_tags.extend(_tags_from_frontmatter(fm))

        articles.append({
            "filename": fp.name,
            "stem": fp.stem,
            "title": str(fm.get("title", "")).strip() or humanize_slug(fp.stem),
            "fm": fm,
        })

    language = detect_language(all_tags)

    # Categoriseren in tweede pass (taal nodig voor 'Overig' vs 'Other').
    for art in articles:
        cat, is_mem = categorize(art["filename"], art["fm"], language)
        art["category"] = cat
        art["is_memory"] = is_mem

    return articles, language


# ----------------------------------------------------------------------------
# Sessie-scanner
# ----------------------------------------------------------------------------

def scan_sessies(sessies_dir: Path) -> list[dict[str, Any]]:
    """Scan recursief naar `raw-sessie-YYYY-MM-DD-*.md`-bestanden.

    Returns list of dicts: {date, slug, title}, gesorteerd descending op date.
    """
    out: list[dict[str, Any]] = []
    if not sessies_dir.is_dir():
        print(f"[warn] sessies-directory bestaat niet: {sessies_dir}", file=sys.stderr)
        return out

    for fp in sessies_dir.rglob("*.md"):
        m = SESSIE_RE.match(fp.name)
        if not m:
            continue
        date_str = m.group(1)
        slug = m.group(2)
        title = humanize_slug(slug)
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            fm_title = str(fm.get("title", "")).strip()
            if fm_title:
                title = fm_title
        except OSError as e:
            print(f"[warn] kan niet lezen sessie {fp}: {e}", file=sys.stderr)

        out.append({"date": date_str, "slug": slug, "title": title, "path": fp})

    out.sort(key=lambda d: d["date"], reverse=True)
    return out


# ----------------------------------------------------------------------------
# Renderers
# ----------------------------------------------------------------------------

def _wikilink(stem: str, title: str) -> str:
    """Bouw [[stem|title]] of [[stem]] afhankelijk of title informatief is."""
    pretty_stem = humanize_slug(stem.removeprefix("wiki-"))
    if title and title.strip().lower() != pretty_stem.lower() and title.strip().lower() != stem.lower():
        return f"[[{stem}|{title}]]"
    return f"[[{stem}]]"


def render_index(articles: list[dict[str, Any]], language: str, generated_at: str) -> tuple[str, dict[str, int]]:
    """Render index.md content. Returns (text, stats).

    Stats: {"categories": N, "wikilinks": M}.
    """
    # Cluster per categorie.
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for art in articles:
        by_cat.setdefault(art["category"], []).append(art)

    # Sorteer artikelen binnen categorie alfabetisch op title.
    for cat, items in by_cat.items():
        items.sort(key=lambda a: a["title"].lower())

    # Sorteer categorieen op aantal artikelen (descending), Memory-snapshots laatst.
    regular = [c for c in by_cat if c != MEMORY_CATEGORY]
    regular.sort(key=lambda c: (-len(by_cat[c]), c.lower()))
    ordered = regular + ([MEMORY_CATEGORY] if MEMORY_CATEGORY in by_cat else [])

    intro = (
        "Index van wiki-artikelen, gegroepeerd per thema."
        if language == "nl"
        else "Index of wiki articles, grouped by theme."
    )

    lines: list[str] = []
    lines.append(f"<!-- Auto-gegenereerd door build-karpathy-index.py op {generated_at}. Niet handmatig bewerken. -->")
    lines.append("")
    lines.append("# Index")
    lines.append("")
    lines.append(intro)
    lines.append("")

    wikilink_count = 0
    for cat in ordered:
        lines.append(f"## {cat}")
        lines.append("")
        for art in by_cat[cat]:
            lines.append(f"- {_wikilink(art['stem'], art['title'])}")
            wikilink_count += 1
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    return text, {"categories": len(ordered), "wikilinks": wikilink_count}


def render_log(sessies: list[dict[str, Any]], language: str, generated_at: str) -> tuple[str, int]:
    """Render log.md content. Returns (text, entry_count)."""
    lines: list[str] = []
    lines.append(f"<!-- Auto-gegenereerd door build-karpathy-index.py op {generated_at}. Niet handmatig bewerken. -->")
    lines.append("")
    lines.append("# Log")
    lines.append("")

    if not sessies:
        today = datetime.now(timezone.utc).date().isoformat()
        lines.append(f"## [{today}] SETUP | Initial log")
        lines.append("")
        text = "\n".join(lines).rstrip() + "\n"
        return text, 1

    for s in sessies:
        lines.append(f"## [{s['date']}] OPERATION | {s['title']}")
    lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    return text, len(sessies)


# ----------------------------------------------------------------------------
# Output / safety
# ----------------------------------------------------------------------------

def _backup(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    return bak


def write_with_safety(target: Path, content: str, force: bool, dry_run: bool) -> bool:
    """Schrijf bestand. Bij conflict (bestaat + niet --force): error.

    Returns True bij geslaagd schrijven (of dry-run), False bij conflict.
    """
    if dry_run:
        return True
    if target.exists() and not force:
        print(
            f"[error] {target} bestaat al. Gebruik --force om te overschrijven (.bak backup wordt gemaakt).",
            file=sys.stderr,
        )
        return False
    if target.exists() and force:
        bak = _backup(target)
        print(f"[info] backup geschreven: {bak}", file=sys.stderr)
    target.write_text(content, encoding="utf-8")
    return True


def _preview(text: str, n: int = 20) -> str:
    lines = text.splitlines()
    head = "\n".join(lines[:n])
    if len(lines) > n:
        head += f"\n... ({len(lines) - n} meer regels)"
    return head


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bouw Karpathy-format index.md en log.md voor de KennisBank-wiki, "
            "zodat parse-knowledge-base.py van Understand-Anything de wiki herkent."
        )
    )
    parser.add_argument(
        "--vault-root",
        type=Path,
        default=VAULT_DEFAULT,
        help=f"Root van de vault (default: {VAULT_DEFAULT})",
    )
    parser.add_argument(
        "--wiki-dir",
        type=str,
        default=WIKI_SUBDIR_DEFAULT,
        help=f"Wiki-subdir relatief aan vault-root (default: {WIKI_SUBDIR_DEFAULT})",
    )
    parser.add_argument(
        "--sessies-dir",
        type=str,
        default=SESSIES_SUBDIR_DEFAULT,
        help=f"Sessies-subdir relatief aan vault-root (default: {SESSIES_SUBDIR_DEFAULT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Toon samenvatting + preview van index.md/log.md, schrijf niets.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overschrijf bestaande index.md/log.md (maak .bak backup).",
    )
    args = parser.parse_args()

    vault_root: Path = args.vault_root.expanduser().resolve()
    wiki_dir: Path = (vault_root / args.wiki_dir).resolve()
    sessies_dir: Path = (vault_root / args.sessies_dir).resolve()

    if not vault_root.is_dir():
        print(f"[error] vault-root bestaat niet of is geen directory: {vault_root}", file=sys.stderr)
        return 1

    articles, language = scan_wiki(wiki_dir)
    if not articles:
        print(
            f"[error] geen wiki-artikelen gevonden in {wiki_dir} (skip: {SKIP_FILENAMES})",
            file=sys.stderr,
        )
        return 1

    sessies = scan_sessies(sessies_dir)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    index_text, idx_stats = render_index(articles, language, generated_at)
    log_text, log_count = render_log(sessies, language, generated_at)

    index_path = wiki_dir / "index.md"
    log_path = wiki_dir / "log.md"

    # Categorieen-distributie voor rapport.
    cat_counts = Counter(a["category"] for a in articles)

    if args.dry_run:
        print("=== DRY RUN ===")
        print(
            f"vault-root:  {vault_root}\n"
            f"wiki-dir:    {wiki_dir}\n"
            f"sessies-dir: {sessies_dir}\n"
            f"language:    {language}\n"
        )
        print(f"Articles:    {len(articles)}")
        print(f"Categories:  {idx_stats['categories']}")
        print(f"Wikilinks:   {idx_stats['wikilinks']}")
        print(f"Log entries: {log_count}")
        print()
        print("Per-category counts:")
        for cat, n in sorted(cat_counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
            print(f"  {n:3d}  {cat}")
        print()
        print(f"--- Preview {index_path} (eerste 20 regels) ---")
        print(_preview(index_text, 20))
        print()
        print(f"--- Preview {log_path} (eerste 20 regels) ---")
        print(_preview(log_text, 20))
        print()
        print("(geen bestanden geschreven; gebruik zonder --dry-run om door te zetten)")
        return 0

    ok_index = write_with_safety(index_path, index_text, args.force, args.dry_run)
    ok_log = write_with_safety(log_path, log_text, args.force, args.dry_run)
    if not (ok_index and ok_log):
        return 2

    print(
        f"[ok] index.md geschreven: {index_path} "
        f"({idx_stats['categories']} categorieen, {idx_stats['wikilinks']} wikilinks)"
    )
    print(f"[ok] log.md geschreven:   {log_path} ({log_count} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

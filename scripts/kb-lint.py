#!/usr/bin/env python3
"""
kb-lint.py — provenance lint for KennisBank wiki articles.

Validates that every wiki article in 02-wiki/ carries traceable session
provenance. A compiled article without a working link to its raw session(s)
is not auditable: a hallucination during distillation then becomes a durable
"fact" that can never be checked against its source again.

Checks per article:

1. **missing** — no reference to a raw session at all
   (no ``[[raw-sessie-...]]`` wikilink and no path text).
2. **dangling** — a ``[[raw-sessie-...]]`` wikilink whose file does not exist
   in ``01-raw/sessies/`` or ``08-archive/``.
3. **path-only** — the only provenance is path text such as
   ``01-raw/sessies/raw-sessie-....md`` (backticks or prose). Path text is
   invisible to Obsidian backlinks and the knowledge graph; turn it into a
   wikilink.

Provenance counts in two forms: a ``[[raw-sessie-...]]`` wikilink (session
provenance) or an explicit ``[[05-bronnen/...]]`` wikilink (source
provenance, for articles that come from an import rather than a session).
References to memories or other articles are relations, not sources.
``index.md`` and ``log.md`` are structure files and are skipped.

Usage: python3 kb-lint.py [--json]

Exit codes (same convention as an evaluator):
  0 = all articles clean
  1 = error (vault or wiki directory not found)
  2 = warnings found
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

# Findings that REALLY break auditability (no traceable provenance, or
# provenance that comes from the system itself). In --strict mode these are
# fail-closed; path-only stays advisory (the link exists, just as path text
# instead of a wikilink).
#
# self-source (TASK-90 E6, the epistemic axis): an article that cites ANOTHER
# wiki article, a memory or a system file as its PROVENANCE is quoting a
# conclusion as evidence — the self-confirmation loop in which the system
# starts citing its own inferences as sources (llm_wiki #538 was the bug form
# of this: the wiki cited its own log file). No judge or stale check catches
# it; it looks like good knowledge. Hence a hard lint rule.
HARD_TYPES = ("missing", "dangling", "self-source")

#: Path prefixes that may never be provenance: synthesized knowledge (wiki),
#: distilled fragments (memory) and tooling/system files.
SELF_SOURCE_PREFIXES = ("02-wiki/", "09-memory/", ".claude/", "06-claude/")

#: The Sessie-herkomst section: from its heading to the next heading or EOF.
#: (The heading text is the Dutch vault's data format — do not translate.)
HERKOMST_SECTION_RE = re.compile(
    r"^##\s+Sessie-herkomst\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)

# [[target]], [[target|alias]], [[path/to/target#heading]]
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
# Path text pointing at a session log outside a wikilink (backticks or prose).
PATH_REF_RE = re.compile(r"01-raw[/\\]sessies[/\\](raw-sessie-[\w.-]+)")


def normalize_target(target: str) -> str:
    """Reduce a wikilink target to its bare file stem.

    Strips alias (``|``), heading anchor (``#``), path prefix and the ``.md``
    extension, so ``[[01-raw/sessies/raw-sessie-x.md|bron]]`` and
    ``[[raw-sessie-x]]`` yield the same stem.
    """
    target = target.split("|", 1)[0].split("#", 1)[0].strip()
    target = target.replace("\\", "/").rsplit("/", 1)[-1]
    if target.endswith(".md"):
        target = target[:-3]
    return target


#: Directories that never contain session logs: tooling/index output, plus
#: 05-bronnen (imported source documents, a separate provenance category
#: -- see resolving_bron_links() -- where a raw-sessie-*.md file never
#: belongs by vault convention). Measured on the real vault (2026-08-03,
#: TASK-130): 05-bronnen held 0 session stems across 58k+ files, and that
#: full recursive walk was 12s of kb-lint's 15.6s total cost.
SKIP_DIRS = {".claude", ".git", ".obsidian", "graphify-out", "05-bronnen"}


def collect_session_stems(root: Path) -> set[str]:
    """Collect the file stems of every known raw session.

    Vault-wide (the way Obsidian resolves wikilinks by file name): active
    sessions live in ``01-raw/sessies/``, but moved or archived sessions
    (``01-raw/debug/``, ``08-archive/``, ...) remain valid provenance as
    long as the file exists somewhere in the vault -- except under
    SKIP_DIRS, where by convention a session log never belongs.

    os.walk with directory pruning, not rglob: rglob always descends fully
    and filters only on the result, so it would still traverse the excluded
    directories completely (TASK-130 -- 05-bronnen alone cost 12s that way).
    """
    stems: set[str] = set()
    suffix = ".md"
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.startswith(SESSION_PREFIX) and name.endswith(suffix):
                stems.add(name[:-len(suffix)])
    return stems


def _clean_target(target: str) -> str:
    """Strip alias and heading anchor from a wikilink target, keep the path."""
    return target.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/")


def resolving_bron_links(text: str, root: Path) -> tuple[list, list]:
    """(resolving, dangling) for explicit [[05-bronnen/...]] wikilinks.

    Source provenance for articles that come from an import (e.g. Evernote)
    rather than a session. Only path-style links starting with
    ``05-bronnen/`` count; bare article links remain relations.
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
    """Lint one article. Returns a list of findings (empty = clean).

    Every finding is ``{"file": str, "type": str, "detail": str}`` with type
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

    # Path references outside wikilinks: cut every wikilink out first, only
    # then look for loose path text.
    text_without_links = WIKILINK_RE.sub("", text)
    path_refs = PATH_REF_RE.findall(text_without_links)

    findings: list[dict] = []
    # E6: conclusions are not evidence. Only links INSIDE the
    # Sessie-herkomst section count; an [[other-article]] under ## Verbanden
    # is a relation and stays allowed.
    m = HERKOMST_SECTION_RE.search(text)
    if m:
        for t2 in WIKILINK_RE.findall(m.group(1)):
            cleaned = _clean_target(t2)
            if cleaned.startswith(SELF_SOURCE_PREFIXES):
                findings.append({
                    "file": path.name,
                    "type": "self-source",
                    "detail": (f"provenance [[{cleaned}]] is synthesized knowledge or a "
                               "system file — a conclusion must never flow back in as "
                               "source/evidence (epistemic axis, TASK-90)"),
                })
    for target in dangling:
        findings.append({
            "file": path.name,
            "type": "dangling",
            "detail": f"dead provenance link [[{target}]]: file not found in the vault",
        })
    if not resolving:
        if path_refs:
            findings.append({
                "file": path.name,
                "type": "path-only",
                "detail": "provenance only as path text (invisible to backlinks and the knowledge graph); turn it into a [[raw-sessie-...]] wikilink",
            })
        elif not dangling:
            findings.append({
                "file": path.name,
                "type": "missing",
                "detail": "no provenance: no [[raw-sessie-...]] or [[05-bronnen/...]] reference",
            })
    return findings


def lint_index_drift(root: Path) -> list:
    """Ghost docs in kb-index.db: indexed paths that no longer exist.

    Index drift is the best-confirmed failure mode of the LLM-wiki field
    (three independent observations: llm_wiki #580, Pratiyush
    ``index_sync``, Arkon's dashboard-vs-linter count mismatch): the
    catalogue silently diverges from reality and nobody notices. Here the
    index is a throwaway cache, so drift is advisory (a rebuild fixes it) —
    but it must be VISIBLE. Fail-soft: no db or a sqlite error -> [].
    """
    import sqlite3
    db = root / ".claude" / "kb-index.db"
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        paths = [r[0] for r in conn.execute("SELECT path FROM docs").fetchall()]
        conn.close()
    except Exception:
        return []
    ghosts = [p for p in paths if not Path(p).exists()]
    if not ghosts:
        return []
    example = Path(ghosts[0]).name
    return [{
        "file": "kb-index.db",
        "type": "index-drift",
        "detail": (f"{len(ghosts)} indexed doc(s) no longer exist on disk "
                   f"(e.g. {example}); run build-kb-index.py to prune"),
    }]


def lint_vault(root: Path) -> dict:
    """Lint every wiki article under ``root``. Returns the report dict."""
    wiki_dir = root / "02-wiki"
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"wiki directory not found: {wiki_dir}")

    stems = collect_session_stems(root)
    warnings: list[dict] = []
    articles = 0
    for f in sorted(wiki_dir.glob("*.md")):
        if f.name in SKIP_FILES:
            continue
        articles += 1
        warnings.extend(lint_article(f, stems, root))
    warnings.extend(lint_index_drift(root))

    # index-drift is not an article finding; it does not count toward
    # warned/clean (otherwise "clean" could go negative on an empty wiki).
    warned_files = {w["file"] for w in warnings if w["type"] != "index-drift"}
    hard = sum(1 for w in warnings if w["type"] in HARD_TYPES)
    return {
        "articles": articles,
        "clean": articles - len(warned_files),
        "warned": len(warned_files),
        "hard": hard,          # count of missing/dangling findings (fail-closed in --strict)
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provenance lint for KennisBank wiki articles."
    )
    parser.add_argument(
        "--json", action="store_true",
        help="machine-readable JSON output (for doctor.sh)",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="fail closed on missing/dangling (exit 2); path-only stays advisory (exit 0). "
             "For gate use: the /wiki hard stop and the doctor FAIL tier.",
    )
    args = parser.parse_args()

    root = vault_root()
    try:
        report = lint_vault(root)
    except FileNotFoundError as exc:
        # Fail-open on an operational error (no vault): exit 1, no false
        # block. A gate calling kb-lint must treat exit 1 as "could not
        # check", not as "provenance broken".
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        for w in report["warnings"]:
            hard = " [HARD]" if w["type"] in HARD_TYPES else ""
            print(f"[WARN]{hard} 02-wiki/{w['file']}: {w['detail']}")
        print(
            f"Summary: {report['articles']} articles, "
            f"{report['warned']} with warnings ({report['hard']} hard), "
            f"{report['clean']} clean"
        )

    # Exit contract:
    #   1 = operational error (no vault) — handled above
    #   --strict: 2 only on hard (missing/dangling); path-only = 0 (advisory)
    #   default:  2 on any warning at all; 0 = clean
    if args.strict:
        return 2 if report["hard"] else 0
    return 2 if report["warnings"] else 0


if __name__ == "__main__":
    sys.exit(main())

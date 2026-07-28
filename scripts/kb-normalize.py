#!/usr/bin/env python3
"""kb-normalize.py - deterministic post-pass after LLM writes (TASK-90 E3).

llm_wiki #576 was a natural experiment: in the same file, the frontmatter the
app corrected deterministically was always right, and the body the prompt was
told to keep intact was always wrong. Lesson: never ask the model for what
code can enforce. This post-pass normalizes structural FORM after every LLM
write in /wiki and /reconcile — it never touches content.

Normalizations (all idempotent; two runs are byte-identical):
  1. Wikilink targets: backslashes -> forward slashes; path-prefixed targets
     reduced to the bare stem (``[[clients/foo-overview.md|x]]`` ->
     ``[[foo-overview|x]]``), matching how Obsidian resolves by filename and
     what /wiki step 4 prescribes. EXCEPTION: ``05-bronnen/...`` keeps its
     path — kb-lint's bron-herkomst contract requires that prefix.
     Aliases (``|``) and heading anchors (``#``) are preserved.
  2. Frontmatter ``tags``: a bare comma string (``tags: a, b``) becomes the
     canonical inline list (``tags: [a, b]``). Already-listed tags untouched.

Exit: 0 = done (summary on stdout), 1 = file unreadable, 2 = --check found
pending changes (for gate use).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
TAGS_BARE_RE = re.compile(r"^(tags:\s*)([^\[\n][^\n]*?)\s*$", re.MULTILINE)
_FENCE_RE = re.compile(r"^---\s*$", re.MULTILINE)


def normalize_link_inner(inner: str) -> str:
    """Normaliseer de binnenkant van één [[wikilink]] (vorm, geen betekenis)."""
    target, sep, alias = inner.partition("|")
    target = target.strip().replace("\\", "/")
    base, hash_sep, anchor = target.partition("#")
    if not base.startswith("05-bronnen/"):
        if "/" in base:
            base = base.rsplit("/", 1)[-1]
        if base.endswith(".md"):
            base = base[:-3]
    new_target = base + (hash_sep + anchor if hash_sep else "")
    return new_target + ((sep + alias.strip()) if sep else "")


def normalize_body(body: str) -> str:
    return WIKILINK_RE.sub(lambda m: f"[[{normalize_link_inner(m.group(1))}]]", body)


def normalize_tags_line(fm: str) -> str:
    """``tags: a, b`` -> ``tags: [a, b]``; lijsten en lege waarden ongemoeid."""
    def repl(m):
        value = m.group(2).strip()
        if not value or value.startswith("["):
            return m.group(0)
        items = [t.strip() for t in value.split(",") if t.strip()]
        return m.group(1) + "[" + ", ".join(items) + "]"
    return TAGS_BARE_RE.sub(repl, fm)


def normalize_text(text: str) -> str:
    """Byte-behoudend buiten de genormaliseerde plekken: de tekst wordt in een
    frontmatter-deel en een body-deel gesneden op de bestaande fence (zelfde
    regex-anker als _frontmatter) en alleen die slices worden getransformeerd —
    nooit hersamengesteld uit geparste onderdelen (dat zou witruimte muteren).
    Wikilinks in het frontmatter-deel (bv. gequote superseded_by) blijven
    bewust ongemoeid."""
    if text.startswith("---"):
        m = _FENCE_RE.search(text, 3)
        if m:
            head, tail = text[:m.end()], text[m.end():]
            return normalize_tags_line(head) + normalize_body(tail)
    return normalize_body(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="deterministische vorm-normalisatie na een LLM-schrijfstap")
    parser.add_argument("files", nargs="+", help="markdown-bestand(en)")
    parser.add_argument("--check", action="store_true",
                        help="alleen melden (exit 2 bij pending wijzigingen)")
    args = parser.parse_args(argv)
    changed = 0
    for f in args.files:
        p = Path(f)
        try:
            before = p.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"kb-normalize: {f}: {exc}", file=sys.stderr)
            return 1
        after = normalize_text(before)
        if after != before:
            changed += 1
            if args.check:
                print(f"kb-normalize: {f}: normalisatie nodig")
            else:
                p.write_text(after, encoding="utf-8")
                print(f"kb-normalize: {f}: genormaliseerd")
    if not changed:
        print("kb-normalize: geen wijzigingen")
    return 2 if (args.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())

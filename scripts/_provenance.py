#!/usr/bin/env python3
"""_provenance.py - source keys per document for the coupling signal (TASK-88).

Bibliographic coupling (Kessler 1963) needs one thing before it can rank:
a queryable "which sources does this doc derive from" per document. This
module extracts that at INDEX TIME (build-kb-index, off the hot path):

- memory: the ``source_session`` frontmatter field (transcript filename,
  written by memory-sweep) — one key per fragment.
- wiki: every provenance wikilink in the body — ``[[raw-sessie-...]]``
  session links plus explicit ``[[05-bronnen/...]]`` source links.

PARSING CONTRACT: wiki provenance is whatever ``kb-lint.py`` accepts as
provenance, nothing more and nothing less. To make drift impossible this
module imports kb-lint's own regex and normalizers via importlib instead of
re-implementing them; ``tests/test_provenance_sources.py`` additionally locks
both parsers to the same fixtures.

Namespace note: memory keys are transcript filenames, wiki keys are session
log stems. They deliberately do not join across layers — the hook never fuses
the layers either, so coupling only ever weighs wiki<->wiki and
memory<->memory. A transcript<->sessionlog mapping is YAGNI until a
measurement asks for it.

Pure stdlib + kb-lint; no vault I/O beyond what the caller hands in.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

_here = os.path.dirname(os.path.abspath(__file__))


def _load_kb_lint():
    spec = importlib.util.spec_from_file_location(
        "kb_lint", os.path.join(_here, "kb-lint.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_lint = _load_kb_lint()


def _norm_bron(target: str) -> str:
    """Normaliseer een 05-bronnen-pad tot een stabiele join-sleutel:
    forward slashes, alias/anker eraf (via kb-lint), zonder .md-extensie."""
    t = _lint._clean_target(target)
    if t.endswith(".md"):
        t = t[:-3]
    return t


def doc_sources(path: Path, layer: str, fm: dict, body: str) -> list:
    """Herleidbare bron-sleutels voor één document, gededupliceerd, gesorteerd.

    memory -> [basename van source_session] (leeg veld -> []).
    wiki   -> alle [[raw-sessie-*]]-stems + genormaliseerde [[05-bronnen/...]]-paden.
    Andere lagen -> [].
    """
    if layer == "memory":
        src = str(fm.get("source_session", "")).strip()
        if not src:
            return []
        return [Path(src.replace("\\", "/")).name]
    if layer != "wiki":
        return []
    keys = set()
    for t in _lint.WIKILINK_RE.findall(body or ""):
        stem = _lint.normalize_target(t)
        if stem.startswith(_lint.SESSION_PREFIX):
            keys.add(stem)
            continue
        cleaned = _lint._clean_target(t)
        if cleaned.replace("\\", "/").startswith("05-bronnen/"):
            keys.add(_norm_bron(t))
    return sorted(keys)

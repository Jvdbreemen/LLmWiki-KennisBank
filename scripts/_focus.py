#!/usr/bin/env python3
"""_focus.py - the shared current_focus block (TASK-201).

One small block that answers "what is being worked on right now" for every
client at SessionStart. Adopted from the Eaves review with its scoping
inverted: Eaves keeps per-agent focus blocks because its agents are different
personas; KennisBank has one subject -- the vault owner's work -- so the same
tier is more valuable shared. Each client used to rediscover the active state
from scratch; this block is the mechanism by which three clients stop
behaving like three systems over one vault.

Scope discipline, by design and guarded by tests (test_focus.py):

  - ONE file (<vault>/.claude/current-focus.md), hard character cap.
  - Replaced wholesale on every write. A running summary that grows is a log,
    and the vault already has a log. No history is kept here.
  - Written OFF the hot path, by the sweep (memory-sweep.py), local model
    only via the _llm seam. Never at session start, never per prompt.
  - Not indexed, not retrievable, no rank factor. The file lives under
    .claude/, which no index builder scans. If this block ever needs a rank
    factor it has become a second memory layer, and that is explicitly not
    this design.
  - Silent when nothing is active: no recent sessions -> empty file -> the
    notify side emits nothing at all (principle #4).

Fail-soft: a dead model or an unparseable answer keeps the previous block.
An outage may never erase working state.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

#: Hard cap, from Eaves' core-memory blocks. Enough for "projects, threads,
#: decisions in flight, next steps"; anything longer is a document.
FOCUS_MAX_CHARS = 2000

#: Sessions older than this cannot claim to describe the CURRENT focus.
FOCUS_WINDOW_DAYS = 7

#: How many of the newest session logs feed the summary. More adds history,
#: and history is what the block deliberately is not.
FOCUS_MAX_SOURCES = 3

FOCUS_NAME = "current-focus.md"

FOCUS_SYSTEM = (
    "You maintain a tiny 'current focus' note for a knowledge worker. From "
    "the session log excerpts, write what is actively being worked on RIGHT "
    "NOW: projects, open threads, decisions in flight, and concrete next "
    "steps. Write in the language the excerpts use. Plain text, at most "
    "1500 characters, no headings, no preamble. If the excerpts show no "
    "active work, answer with exactly: NIETS_ACTIEF"
)


def focus_path() -> Path:
    return vault_root() / ".claude" / FOCUS_NAME


def read_focus() -> str:
    """The current block, or "" when absent/blank. Fail-open."""
    try:
        return focus_path().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _recent_sessions() -> list:
    """The newest session logs inside the window, newest first."""
    sdir = vault_root() / "01-raw" / "sessies"
    if not sdir.exists():
        return []
    cutoff = (date.today() - timedelta(days=FOCUS_WINDOW_DAYS)).isoformat()
    rows = []
    for f in sdir.glob("raw-sessie-*.md"):
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        created = str(fm.get("created", ""))[:10]
        if created >= cutoff:
            rows.append((created, f, body))
    rows.sort(key=lambda t: t[0], reverse=True)
    return rows[:FOCUS_MAX_SOURCES]


def _looks_inactive(text: str) -> bool:
    t = text.strip()
    if not t or "NIETS_ACTIEF" in t:
        return True
    low = t.lower()
    # The extraction seam's refusal heuristic, inlined for the same reason it
    # exists there: refusal prose written into the block would be injected
    # into every session start until the next sweep.
    return low.startswith(("i cannot", "i can't", "i'm sorry", "sorry,"))


def update_focus() -> bool:
    """Rewrite the block from the newest session logs. Returns True on write.

    No recent sessions -> the block is emptied WITHOUT consulting the model:
    there is nothing to summarise, and an empty block is the designed silence.
    A dead or refusing model keeps the previous block untouched.
    """
    p = focus_path()
    rows = _recent_sessions()
    try:
        if not rows:
            if read_focus():
                p.write_text("", encoding="utf-8")
            elif not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("", encoding="utf-8")
            return True
        import _llm
        excerpts = "\n\n---\n\n".join(
            f"[{created}] {f.stem}\n{body[:2500]}" for created, f, body in rows)
        raw = _llm.generate(f"SESSION LOG EXCERPTS:\n\n{excerpts}\n\nCurrent focus:",
                            system=FOCUS_SYSTEM)
        if not raw or _looks_inactive(raw):
            if raw and "NIETS_ACTIEF" in raw:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("", encoding="utf-8")
                return True
            return False  # outage or refusal: keep the previous block
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(raw.strip()[:FOCUS_MAX_CHARS], encoding="utf-8")
        return True
    except Exception:
        return False

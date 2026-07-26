#!/usr/bin/env python3
"""kb-orientation.py — compact vault orientation at session start (TASK-80).

Borrowed from Mind's space_get: a cheap "what lives in this vault" summary as
first context for an agent. Pure SQL reads on kb-index.db and kb-usage.db plus
a filename scan of backlog/tasks in the session cwd — no embeddings, no LLM,
sub-second by construction.

Modes:
* no arguments: print the orientation as plain text (used by /sessiestart).
* --hook: emit SessionStart additionalContext JSON, gated on the opt-in
  toggle ``orientation`` (default off). Runs in the coordinator's
  NOTIFICATIONS phase, so it inherits the freshness gate — orientation is
  routine context, not an urgent notice.

FAIL-OPEN, ALWAYS: any error exits 0 and prints nothing (hook mode) or a
partial summary (CLI mode). Stdlib-only (ADR-0002).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

RECENT_N = 5
TRENDING_N = 3
TRENDING_WINDOW_DAYS = 14


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.5)


def index_lines(vault: Path) -> list[str]:
    """Counts per layer and most recently created wiki articles."""
    lines: list[str] = []
    db = vault / ".claude" / "kb-index.db"
    if not db.exists():
        return lines
    try:
        conn = _ro(db)
        try:
            layers = conn.execute(
                "SELECT layer, count(*) FROM docs GROUP BY layer ORDER BY layer"
            ).fetchall()
            if layers:
                lines.append("inhoud: " + ", ".join(f"{n} {layer}" for layer, n in layers))
            recent = conn.execute(
                "SELECT title, created FROM docs WHERE layer='wiki' "
                "ORDER BY created DESC, doc_id DESC LIMIT ?", (RECENT_N,)
            ).fetchall()
            if recent:
                lines.append("recent gewijzigd: " + "; ".join(
                    f"{title} ({created})" for title, created in recent if title))
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return lines


def trending_lines(vault: Path) -> list[str]:
    """Most-used injected knowledge in the recent window (kb-usage.db)."""
    db = vault / ".claude" / "kb-usage.db"
    if not db.exists():
        return []
    try:
        conn = _ro(db)
        try:
            rows = conn.execute(
                "SELECT stem FROM usage "
                "WHERE last_injected >= date('now', ?) AND used > 0 "
                "ORDER BY used DESC, injected DESC LIMIT ?",
                (f"-{TRENDING_WINDOW_DAYS} day", TRENDING_N),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    if not rows:
        return []
    return ["veel gebruikt: " + "; ".join(stem for (stem,) in rows)]


def backlog_lines(cwd: Path) -> list[str]:
    """Open backlog tasks in the session cwd, if it uses Backlog.md."""
    tasks_dir = cwd / "backlog" / "tasks"
    if not tasks_dir.is_dir():
        return []
    counts = {"To Do": 0, "In Progress": 0}
    try:
        for path in tasks_dir.glob("task-*.md"):
            try:
                head = path.read_text(encoding="utf-8", errors="replace")[:2000]
            except OSError:
                continue
            match = re.search(r"^status:\s*(.+?)\s*$", head, re.M | re.I)
            if match and match.group(1) in counts:
                counts[match.group(1)] += 1
    except OSError:
        return []
    open_total = sum(counts.values())
    if not open_total:
        return []
    return [f"backlog hier: {counts['In Progress']} in progress, {counts['To Do']} to do"]


def orientation(vault: Path, cwd: Path) -> str:
    lines = index_lines(vault) + trending_lines(vault) + backlog_lines(cwd)
    if not lines:
        return ""
    return "\n".join(f"- {line}" for line in lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if not sys.stdin.isatty():
            try:
                sys.stdin.read()
            except OSError:
                pass
        vault = vault_root()
        text = orientation(vault, Path.cwd())
        if argv and argv[0] == "--hook":
            try:
                import _settings
                enabled = _settings.get("orientation", False)
            except Exception:
                enabled = False
            if enabled and text:
                sys.stdout.write(json.dumps({
                    "suppressOutput": True,
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": f"KennisBank orientatie:\n{text}",
                    },
                }))
            return 0
        if text:
            print(text)
    except Exception as exc:  # noqa: BLE001 — session start must never depend on this
        print(f"[kb-orientation] unexpected: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)

#!/usr/bin/env python3
"""Read-only aggregate report joining exposure and outcome ledgers."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _outcome_report import correlate  # noqa: E402


def _rows(path, query):
    if not path.is_file():
        return []
    conn = None
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query).fetchall()]
    except sqlite3.Error:
        return []
    finally:
        if conn is not None:
            conn.close()


def build_report(vault: Path) -> dict:
    usage_path = Path(vault) / ".claude" / "kb-usage.db"
    experience_path = Path(vault) / ".claude" / "kb-experience.db"
    exposures = _rows(
        usage_path,
        "SELECT session_id, task_id, item_id, layer FROM exposures")
    outcomes = _rows(
        experience_path,
        "SELECT session_id, task_id, state FROM experience_outcomes")
    return correlate(exposures, outcomes)


def main() -> int:
    vault = Path(os.environ.get("KENNISBANK_VAULT", "."))
    print(json.dumps(build_report(vault), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

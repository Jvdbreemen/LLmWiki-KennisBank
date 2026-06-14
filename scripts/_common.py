"""Shared helpers for the KennisBank importer scripts.

Single source of truth for the small utilities that were duplicated verbatim
across ``import-folder.py``, ``import-claudeai-export.py`` and
``import-cc-history.py``:

- :func:`slugify` — filename-safe slug from arbitrary text.
- :func:`_utcnow_iso` / :func:`_today_iso` — UTC timestamp helpers.
- :func:`print_summary` — render the import summary (JSON or one-line text).

Stdlib only. No hyphen in the filename so the scripts can ``import`` it after
``sys.path.insert`` (the same trick used for ``_frontmatter.py`` /
``_vaultpath.py``).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone


def slugify(text: str, max_len: int = 50) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        return "untitled"
    return text[:max_len].rstrip("-") or "untitled"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def print_summary(summary: dict, as_json: bool) -> None:
    """Print the import summary the same way all three importers always did.

    ``summary`` is the dict with ``imported`` / ``skipped`` / ``errors`` /
    ``files`` / ``errors_detail`` keys. When ``as_json`` is true the full dict
    is dumped as indented JSON; otherwise a single ``--- summary: ...`` line is
    printed. Byte-faithful to the previous inline blocks.
    """
    if as_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(
            f"--- summary: imported={summary['imported']} "
            f"skipped={summary['skipped']} errors={summary['errors']}"
        )

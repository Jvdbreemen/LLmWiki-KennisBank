#!/usr/bin/env python3
"""_memory.py - format van de ruwe geheugenlaag (09-memory/).

Pure stdlib-bibliotheek: rendert en pareert memory-markdown met frontmatter,
en bouwt paden. Geen netwerk, geen embeddings, geen side-effects bij import.
Underscore-naam zodat scripts het importeren na sys.path.insert (idem _settings).

Frontmatter-contract (spec fase 1):
    title: vrije tekst (verplicht)
    type: memory
    status: unverified | current | superseded | retracted | expired
    evidence_basis: getypt | cc-sessie | audio | import | autoresearch | agent
    source_session, created, updated, expires?, superseded_by?, tags
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import slugify, _today_iso  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

STATUSES = ("unverified", "current", "superseded", "retracted", "expired")
EVIDENCE_BASES = ("getypt", "cc-sessie", "audio", "import", "autoresearch", "agent")
DEFAULT_STATUS = "unverified"
DEFAULT_EVIDENCE = "cc-sessie"


def memory_dir() -> Path:
    return vault_root() / "09-memory"


def memory_path(title: str, created: str | None = None) -> Path:
    date = created or _today_iso()
    return memory_dir() / f"{date}-{slugify(title)}.md"


def unique_memory_path(title: str, created: str | None = None) -> Path:
    """memory_path met collision-guard: voegt -2,-3,.. toe tot het pad vrij is."""
    base = memory_path(title, created)
    if not base.exists():
        return base
    stem, suffix, parent = base.stem, base.suffix, base.parent
    n = 2
    while True:
        cand = parent / f"{stem}-{n}{suffix}"
        if not cand.exists():
            return cand
        n += 1


def _yaml_scalar(s) -> str:
    """Veilige double-quoted scalar voor de minimale frontmatter-parser.
    Sanitize i.p.v. escape (de parser kent geen escapes): embedded quotes ->
    enkele quote, newlines -> spatie."""
    s = str(s).replace('"', "'").replace("\n", " ").replace("\r", " ").strip()
    return f'"{s}"'


def _yaml_list(items) -> str:
    if isinstance(items, str):
        items = [items]
    safe = [str(i).replace("\n", " ").strip() for i in (items or [])]
    return "[" + ", ".join(safe) + "]"


def render(title: str, body: str, *, status: str = DEFAULT_STATUS,
           evidence_basis: str = DEFAULT_EVIDENCE, source_session: str = "",
           created: str | None = None, updated: str | None = None,
           expires: str | None = None, superseded_by=None, tags=None) -> str:
    if status not in STATUSES:
        raise ValueError(f"ongeldige status: {status!r} (verwacht een van {STATUSES})")
    if evidence_basis not in EVIDENCE_BASES:
        raise ValueError(f"ongeldige evidence_basis: {evidence_basis!r}")
    created = created or _today_iso()
    updated = updated or created
    lines = ["---",
             f"title: {_yaml_scalar(title)}",
             "type: memory",
             f"status: {status}",
             f"evidence_basis: {evidence_basis}",
             f"source_session: {_yaml_scalar(source_session)}",
             f"created: {created}",
             f"updated: {updated}"]
    if expires:
        lines.append(f"expires: {expires}")
    if superseded_by:
        lines.append(f"superseded_by: {_yaml_list(superseded_by)}")
    lines.append(f"tags: {_yaml_list(tags or [])}")
    lines.append("---")
    lines.append("")
    lines.append(body.rstrip() + "\n")
    return "\n".join(lines)


def write(title: str, body: str, **kw) -> Path:
    created = kw.get("created")
    p = memory_path(title, created)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(title, body, **kw), encoding="utf-8")
    return p


def read_status(path) -> str:
    try:
        fm, _ = parse_frontmatter(Path(path).read_text(encoding="utf-8"))
        status = fm.get("status")
        return status if status in STATUSES else DEFAULT_STATUS
    except Exception:
        return DEFAULT_STATUS

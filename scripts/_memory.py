#!/usr/bin/env python3
"""_memory.py - format van de ruwe geheugenlaag (09-memory/).

Pure stdlib-bibliotheek: rendert en pareert memory-markdown met frontmatter,
en bouwt paden. Geen netwerk, geen embeddings, geen side-effects bij import.
Underscore-naam zodat scripts het importeren na sys.path.insert (idem _settings).

Frontmatter-contract (spec fase 1, bi-temporeel uitgebreid):
    title: vrije tekst (verplicht)
    type: memory
    memory_type: feit | voorkeur | procedure | beslissing
    importance: 1-5 (judge-oordeel bij capture; 3 = neutraal)
    status: unverified | current | superseded | retracted | expired
    evidence_basis: getypt | cc-sessie | audio | import | autoresearch | agent
    source_session, created, updated, expires?, superseded_by?, tags
    valid_from: vanaf wanneer het feit geldt (event-tijd; default = created).
        Bewust apart van created (capture-tijd): een laat geïmporteerd
        transcript levert een feit dat al eerder gold.
    valid_until?: tot wanneer het feit gold. Gezet bij superseden en
        expiren; een memory zonder valid_until is open-einde geldig.
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
# Kennistypes verouderen verschillend: een beslissing heeft lange geldigheid
# met expliciete supersession, een voorkeur is zachter, een procedure is
# stabiel tot de tooling wijzigt, een feit tot de wereld wijzigt. Het type
# maakt verval en retrieval per soort differentieerbaar (CrewAI/Cognee-les).
MEMORY_TYPES = ("feit", "voorkeur", "procedure", "beslissing")
DEFAULT_STATUS = "unverified"
DEFAULT_EVIDENCE = "cc-sessie"
DEFAULT_MEMORY_TYPE = "feit"


def coerce_memory_type(value) -> str:
    """Sanitize een (LLM-geleverd) memory-type; onbekend -> 'feit'."""
    v = str(value or "").strip().lower()
    return v if v in MEMORY_TYPES else DEFAULT_MEMORY_TYPE


def coerce_importance(value) -> int:
    """Sanitize importance naar 1..5; onparseerbaar -> neutraal 3."""
    try:
        imp = int(value)
    except (TypeError, ValueError):
        return 3
    return min(5, max(1, imp))


# Herkomst-klassen voor de injectie-tag (TASK-20). Puur presentatie: mapt
# (evidence_basis, status) op een korte, deterministische herkomst-tag zodat
# het consumerende model mens-herkomst autoritatief leest en autonoom/onbevestigd
# als hint. Geen nieuw frontmatter-veld, geen LLM. 'getypt' = mens typte letterlijk
# (autoritatief, geen kwalificatie); cc-sessie/import/autoresearch/audio = mens-in-lus
# (autoritatief); agent = autonoom geextraheerd (hint).
_HUMAN_IN_LOOP_BASES = ("cc-sessie", "import", "autoresearch", "audio")


def provenance_tag(evidence_basis, status="") -> str:
    """Korte deterministische herkomst/status-tag voor een geinjecteerde memory.

    Twee ORTHOGONALE assen, bewust gescheiden (TASK-20):
      - herkomst-as (wie/hoe vastgelegd): getypt = geen marker (autoritatief);
        cc-sessie/import/autoresearch/audio = "mens-in-lus"; agent = "autonoom" (hint).
      - status-as (is het geverifieerd): status=unverified voegt ", onbevestigd" toe,
        ongeacht de herkomst. "onbevestigd" trackt dus UITSLUITEND de status, niet de
        herkomst -- een agent-memory met status=current is judge-geverifieerd en heet
        daarom NIET onbevestigd, wel "autonoom".

    Vormen:
        getypt (current)     -> "(bron: getypt)"
        cc-sessie (current)  -> "(bron: cc-sessie, mens-in-lus)"
        agent (current)      -> "(bron: agent, autonoom)"
        agent (unverified)   -> "(bron: agent, autonoom, onbevestigd)"
        getypt (unverified)  -> "(bron: getypt, onbevestigd)"

    Fail-soft: onbekende/ontbrekende evidence_basis -> "" (geen tag, nooit crash).
    """
    basis = str(evidence_basis or "").strip().lower()
    stat = str(status or "").strip().lower()
    if basis not in EVIDENCE_BASES:
        return ""
    quals = []
    if basis == "getypt":
        pass  # mens typte letterlijk -> autoritatief, geen herkomst-marker
    elif basis == "agent":
        quals.append("autonoom")  # autonoom geextraheerd -> hint (origin-as, niet status)
    elif basis in _HUMAN_IN_LOOP_BASES:
        quals.append("mens-in-lus")  # mens-in-lus -> autoritatief
    if stat == "unverified":
        quals.append("onbevestigd")  # status-as: los van de herkomst
    inner = "bron: " + basis
    if quals:
        inner += ", " + ", ".join(quals)
    return f"({inner})"


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
           valid_from: str | None = None, valid_until: str | None = None,
           expires: str | None = None, superseded_by=None, tags=None,
           memory_type: str = DEFAULT_MEMORY_TYPE, importance: int = 3) -> str:
    if status not in STATUSES:
        raise ValueError(f"ongeldige status: {status!r} (verwacht een van {STATUSES})")
    if evidence_basis not in EVIDENCE_BASES:
        raise ValueError(f"ongeldige evidence_basis: {evidence_basis!r}")
    if memory_type not in MEMORY_TYPES:
        raise ValueError(f"ongeldig memory_type: {memory_type!r} (verwacht een van {MEMORY_TYPES})")
    importance = coerce_importance(importance)
    created = created or _today_iso()
    updated = updated or created
    valid_from = valid_from or created
    lines = ["---",
             f"title: {_yaml_scalar(title)}",
             "type: memory",
             f"memory_type: {memory_type}",
             f"importance: {importance}",
             f"status: {status}",
             f"evidence_basis: {evidence_basis}",
             f"source_session: {_yaml_scalar(source_session)}",
             f"created: {created}",
             f"updated: {updated}",
             f"valid_from: {valid_from}"]
    if valid_until:
        lines.append(f"valid_until: {valid_until}")
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


def set_status(path, status: str, superseded_by=None, valid_until: str | None = None) -> bool:
    """Herschrijf de status-regel binnen het frontmatter-blok; optioneel een
    superseded_by-link en/of valid_until (bi-temporele sluiting) zetten.
    Return True als het bestand gewijzigd is.
    Mutatie alleen binnen het frontmatter (tussen de eerste twee --- fences).
    Fail-soft: return False bij ongeldige status of OSError."""
    import re
    if status not in STATUSES:
        return False
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return False
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return False
    fm = parts[1]
    # Replacement altijd via een lambda: een string-replacement interpreteert
    # backslashes als regex-escapes (re.PatternError op bv. een pad of "\x").
    new_fm = re.sub(r"^status:.*$", lambda _m: f"status: {status}",
                    fm, count=1, flags=re.MULTILINE)
    if superseded_by:
        link = "[" + ", ".join(f"[[{s}]]" for s in superseded_by) + "]"
        if re.search(r"^superseded_by:.*$", new_fm, flags=re.MULTILINE):
            new_fm = re.sub(r"^superseded_by:.*$", lambda _m: f"superseded_by: {link}",
                            new_fm, count=1, flags=re.MULTILINE)
        else:
            new_fm = new_fm.rstrip("\n") + f"\nsuperseded_by: {link}\n"
    if valid_until:
        if re.search(r"^valid_until:.*$", new_fm, flags=re.MULTILINE):
            new_fm = re.sub(r"^valid_until:.*$", lambda _m: f"valid_until: {valid_until}",
                            new_fm, count=1, flags=re.MULTILINE)
        else:
            new_fm = new_fm.rstrip("\n") + f"\nvalid_until: {valid_until}\n"
    new_raw = parts[0] + "---" + new_fm + "---" + parts[2]
    if new_raw == raw:
        return False
    try:
        p.write_text(new_raw, encoding="utf-8")
    except OSError:
        return False
    return True

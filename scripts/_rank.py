#!/usr/bin/env python3
"""_rank.py - retrieval-scoring: relevance x recency x importance + graafbuur.

Generative-Agents-stijl re-ranking voor de recall-route (kb-recall):

- relevance: de hybride RRF-score uit _kbindex.search (ongewijzigd);
- recency: exponentieel verval op de memory-laag, met halfwaardetijd per
  memory_type (een beslissing veroudert trager dan een voorkeur) en een
  vloer zodat oud-maar-relevant nooit verdwijnt;
- importance: 1-5, door de judge toegekend bij capture; neutraal 3 = x1.0.

Alleen de MEMORY-laag krijgt recency/importance-weging. De wiki-laag is
gecureerd (stale-check bewaakt veroudering daar) en blijft ongewogen.

Derde signaal: one_hop_neighbor() kiest de meest-verwezen wiki-buur
(wikilink) vanuit de hit-artikelen, zodat de evidence pack een coherente
kennisbuurt wordt in plaats van losse hits. Buren worden ALLEEN toegevoegd,
nooit boven directe hits gerangschikt.

Pure functies, stdlib; de frontmatter-reader is injecteerbaar voor tests.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

#: Halfwaardetijd (dagen) per memory_type. Een voorkeur is zachter dan een
#: feit; een beslissing geldt tot een supersession en vervalt het traagst.
HALF_LIFE_DAYS = {"feit": 365, "voorkeur": 180, "procedure": 365, "beslissing": 730}
DEFAULT_HALF_LIFE = 365
#: Vloer op het recency-verval: oud-maar-relevant blijft vindbaar.
RECENCY_FLOOR = 0.6

_WIKILINK_RE = re.compile(r"\[\[([^\[\]|#]+)")


def _age_days(iso_date: str, today: date) -> int:
    try:
        d = datetime.strptime(str(iso_date)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 0
    return max(0, (today - d).days)


def recency_factor(age_days: int, memory_type: str = "feit") -> float:
    """Exponentieel verval met type-specifieke halfwaardetijd, gevloerd."""
    if age_days <= 0:
        return 1.0
    hl = HALF_LIFE_DAYS.get(memory_type, DEFAULT_HALF_LIFE)
    return max(RECENCY_FLOOR, 0.5 ** (age_days / hl))


def importance_factor(importance) -> float:
    """1-5 -> 0.9..1.1 (neutraal 3 = 1.0). Onparseerbaar -> neutraal."""
    try:
        imp = int(importance)
    except (TypeError, ValueError):
        imp = 3
    imp = min(5, max(1, imp))
    return 1.0 + 0.05 * (imp - 3)


TRUST_RANK = {
    "getypt": 2,
    "cc-sessie": 1,
    "import": 1,
    "autoresearch": 1,
    "audio": 1,
    "agent": 0,
}


def trust_factor(evidence_basis) -> float:
    """Kleine trust-bonus over de bestaande evidence_basis-orden.

    getypt > mens-in-lus > agent, neutraal op onbekende waarden.
    """
    tier = TRUST_RANK.get(str(evidence_basis or ""), 1)
    return 1.0 + 0.05 * (tier - 1)


#: Gebruiks-boost: een document dat recent daadwerkelijk gebruikt is
#: (usage-telemetrie, kb-usage.db) is bewezen nuttig voor deze gebruiker.
USAGE_BOOST_RECENT = 1.10   # laatst gebruikt <= 30 dagen geleden
USAGE_BOOST_WARM = 1.05     # laatst gebruikt <= 90 dagen geleden


def usage_factor(last_used_iso: str, today: date | None = None) -> float:
    """Boost op recency-of-use. Nooit gebruikt of onbekend -> neutraal 1.0."""
    if not last_used_iso:
        return 1.0
    age = _age_days(last_used_iso, today or date.today())
    if age <= 30:
        return USAGE_BOOST_RECENT
    if age <= 90:
        return USAGE_BOOST_WARM
    return 1.0


def rerank(hits: list, meta_fn, today: date | None = None,
           last_used_fn=None) -> list:
    """Herweeg hits op relevance x recency x importance x usage, hersorteer.

    ``hits``: dicts met minstens ``path``, ``layer``, ``score``.
    ``meta_fn(path) -> dict``: frontmatter-reader (injecteerbaar).
    ``last_used_fn(stem) -> iso-datum``: usage-telemetrie-reader (optioneel);
    de gebruiks-boost geldt voor BEIDE lagen (een warm wiki-artikel is
    bewezen nuttig), recency/importance alleen voor de memory-laag.
    Geeft een NIEUWE lijst terug.
    """
    today = today or date.today()
    out = []
    for h in hits:
        score = h.get("score", 0.0)
        if h.get("layer") == "memory":
            try:
                fm = meta_fn(h.get("path", "")) or {}
            except Exception:
                fm = {}
            ref = fm.get("updated") or fm.get("valid_from") or fm.get("created") or ""
            score = (score
                     * recency_factor(_age_days(ref, today),
                                      fm.get("memory_type", "feit"))
                     * importance_factor(fm.get("importance", 3))
                     * trust_factor(fm.get("evidence_basis")))
        if last_used_fn is not None:
            try:
                score *= usage_factor(last_used_fn(Path(h.get("path", "")).stem), today)
            except Exception:
                pass
        out.append({**h, "score": score})
    out.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return out


def one_hop_neighbor(hits: list, root: Path, read_fn=None) -> str | None:
    """Meest-verwezen wiki-buur vanuit de wiki-hits die zelf geen hit is.

    Telt wikilinks in de hit-artikelen; alleen targets die als artikel in
    ``02-wiki/`` bestaan tellen (raw-sessies en memories zijn herkomst of
    verbanden, geen buur). Deterministische tie-break op naam. None als er
    geen kandidaat is.
    """
    read = read_fn or (lambda p: Path(p).read_text(encoding="utf-8", errors="replace"))
    wiki_dir = Path(root) / "02-wiki"
    hit_stems = {Path(h.get("path", "")).stem for h in hits}
    counts: Counter = Counter()
    for h in hits:
        if h.get("layer") != "wiki":
            continue
        try:
            text = read(h["path"])
        except Exception:
            continue
        for t in _WIKILINK_RE.findall(text):
            stem = t.strip().replace("\\", "/").rsplit("/", 1)[-1]
            if stem.endswith(".md"):
                stem = stem[:-3]
            if not stem or stem in hit_stems:
                continue
            if not (wiki_dir / f"{stem}.md").exists():
                continue
            counts[stem] += 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

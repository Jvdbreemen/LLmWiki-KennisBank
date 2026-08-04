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

Derde signaal: de graafbuur (kb-recall.graph_neighbor, TASK-87) kiest de
best-gewogen wiki-buur uit kb-graph.db, zodat de evidence pack een coherente
kennisbuurt wordt in plaats van losse hits. Buren worden ALLEEN toegevoegd,
nooit boven directe hits gerangschikt. De vroegere regex-scan hier
(one_hop_neighbor, N x read_text per call) is verwijderd nadat vier releases
zonder regressie op de graaf-default bevestigden dat hij overbodig was
(TASK-93).

Pure functies, stdlib; de frontmatter-reader is injecteerbaar voor tests.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

#: Halfwaardetijd (dagen) per memory_type. Een voorkeur is zachter dan een
#: feit; een beslissing geldt tot een supersession en vervalt het traagst.
HALF_LIFE_DAYS = {"feit": 365, "voorkeur": 180, "procedure": 365, "beslissing": 730}
DEFAULT_HALF_LIFE = 365
#: Vloer op het recency-verval: oud-maar-relevant blijft vindbaar.
RECENCY_FLOOR = 0.6


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


#: Noise-penalty (TASK-17, yesmem signed-patroon): een mens-gemarkeerd
#: ruis-document mag ONDER 1.0 zakken — begrensd, deterministisch, en
#: uitsluitend gevoed door expliciete markeringen (kb-noise.py).
NOISE_PENALTY = 0.20   # maximale aftrek bij 100% noise-rate
NOISE_FLOOR = 0.80     # anti-runaway ondergrens


def noise_factor(noise: int, injected: int) -> float:
    """Signed tegenhanger van usage_factor. Zonder markeringen exact 1.0
    (ranking identiek aan voorheen); met markeringen begrensd omlaag."""
    if noise <= 0 or injected <= 0:
        return 1.0
    return max(NOISE_FLOOR, 1.0 - NOISE_PENALTY * min(1.0, noise / injected))


#: Bibliographic-coupling-bonus (TASK-88): kandidaten die >=1 bron delen met
#: een ANDERE kandidaat in dezelfde resultaatset zijn coherenter met de vraag
#: dan losse treffers (Kessler 1963). Begrensd op het niveau van de usage-
#: warmte en nooit < 1.0 (coupling is een coherentie-bonus, geen straf).
#: Startwaarden bewust conservatief en NIET llm_wiki's 4.0/3.0/1.5/1.0 —
#: die gewichten zijn ongefundeerd handwerk; deze worden getuned via de
#: kb-eval A/B op de >=100-vraag-sets (bewijsregel TASK-86) en gepind door
#: tests/test_knob_consistency.py tegen CONFIGURATION.md.
COUPLING_BOOST_ONE = 1.05    # deelt >=1 bron met een andere kandidaat
COUPLING_BOOST_MULTI = 1.10  # deelt bronnen met >=2 andere kandidaten


def coupling_factor(shared_with: int) -> float:
    """Bonus op basis van het aantal ANDERE kandidaten met een gedeelde bron.
    0 -> neutraal 1.0; nooit onder 1.0."""
    if shared_with >= 2:
        return COUPLING_BOOST_MULTI
    if shared_with == 1:
        return COUPLING_BOOST_ONE
    return 1.0


def rerank(hits: list, meta_fn, today: date | None = None,
           last_used_fn=None, noise_fn=None, sources_fn=None) -> list:
    """Herweeg hits op relevance x recency x importance x usage, hersorteer.

    ``hits``: dicts met minstens ``path``, ``layer``, ``score``.
    ``meta_fn(path) -> dict``: frontmatter-reader (injecteerbaar).
    ``last_used_fn(stem) -> iso-datum``: usage-telemetrie-reader (optioneel);
    de gebruiks-boost geldt voor BEIDE lagen (een warm wiki-artikel is
    bewezen nuttig), recency/importance alleen voor de memory-laag.
    ``noise_fn(stem) -> (noise, injected)``: mens-gemarkeerde ruis (optioneel);
    drukt de score begrensd onder 1.0 (noise_factor).
    ``sources_fn(path) -> set[str]``: provenance-sleutels (optioneel, TASK-88);
    activeert het bibliographic-coupling-signaal BINNEN de kandidatenset.
    Zonder sources_fn is de ranking bit-voor-bit identiek aan voorheen
    (regressie-vergrendeling in tests/test_rank.py).
    Geeft een NIEUWE lijst terug.
    """
    today = today or date.today()

    # Coupling vooraf berekenen: per hit het aantal ANDERE hits waarmee hij
    # >=1 bron deelt. Eén pass over de kandidatenset, geen I/O hier — de
    # aanroeper batcht de bron-lookup (kb-recall: één sources_for-query).
    shared_counts = {}
    if sources_fn is not None:
        srcs = []
        for h in hits:
            try:
                s = set(sources_fn(h.get("path", "")) or ())
            except Exception:
                s = set()
            srcs.append(s)
        for i, si in enumerate(srcs):
            if not si:
                continue
            shared_counts[i] = sum(1 for j, sj in enumerate(srcs)
                                   if j != i and sj and (si & sj))

    out = []
    for i, h in enumerate(hits):
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
        stem = Path(h.get("path", "")).stem
        if last_used_fn is not None:
            try:
                score *= usage_factor(last_used_fn(stem), today)
            except Exception:
                pass
        if noise_fn is not None:
            try:
                score *= noise_factor(*noise_fn(stem))
            except Exception:
                pass
        score *= coupling_factor(shared_counts.get(i, 0))
        out.append({**h, "score": score})
    out.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return out

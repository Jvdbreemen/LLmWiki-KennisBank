#!/usr/bin/env python3
"""_reconcile.py - write-time invalidatie voor de capture-sweep (Mem0-patroon).

Bij het wegschrijven van een nieuw kandidaat-geheugen wordt eerst gereconciled
tegen de meest gelijkende bestaande memories: per paar beslist een LLM-seam
tussen ADD (echt nieuw), SUPERSEDE (nieuw feit vervangt/weerlegt oud feit) en
NOOP (al afgedekt, niets doen). Dit maakt van de sweep een actief
consolidatiemodel in plaats van append-plus-latere-scan; de bestaande
supersede-pass in _maintenance blijft als vangnet.

Drempel-interplay (gedocumenteerd gedrag, geen toeval):
  - cosine > DUP_THRESHOLD (0.92): kandidaat wordt VOOR reconcile als
    her-capture geskipt, MAAR alleen tegen een open memory (current/
    unverified) of tegen een gesloten memory uit hetzelfde tijdperk
    (kandidaat.valid_from <= gesloten.valid_until). Een her-assertie van
    een eerder gesloten feit met LATERE valid_from (flip-back: "Jim zoekt
    weer een baan") passeert de dedup en bereikt deze reconcile-laag wel
    (zie _dup_skip in memory-sweep.py). Dit houdt --all-rebuilds idempotent
    zonder LLM-kosten. Bekende, geaccepteerde beperking: een TEGENSPRAAK
    die toevallig >0.92 embedt tegen een OPEN memory wordt als duplicaat
    geskipt en dus gemist; geen enkel vangnet vangt die (de supersede-pass
    ziet alleen wat geschreven is). Prijs van idempotentie.
  - RECONCILE_THRESHOLD < cosine <= DUP_THRESHOLD: reconcile-band; de top-K
    buren gaan naar de judge.
  - cosine <= RECONCILE_THRESHOLD: ongerelateerd, gewoon ADD.

Temporele guard (deterministisch, geen LLM): een kandidaat mag een bestaand
memory alleen superseden als zijn valid_from >= de valid_from van het
bestaande memory. Een OUDER feit kan een NIEUWER feit nooit invalideren;
dit beschermt out-of-order sweeps (--all rebuild van oude transcripts).

FAIL-SAFE: judge onbereikbaar / onparseerbaar -> ADD. Worst case is een
redundant memory dat de supersede-pass later opruimt; nooit destructief
op een dode judge.

Stdlib + _embeddings; LLM alleen via de judge_reconcile-seam (mockbaar).
"""
from __future__ import annotations

import json as _json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402

RECONCILE_THRESHOLD = 0.75
TOP_K = 2

ACTIONS = ("ADD", "SUPERSEDE", "NOOP")

RECONCILE_SYSTEM = (
    "Je vergelijkt een NIEUW kandidaat-geheugen met een BESTAAND geheugen uit een "
    "persoonlijke kennisbank. Kies precies een actie:\n"
    "- SUPERSEDE: het nieuwe feit VERVANGT of WEERLEGT het bestaande "
    "(bv. 'Jim zoekt baan' -> 'Jim heeft baan', of een besluit dat is teruggedraaid).\n"
    "- NOOP: het nieuwe voegt niets toe; het bestaande dekt het al.\n"
    "- ADD: het nieuwe is echt aanvullend; beide kunnen naast elkaar bestaan.\n"
    "Antwoord UITSLUITEND met JSON: {\"action\": \"ADD\"|\"SUPERSEDE\"|\"NOOP\", "
    "\"reason\": \"<kort>\"}. Bij twijfel: ADD."
)


def similar_existing(vec, items: list, threshold: float = RECONCILE_THRESHOLD,
                     k: int = TOP_K) -> list:
    """Top-k bestaande items met cosine(vec, item.vec) > threshold, hoog->laag.

    ``items`` is de shape van _maintenance.current_items: dicts met minstens
    ``vec``; items zonder vector tellen niet mee.
    """
    scored = []
    for it in items:
        v = it.get("vec")
        if not v:
            continue
        s = emb.cosine(vec, v)
        if s > threshold:
            scored.append((s, it))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [it for _s, it in scored[:k]]


def judge_reconcile(new_text: str, old_text: str) -> str:
    """LLM-seam: beslis ADD | SUPERSEDE | NOOP voor (nieuw, bestaand).

    FAIL-SAFE-TO-ADD: geen respons, parse-fout of onbekende actie -> "ADD".
    """
    import _llm
    raw = _llm.generate(
        f"NIEUW:\n{new_text}\n\nBESTAAND:\n{old_text}\n\nOordeel (JSON):",
        system=RECONCILE_SYSTEM,
    )
    if not raw:
        return "ADD"
    try:
        s, e = raw.find("{"), raw.rfind("}")
        obj = _json.loads(raw[s:e + 1]) if s >= 0 and e > s else {}
    except Exception:
        return "ADD"
    action = obj.get("action")
    return action if action in ACTIONS else "ADD"


def may_supersede(new_valid_from: str, old_valid_from: str) -> bool:
    """Temporele guard: alleen superseden als het nieuwe feit niet OUDER is.

    ISO-datums (YYYY-MM-DD) sorteren lexicografisch; ontbrekende datums
    tellen als 'onbekend' en blokkeren niet (lege string < elke datum).
    """
    return (new_valid_from or "") >= (old_valid_from or "")


def reconcile(new_body: str, new_valid_from: str, vec, items: list,
              judge_fn=None) -> dict:
    """Reconcileer een kandidaat tegen de bestaande pool.

    Returns {"action": "ADD"|"NOOP", "supersedes": [item, ...]}:
      - NOOP: een CURRENT buur dekt de kandidaat al -> niet schrijven.
        Een NOOP-verdict tegen een unverified buur telt NIET: quarantaine-
        kennis mag nieuw bewijs niet wegdrukken (het nieuwe wordt gewoon
        ge-ADD en voedt de cluster-promotie).
      - ADD met supersedes: schrijf de kandidaat en sluit de genoemde items.
      - ADD zonder supersedes: gewoon schrijven.
    Judge-volgorde: buren van meest naar minst gelijkend; een geldig
    NOOP-verdict wint direct (niets schrijven verslaat schrijven-en-sluiten).
    """
    judge_fn = judge_fn or judge_reconcile
    supersedes = []
    for it in similar_existing(vec, items):
        action = judge_fn(new_body, it.get("body", ""))
        if action == "NOOP":
            if it.get("status") == "current":
                return {"action": "NOOP", "supersedes": []}
            continue
        if action == "SUPERSEDE" and may_supersede(new_valid_from, it.get("valid_from", it.get("created", ""))):
            supersedes.append(it)
    return {"action": "ADD", "supersedes": supersedes}

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

import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _llmjson  # noqa: E402

RECONCILE_THRESHOLD = 0.75
#: Hoeveel buren de judge te zien krijgt. Was 2.
#:
#: Gemeten over 149 echte supersede-paren: de opvolger staat binnen top-2 bij
#: 96,6% en binnen top-3 bij 98,0%. Hoger dan 3 heeft geen zin, en dat is
#: gemeten in plaats van geschat: over alle 1.271.215 paren in de vault heeft
#: GEEN ENKELE memory meer dan drie buren boven de drempel (mediaan 0, p99 2,
#: max 3). Met TOP_K=3 ziet de judge dus alles wat er is; 5 zou identiek zijn.
#:
#: Let op welke vraag die top-5 beantwoordt: dat is de rang onder ALLE
#: memories. similar_existing filtert eerst op de drempel en pakt daarna pas
#: top-k, dus een opvolger op rang 4 die onder 0.75 zit is bij elke k
#: onzichtbaar. De drempel is de bindende beperking, niet k.
#: Zie docs/research/supersede-window-2026-08-13.md.
TOP_K = 3

ACTIONS = ("ADD", "SUPERSEDE", "NOOP")

#: Promptversie: ophogen bij ELKE wijziging aan RECONCILE_SYSTEM.
#:
#: Waar hij landt, en waar niet -- want een versienummer dat nergens wordt
#: gestempeld belooft traceerbaarheid die er niet is. Een SUPERSEDE zet hem in
#: de reden in de closed-log (TASK-150), dus elke sluiting is herleidbaar tot
#: de prompt die haar veroorzaakte. Een NOOP laat NIETS achter: de kandidaat
#: wordt weggegooid, de heartbeat telt alleen hoevaak. Dat is precies de
#: actie waar modellen de mist in gaan (TASK-144), dus het gat is bekend en
#: staat als aparte taak genoteerd, niet als stilzwijgende aanname.
RECONCILE_PROMPT_VERSION = 2

#: De volgorde van de vragen IS de fix (TASK-144).
#:
#: De oude prompt gaf drie definities zonder volgorde, en beide lokale modellen
#: gebruikten NOOP voor "gaat nergens over elkaar" -- het omgekeerde van de
#: definitie, en precies waar ADD voor is. Gemeten op 20 bewust ongerelateerde
#: paren: qwen3.5:4b zei 6 keer NOOP, de 9b 18 keer, met redenen als "de nieuwe
#: tekst gaat over lwIP, de bestaande over exit codes; geen overlap".
#:
#: NOOP is de enige actie waarbij het nieuwe geheugen NIET geschreven wordt. Een
#: model dat de definities door elkaar haalt, verliest dus kennis. Daarom staat
#: de vraag "gaat dit uberhaupt over hetzelfde?" nu VOORAAN met ADD als
#: uitkomst, en komt de destructieve actie als laatste aan bod.
#:
#: De draadwaarden ADD/SUPERSEDE/NOOP blijven ongewijzigd; alleen de uitleg
#: verandert, dus er hoeft niets gemigreerd te worden.
RECONCILE_SYSTEM = (
    "Je vergelijkt een NIEUW kandidaat-geheugen met een BESTAAND geheugen uit een "
    "persoonlijke kennisbank. Loop de vragen in DEZE volgorde af en stop bij de "
    "eerste die past:\n"
    "1. Gaan ze over HETZELFDE onderwerp? Nee, of maar zijdelings verwant -> ADD. "
    "Geen overlap is ALTIJD ADD, nooit NOOP.\n"
    "2. Zegt het nieuwe iets ANDERS over dat onderwerp dan het bestaande -- een "
    "andere waarde, een teruggedraaid besluit, een weerlegging "
    "(bv. 'Jim zoekt baan' -> 'Jim heeft baan')? Ja -> SUPERSEDE.\n"
    "3. Staat alles wat het nieuwe zegt AL in het bestaande, zodat opslaan "
    "letterlijk niets toevoegt? Ja -> NOOP. Let op: bij NOOP wordt het nieuwe "
    "geheugen WEGGEGOOID, dus kies dit alleen als je zeker bent.\n"
    "4. Anders -> ADD.\n"
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
    obj = _llmjson.first_object(raw) or {}
    action = obj.get("action")
    return action if action in ACTIONS else "ADD"


def may_supersede(new_valid_from: str, old_valid_from: str) -> bool:
    """Temporele guard: alleen superseden als het nieuwe feit niet OUDER is.

    ISO-datums (YYYY-MM-DD) sorteren lexicografisch; ontbrekende datums
    tellen als 'onbekend' en blokkeren niet (lege string < elke datum).
    """
    return (new_valid_from or "") >= (old_valid_from or "")


def reconcile(new_body: str, new_valid_from: str, vec, items: list,
              judge_fn=None, new_volatility: str = "event") -> dict:
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

    new_volatility: de update-as van de KANDIDAAT ('state' | 'event'). Default
    'event' = altijd ADD, want geschiedenis vernietigen is de onomkeerbare
    fout. Let op wat die default betekent voor een aanroeper die hem vergeet:
    reconcile doet dan niets meer. De sweep geeft hem expliciet mee en een
    test pint dat vast; een volgende aanroeper moet dat ook doen.
    """
    judge_fn = judge_fn or judge_reconcile
    # Een gebeurtenis accumuleert (TASK-146): ze wordt nooit gesloten en drukt
    # nooit iets weg. Geen judge-aanroep, geen oordeel -- gewoon schrijven.
    # NOOP zou hier net zo schadelijk zijn als SUPERSEDE: de dedup op 0.92
    # vangt her-captures al af, dus wat in de 0.75-0.92-band binnenkomt zijn
    # ECHT verschillende gebeurtenissen en die horen allebei te bestaan.
    if new_volatility == "event":
        return {"action": "ADD", "supersedes": []}
    supersedes = []
    for it in similar_existing(vec, items):
        if it.get("volatility") == "event":
            continue
        action = judge_fn(new_body, it.get("body", ""))
        if action == "NOOP":
            if it.get("status") == "current":
                return {"action": "NOOP", "supersedes": []}
            continue
        if action == "SUPERSEDE" and may_supersede(new_valid_from, it.get("valid_from", it.get("created", ""))):
            supersedes.append(it)
    return {"action": "ADD", "supersedes": supersedes}

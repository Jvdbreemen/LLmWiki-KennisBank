#!/usr/bin/env python3
"""_extract.py - kandidaat-extractie-seam voor de capture-sweep.

Haalt uit een transcript de herbruikbare kennis: lessons learned, bug-fixes,
besluiten, duurzame feiten. Geeft een lijst kandidaat-memories; de judge (_judge)
beslist daarna current vs unverified.

FAIL-SAFE: None/parse-fout -> [] (liever niets dan ruis). Dunne laag op
_llm.generate(); tests monkeypatchen die seam.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _llm  # noqa: E402
import _llmjson  # noqa: E402

EXTRACT_SYSTEM = (
    "Je extraheert herbruikbare kennis uit een werk-transcript voor een persoonlijke "
    "kennisbank. Vang alleen: lessons learned, bug-fixes (oorzaak+oplossing), genomen "
    "besluiten, en duurzame feiten. NEGEER smalltalk, tussenstappen en vluchtige status. "
    "Elke memory is atomair en zelf-verklarend. Typeer elke memory: "
    "\"feit\" (duurzaam waar over de wereld of het project), "
    "\"voorkeur\" (hoe de gebruiker het wil), "
    "\"procedure\" (hoe je iets doet: stappen, werkwijze), "
    "\"beslissing\" (gemaakte keuze met reden). "
    "Geef daarnaast per memory de UPDATE-as: "
    "\"state\" = een huidige waarde die verandert en dus vervangen moet worden "
    "(een model, een drempel, een versie, een pad, een status, een eigenaar); "
    "\"event\" = iets dat gebeurd is en blijft staan "
    "(een bug-fix, een besluit, een les, een meting). Twijfel? Kies \"event\". "
    "Antwoord UITSLUITEND met een JSON-lijst: "
    "[{\"title\": \"<kort>\", \"body\": \"<2-4 zinnen>\", "
    "\"type\": \"feit|voorkeur|procedure|beslissing\", "
    "\"volatility\": \"state|event\"}]. Leeg = []."
)


#: Promptversie (TASK-90 E5): opgehoogd bij ELKE wijziging aan EXTRACT_SYSTEM.
#: Wordt met het model-id in de memory-frontmatter gestempeld, zodat na een
#: slechte promptversie alle getroffen claims selecteerbaar zijn.
EXTRACT_PROMPT_VERSION = 2

#: Weigering-/meta-patronen (TASK-90 E4, arkon#25): een model dat niet kan
#: antwoorden mag dat NOOIT als kennis het archief in schrijven. "Ik kan deze
#: vraag niet beantwoorden" met een titel en een plek in de index is de
#: nachtmerrie-variant van confidently-wrong: volstrekt inhoudsloos en toch
#: canoniek. Deterministische check, lowercase-substring — geen judge nodig.
REFUSAL_MARKERS = (
    "ik kan niet", "ik kan geen", "ik kan deze", "ik heb geen toegang",
    "het spijt me", "mijn excuses", "als ai", "als taalmodel",
    "i cannot", "i can't", "i am unable", "i'm unable", "i don't have access",
    "as an ai", "as a language model", "i apologize", "i'm sorry",
    "no relevant", "geen relevante kennis", "niet genoeg context",
)


def looks_like_refusal(text: str) -> bool:
    """True als de tekst een weigering/meta-antwoord is i.p.v. kennis."""
    low = " ".join(str(text or "").lower().split())
    return any(m in low for m in REFUSAL_MARKERS)


def extract_candidates(transcript_text: str, max_n: int = 8) -> list:
    if not (transcript_text or "").strip():
        return []
    raw = _llm.generate(f"Transcript:\n{transcript_text}\n\nKandidaten (alleen JSON-lijst):",
                        system=EXTRACT_SYSTEM)
    if not raw:
        return []
    arr = _llmjson.first_array(raw) or []
    out = []
    for item in arr if isinstance(arr, list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        body = str(item.get("body", "")).strip()
        # Weigering-poort (E4): een refusal/meta-kandidaat wordt hier
        # afgebroken, niet opgeslagen — geen latere lint repareert dat nog.
        if looks_like_refusal(title) or looks_like_refusal(body):
            continue
        if title and body:
            out.append({"title": title, "body": body,
                        "type": str(item.get("type", "")).strip().lower(),
                        # Ongefilterd doorgeven; _memory.coerce_volatility
                        # bepaalt de regel (label > config-vorm > event) op
                        # EEN plek, niet hier en daar allebei een beetje.
                        "volatility": str(item.get("volatility", "")).strip().lower()})
        if len(out) >= max_n:
            break
    return out

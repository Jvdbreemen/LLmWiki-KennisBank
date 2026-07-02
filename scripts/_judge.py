#!/usr/bin/env python3
"""_judge.py - onafhankelijke oordeel-seam voor de capture-sweep.

Beoordeelt of een kandidaat-memory de moeite waard is om als 'current' (direct
recallbaar) te bewaren, of dat-ie naar 'unverified' (quarantaine) moet. Draait
in de sweep met verse context, los van de producerende sessie -> onafhankelijk.

FAIL-SAFE: alles wat geen expliciet hoog-zeker 'current' is -> 'unverified'.
Een None/parse-fout/onbekend verdict promoot NOOIT. Dit beschermt #1 (geen
foute/stale recall) en #2 (geen ruis).

Dunne laag op _llm.generate(); tests monkeypatchen die seam.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _llm  # noqa: E402

JUDGE_SYSTEM = (
    "Je bent een sceptische, onafhankelijke keurder van kandidaat-geheugens voor een "
    "persoonlijke kennisbank. Keur streng. Promoot ALLEEN tot 'current' als dit een "
    "duidelijke, herbruikbare lesson learned, bug-fix, besluit of duurzaam feit is. "
    "Bij twijfel, ruis, smalltalk of vaagheid: 'unverified'. "
    "Ken ook een belang toe: importance 1-5 "
    "(5 = cruciale duurzame kennis, 3 = nuttig, 1 = marginaal). "
    "Antwoord UITSLUITEND met JSON: "
    "{\"verdict\": \"current\"|\"unverified\", \"importance\": 1-5, \"reason\": \"<kort>\"}."
)


def _clamp_importance(value) -> int:
    """Sanitize importance naar 1..5; onparseerbaar -> neutraal 3."""
    try:
        imp = int(value)
    except (TypeError, ValueError):
        return 3
    return min(5, max(1, imp))


def judge(candidate: str, context: str = "") -> dict:
    prompt = (f"Context:\n{context}\n\n" if context else "") + \
             f"Kandidaat-geheugen:\n{candidate}\n\nOordeel (alleen JSON):"
    raw = _llm.generate(prompt, system=JUDGE_SYSTEM)
    if not raw:
        return {"verdict": "unverified", "importance": 3,
                "reason": "geen model-respons (fail-safe)"}
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        obj = json.loads(raw[start:end + 1]) if start >= 0 and end > start else {}
    except Exception:
        return {"verdict": "unverified", "importance": 3,
                "reason": "onparseerbaar (fail-safe)"}
    verdict = obj.get("verdict")
    importance = _clamp_importance(obj.get("importance"))
    if verdict == "current":
        return {"verdict": "current", "importance": importance,
                "reason": str(obj.get("reason", ""))[:200]}
    return {"verdict": "unverified", "importance": importance,
            "reason": str(obj.get("reason", ""))[:200] or "geen current (fail-safe)"}

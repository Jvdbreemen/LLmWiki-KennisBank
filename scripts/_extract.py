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

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _llm  # noqa: E402

EXTRACT_SYSTEM = (
    "Je extraheert herbruikbare kennis uit een werk-transcript voor een persoonlijke "
    "kennisbank. Vang alleen: lessons learned, bug-fixes (oorzaak+oplossing), genomen "
    "besluiten, en duurzame feiten. NEGEER smalltalk, tussenstappen en vluchtige status. "
    "Elke memory is atomair en zelf-verklarend. Antwoord UITSLUITEND met een JSON-lijst: "
    "[{\"title\": \"<kort>\", \"body\": \"<2-4 zinnen>\"}]. Leeg = []."
)


def extract_candidates(transcript_text: str, max_n: int = 8) -> list:
    if not (transcript_text or "").strip():
        return []
    raw = _llm.generate(f"Transcript:\n{transcript_text}\n\nKandidaten (alleen JSON-lijst):",
                        system=EXTRACT_SYSTEM)
    if not raw:
        return []
    try:
        start = raw.find("[")
        end = raw.rfind("]")
        arr = json.loads(raw[start:end + 1]) if start >= 0 and end > start else []
    except Exception:
        return []
    out = []
    for item in arr if isinstance(arr, list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        body = str(item.get("body", "")).strip()
        if title and body:
            out.append({"title": title, "body": body})
        if len(out) >= max_n:
            break
    return out

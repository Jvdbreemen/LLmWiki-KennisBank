#!/usr/bin/env python3
"""kb-ask.py - manuele export-bridge naar cloud-agents (TASK-22).

Voor agents die NIET op deze machine draaien (cloud-ChatGPT, gehoste chat) en
een lokale MCP-server per definitie niet kunnen bereiken. In plaats van de
soevereine vault via een tunnel aan het internet bloot te stellen, blijft de
MENS de poort: dit script retrievet lokaal en print een kant-en-klaar
kennisblok dat je zelf in het chatvenster plakt. Niets verlaat de machine
automatisch; jij beslist wat je deelt.

Gebruik:
    python3 kb-ask.py "mijn vraag of onderwerp"
    python3 kb-ask.py "onderwerp" --k 8            # meer treffers
    python3 kb-ask.py "onderwerp" --clip           # ook naar het klembord
    python3 kb-ask.py "onderwerp" --plain          # kale treffers, geen wikkel

De wikkel is een korte instructie voor het cloud-model + de treffers, zodat je
het blok bovenaan je ChatGPT-bericht plakt en daaronder je eigenlijke vraag
stelt. Read-only over de index. Fail-soft: geen index/model -> nette melding,
exit 0 (dit is een hulpmiddel, geen poort die dicht mag vallen).

Klembord (--clip) is best-effort en OPTIONEEL: pyperclip als het er is, anders
het OS-hulpje (clip.exe / pbcopy / xclip / wl-copy). Faalt dat, dan staat het
blok nog steeds op stdout - kopieer het handmatig.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# kb-recall via importlib (hyphen in de bestandsnaam).
kb_recall = None
try:
    _spec = importlib.util.spec_from_file_location(
        "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
    kb_recall = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(kb_recall)
except Exception:
    kb_recall = None

WRAP_HEADER = (
    "Hieronder staat relevante kennis uit mijn eigen lokale KennisBank. Gebruik "
    "die als context bij mijn vraag; als iets ontbreekt, zeg dat eerlijk in "
    "plaats van te gokken.\n\n--- KennisBank-context ---"
)
WRAP_FOOTER = "--- einde context ---\n\nMijn vraag:"


def gather(query: str, k: int) -> list:
    """Retrieveer treffers lokaal. Lege lijst bij model/index-afwezigheid (fail-soft)."""
    q = (query or "").strip()
    if not q or kb_recall is None:
        return []
    try:
        import _embeddings as emb
        qvec = emb.embed(q)
        if not qvec:
            return []
        return kb_recall.recall_hits(qvec, query_text=q, k=int(k),
                                     layers=("wiki", "memory")) or []
    except Exception:
        return []


def format_hits(hits: list) -> str:
    lines = []
    for h in hits:
        tag = "geheugen" if h.get("layer") == "memory" else "wiki"
        stem = Path(h.get("path", "")).stem
        title = h.get("title", "") or stem
        snippet = (h.get("snippet", "") or "").replace("\n", " ").strip()
        lines.append(f"- [{tag}] {title}: {snippet}")
    return "\n".join(lines)


def to_clipboard(text: str) -> bool:
    """Best-effort klembord-kopie. True bij succes."""
    try:
        import pyperclip  # type: ignore
        pyperclip.copy(text)
        return True
    except Exception:
        pass
    candidates = []
    if sys.platform.startswith("win"):
        candidates = [["clip"]]
    elif sys.platform == "darwin":
        candidates = [["pbcopy"]]
    else:
        candidates = [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-b"]]
    for cmd in candidates:
        try:
            p = subprocess.run(cmd, input=text.encode("utf-8"), check=True)
            if p.returncode == 0:
                return True
        except Exception:
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Retrieveer lokaal een kennisblok om in een cloud-chat te plakken.")
    ap.add_argument("query", nargs="+", help="vraag of onderwerp")
    ap.add_argument("--k", type=int, default=5, help="aantal treffers (default 5)")
    ap.add_argument("--clip", action="store_true", help="ook naar het klembord")
    ap.add_argument("--plain", action="store_true",
                    help="alleen de kale treffers, zonder wikkel-instructie")
    args = ap.parse_args()

    query = " ".join(args.query).strip()
    hits = gather(query, args.k)
    if not hits:
        print("Geen treffers in de KennisBank (of model/index onbereikbaar).",
              file=sys.stderr)
        return 0

    body = format_hits(hits)
    block = body if args.plain else f"{WRAP_HEADER}\n{body}\n{WRAP_FOOTER} {query}"
    print(block)

    if args.clip:
        ok = to_clipboard(block)
        print(("[naar klembord gekopieerd]" if ok
               else "[klembord niet beschikbaar - kopieer hierboven handmatig]"),
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

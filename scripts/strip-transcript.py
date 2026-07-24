#!/usr/bin/env python3
"""strip-transcript.py - strip een Claude Code transcript-.jsonl tot platte
conversatietekst (alleen user+assistant), zodat een groot transcript subagent-
verteerbaar wordt voor /destilleer. Thinking, tool_use, tool_result en
isSidechain-turns vallen weg; dat scheelt in de praktijk ~10x (een transcript
van ~12 MB zakt naar een paar honderd KB).

Gebruik:
  strip-transcript.py <pad-of-stem> [-o OUT]

<pad-of-stem>: een pad naar een .jsonl, of een bare stem die tegen
  $VAULT/01-raw/transcripts/<stem>.jsonl wordt geresolveerd.
Zonder -o gaat de output naar stdout (pipe-vriendelijk; schrijf zelf naar een
scratch-bestand, niet naar de vault - de raw-sessie-stubs blijven de index).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _transcript import strip_to_text  # noqa: E402


def resolve_transcript(arg: str) -> Path:
    """Een expliciet .jsonl-pad blijft ongewijzigd; een bare stem resolvet tegen
    de vault-transcriptmap."""
    p = Path(arg)
    if p.suffix == ".jsonl" or p.exists():
        return p
    from _vaultpath import vault_root  # lazy: alleen nodig bij een bare stem
    return vault_root() / "01-raw" / "transcripts" / f"{arg}.jsonl"


def main(argv=None) -> int:
    # Forceer UTF-8 I/O: de Windows-console default (cp1252) kan transcript-
    # tekens (pijlen, emoji, accenten) niet encoden en zou crashen op stdout.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(
        description="Strip een Claude Code transcript-.jsonl tot platte tekst.")
    ap.add_argument(
        "transcript",
        help="pad naar een .jsonl, of een bare stem (resolvet tegen 01-raw/transcripts/)")
    ap.add_argument("-o", "--out", help="schrijf naar bestand i.p.v. stdout")
    args = ap.parse_args(argv)

    path = resolve_transcript(args.transcript)
    if not path.exists():
        print(f"transcript niet gevonden: {path}", file=sys.stderr)
        return 1

    text = strip_to_text(path)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

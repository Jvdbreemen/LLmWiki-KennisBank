#!/usr/bin/env python3
"""eval-wiki-recall.py - before/after-demo voor de hybride wiki-recall.

Bouwt in de ACTIEVE vault (KENNISBANK_VAULT) niets nieuws; vergelijkt voor een
paar queries het oude vector-only-signaal met het nieuwe FTS-signaal over de
bestaande kb-index. Read-only. Bedoeld als handmatige eval, niet als test.

Usage: KENNISBANK_VAULT=<vault> python3 eval-wiki-recall.py "query1" "query2" ...
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
import _embeddings as emb

_spec = importlib.util.spec_from_file_location(
    "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
kb_recall = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kb_recall)


def main(argv):
    queries = argv or ["voorbeeldquery"]
    for q in queries:
        qv = emb.embed(q)
        fts = kb_recall.has_fts_match(q, "wiki")
        hits = kb_recall.wiki_hits(qv, query_text=q, k=3) if qv else []
        print(f"\nQUERY: {q!r}")
        print(f"  FTS-keyword-match (wiki): {fts}")
        print(f"  hybride treffers: {[ (Path(h['path']).stem, round(h['score'],3)) for h in hits ]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

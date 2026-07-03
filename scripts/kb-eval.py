#!/usr/bin/env python3
"""kb-eval.py - recall@k eval-harnas voor de KennisBank-retrieval.

Meet hoe goed de recall-route de juiste documenten terugvindt voor een
persoonlijke eval-set van vragen. Zonder meting is elke retrieval-wijziging
gevoelsmatig; dit harnas maakt verbeteringen (en regressies) toetsbaar: draai
voor en na elke wijziging.

FIDELITY: de UserPromptSubmit-hook injecteert wiki en geheugen als TWEE
gescheiden, gelabelde blokken (kb-retrieve._wiki_block via wiki_hits,
_memory_block via memory_hits) — hij fuseert de lagen NOOIT in één ranking.
Daarom meet dit harnas per laag: de wiki-set (default) wordt wiki-only
gemeten, de geheugen-set memory-only. Een gefuseerde meting zou een topologie
scoren die de hook niet gebruikt en vals signaal geven (een geheugen-hit die
een wiki-artikel in een gefuseerde lijst verdringt telt in productie niet,
want ze staan in aparte blokken).

Eval-set: JSON-lijst van entries, default <vault>/06-claude/kb-eval-set.json
(wiki) en <vault>/06-claude/kb-memory-eval-set.json (geheugen):

    [
      {"q": "hoe zet ik wireguard op achter cgnat?",
       "expect": ["mikrotik-routeros-wireguard-cgnat"],
       "type": "single-hop"},
      ...
    ]

- ``q``: de vraag zoals je hem aan de agent zou stellen.
- ``expect``: bestandsstammen (zonder .md) die het antwoord dragen; een hit
  telt zodra een ervan in de top-k staat.
- ``type``: vrij label voor de breakdown (bv. single-hop, keyword,
  paraphrase, temporal, multi-hop; of feit/voorkeur/procedure/beslissing).

Metrics: recall@k voor k in (1, 3, 5), MRR (mean reciprocal rank van de
eerste verwachte hit), en een per-type breakdown. ``--json`` voor
machine-leesbare uitvoer, ``--verbose`` toont per vraag de gevonden top-k.
``--layer wiki|memory`` overschrijft de laag voor een custom ``--set``.

Zonder ``--set`` draait het harnas BEIDE sets als ze bestaan: de wiki-set
wiki-only en de geheugen-set memory-only, en rapporteert per laag — precies
de twee blokken die de hook injecteert.

Vereist een gebouwde kb-index (build-kb-index.py) en een bereikbare
embedding-backend. Exit: 0 = rapport gedraaid, 1 = set/index/embedding
onbereikbaar.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

KS = (1, 3, 5)
DEFAULT_SET = "06-claude/kb-eval-set.json"
MEMORY_SET = "06-claude/kb-memory-eval-set.json"


def load_set(path: Path) -> list:
    """Laad en valideer de eval-set. Raises ValueError bij vormfouten."""
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("eval-set moet een niet-lege JSON-lijst zijn")
    for i, e in enumerate(entries):
        if not isinstance(e, dict) or not e.get("q") or not e.get("expect"):
            raise ValueError(f"entry {i} mist 'q' of 'expect'")
        if not isinstance(e["expect"], list):
            raise ValueError(f"entry {i}: 'expect' moet een lijst van stems zijn")
    return entries


def rank_of_first_expected(hit_stems: list, expect: list) -> int:
    """1-based rang van de eerste verwachte stem in de hits; 0 = niet gevonden."""
    want = set(expect)
    for i, stem in enumerate(hit_stems, start=1):
        if stem in want:
            return i
    return 0


def evaluate(entries: list, hits_fn, ks=KS) -> dict:
    """Draai de eval. ``hits_fn(q: str, k: int) -> list[stem]`` is injecteerbaar
    zodat het harnas zonder model/index getest kan worden.

    Returns rapport-dict: per-k recall, mrr, per-type breakdown, per-vraag
    resultaten (q, expect, rank, hits).
    """
    kmax = max(ks)
    results = []
    for e in entries:
        stems = hits_fn(e["q"], kmax)
        rank = rank_of_first_expected(stems, e["expect"])
        results.append({
            "q": e["q"], "expect": e["expect"],
            "type": e.get("type", "single-hop"),
            "rank": rank, "hits": stems,
        })

    n = len(results)
    report = {
        "questions": n,
        "recall": {f"@{k}": round(sum(1 for r in results if 0 < r["rank"] <= k) / n, 3)
                   for k in ks},
        "mrr": round(sum((1.0 / r["rank"]) for r in results if r["rank"]) / n, 3),
        "by_type": {},
        "results": results,
    }
    for t in sorted({r["type"] for r in results}):
        sub = [r for r in results if r["type"] == t]
        report["by_type"][t] = {
            "n": len(sub),
            **{f"@{k}": round(sum(1 for r in sub if 0 < r["rank"] <= k) / len(sub), 3)
               for k in ks},
        }
    return report


def _live_hits_fn(layers=("wiki",)):
    """Bouw de echte hits_fn op de hook-route: embed + recall over EEN laag.

    ``layers`` is de laag-tuple die de hook voor dit blok gebruikt: ("wiki",)
    voor _wiki_block, ("memory",) voor _memory_block. Bewust GEEN gefuseerde
    ("wiki","memory") — dat is niet hoe de hook injecteert (zie module-docstring).

    Returns (hits_fn, None) of (None, foutmelding).
    """
    import _embeddings as emb
    spec = importlib.util.spec_from_file_location(
        "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
    kb_recall = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kb_recall)

    if emb.embed("ping") is None:
        return None, "embedding-backend onbereikbaar (Ollama draait niet?)"

    def hits_fn(q: str, k: int) -> list:
        qv = emb.embed(q)
        if qv is None:
            return []
        rows = kb_recall.recall_hits(qv, query_text=q, k=k, layers=tuple(layers))
        return [Path(r["path"]).stem for r in rows]

    return hits_fn, None


def _print_report(name: str, layer: str, report: dict, verbose: bool) -> None:
    print(f"\nkb-eval [{layer}]: {report['questions']} vragen uit {name}")
    for k, v in report["recall"].items():
        print(f"  recall{k}: {v}")
    print(f"  MRR: {report['mrr']}")
    for t, stats in report["by_type"].items():
        print(f"  [{t}] n={stats['n']} " +
              " ".join(f"{k}={v}" for k, v in stats.items() if k != "n"))
    misses = [r for r in report["results"] if r["rank"] == 0]
    if misses:
        print(f"  gemist ({len(misses)}):")
        for r in misses:
            print(f"    - {r['q']!r} (verwacht: {', '.join(r['expect'])})")
    if verbose:
        for r in report["results"]:
            print(f"  Q: {r['q']!r} rank={r['rank']}")
            for i, h in enumerate(r["hits"], start=1):
                mark = "*" if h in r["expect"] else " "
                print(f"    {mark}{i}. {h}")


def _run_one(set_path: Path, layer: str):
    """Laad set, bouw laag-specifieke hits_fn, evalueer. Returns (name, report)
    of (name, foutmelding-str)."""
    try:
        entries = load_set(set_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return set_path.name, f"eval-set niet bruikbaar: {exc}"
    hits_fn, err = _live_hits_fn(layers=(layer,))
    if hits_fn is None:
        return set_path.name, err
    return set_path.name, evaluate(entries, hits_fn)


def main() -> int:
    parser = argparse.ArgumentParser(description="recall@k eval over kb-index.db")
    parser.add_argument("--set", dest="set_path", default=None,
                        help=f"pad naar eval-set (default: beide, <vault>/{DEFAULT_SET} + {MEMORY_SET})")
    parser.add_argument("--layer", choices=("wiki", "memory"), default=None,
                        help="laag voor een custom --set (default: wiki)")
    parser.add_argument("--json", action="store_true", help="machine-leesbare uitvoer")
    parser.add_argument("--verbose", action="store_true", help="toon per vraag de top-k")
    args = parser.parse_args()

    # Bepaal welke (set, laag)-paren te draaien. Custom --set: één paar met de
    # opgegeven (of default wiki) laag. Zonder --set: beide standaardsets, elk
    # tegen zijn eigen laag — precies de twee blokken die de hook injecteert.
    if args.set_path:
        jobs = [(Path(args.set_path), args.layer or "wiki")]
    else:
        jobs = [(vault_root() / DEFAULT_SET, "wiki")]
        mem = vault_root() / MEMORY_SET
        if mem.exists():
            jobs.append((mem, "memory"))

    reports = {}
    any_ok = False
    for set_path, layer in jobs:
        name, res = _run_one(set_path, layer)
        if isinstance(res, str):
            print(f"kb-eval [{layer}] {name}: {res}", file=sys.stderr)
            continue
        any_ok = True
        reports[layer] = {"name": name, "report": res}
        if not args.json:
            _print_report(name, layer, res, args.verbose)

    if not any_ok:
        return 1
    if args.json:
        out = {}
        for layer, r in reports.items():
            rep = dict(r["report"])
            if not args.verbose:
                rep.pop("results")
            out[layer] = {"set": r["name"], **rep}
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

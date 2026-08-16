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


def _pct(sorted_vals: list, q: float) -> float:
    """Percentiel (nearest-rank) over een reeds gesorteerde lijst."""
    if not sorted_vals:
        return 0.0
    idx = max(0, min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def evaluate(entries: list, hits_fn, ks=KS, measure_latency=False) -> dict:
    """Draai de eval. ``hits_fn(q: str, k: int) -> list[stem]`` is injecteerbaar
    zodat het harnas zonder model/index getest kan worden.

    Returns rapport-dict: per-k recall, mrr, per-type breakdown, per-vraag
    resultaten (q, expect, rank, hits). Met ``measure_latency=True`` komt er
    een ``latency_ms``-blok bij (p50/p95 wall time per hits_fn-aanroep) — de
    deel-latency van de recall-route; de volledige hook-latency meet je door
    kb-retrieve.py zelf te timen (recept in TASK-86).
    """
    import time as _time
    kmax = max(ks)
    results = []
    timings = []
    for e in entries:
        t0 = _time.perf_counter()
        stems = hits_fn(e["q"], kmax)
        timings.append((_time.perf_counter() - t0) * 1000.0)
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
    if measure_latency:
        st = sorted(timings)
        report["latency_ms"] = {
            "p50": round(_pct(st, 0.50), 1),
            "p95": round(_pct(st, 0.95), 1),
        }
    for t in sorted({r["type"] for r in results}):
        sub = [r for r in results if r["type"] == t]
        report["by_type"][t] = {
            "n": len(sub),
            **{f"@{k}": round(sum(1 for r in sub if 0 < r["rank"] <= k) / len(sub), 3)
               for k in ks},
        }
    return report


def _load_by_path(filename: str):
    """Importlib-load van een hyphenated zusterscript uit scripts/."""
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_").replace(".py", ""),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _live_hits_fn(layers=("wiki",), expand=None):
    """Bouw de echte hits_fn op de hook-route: embed + recall over EEN laag.

    ``layers`` is de laag-tuple die de hook voor dit blok gebruikt: ("wiki",)
    voor _wiki_block, ("memory",) voor _memory_block. Bewust GEEN gefuseerde
    ("wiki","memory") — dat is niet hoe de hook injecteert (zie module-docstring).

    PRODUCTIE-PARITEIT (TASK-86): de hook geeft ``expand=`` en ``min_cos=`` mee
    aan recall_hits; dit harnas resolvet die knoppen via exact dezelfde functie
    (kb-retrieve.retrieve_params over dezelfde config) zodat de eval de poort,
    de buur-expansie en de weging van productie meet — niet een kale variant.
    Vóór deze fix mat kb-eval een pipeline zonder relevance floor en zonder
    expansie; de task-70-cijfers (wiki@5=1.000) zijn daardoor niet vergelijkbaar
    met alles wat hierna gemeten wordt.

    ``expand=None`` volgt productie (config/env); True/False (CLI --expand /
    --no-expand) overschrijft alleen de buur-expansie, voor offline A/B.

    NB: de eval vraagt k=max(KS)=5 waar productie top_n=3 injecteert; dat is
    bewust (recall@5 vereist 5 kandidaten). De pariteit zit in gate/expansie/
    weging, niet in k.

    Returns (hits_fn, None) of (None, foutmelding).
    """
    import _embeddings as emb
    kb_recall = _load_by_path("kb-recall.py")
    kb_retrieve = _load_by_path("kb-retrieve.py")

    cfg = kb_retrieve.load_embed_cfg(vault_root)
    params = kb_retrieve.retrieve_params(cfg)
    wiki_expand = params["expand"] if expand is None else bool(expand)

    if emb.embed("ping") is None:
        return None, "embedding-backend onbereikbaar (Ollama draait niet?)"

    def hits_fn(q: str, k: int) -> list:
        qv = emb.embed_query(q)
        if qv is None:
            return []
        if tuple(layers) == ("memory",):
            # productie: _memory_block -> memory_hits met de EIGEN memory-drempel
            rows = kb_recall.recall_hits(qv, query_text=q, k=k, layers=("memory",),
                                         min_cos=kb_recall.MEMORY_MIN_COS)
        else:
            # productie: _wiki_block -> wiki_hits met drempel + buur-expansie
            rows = kb_recall.recall_hits(qv, query_text=q, k=k, layers=tuple(layers),
                                         expand=wiki_expand, min_cos=params["min_cos"])
        return [Path(r["path"]).stem for r in rows]

    return hits_fn, None


def _print_report(name: str, layer: str, report: dict, verbose: bool) -> None:
    print(f"\nkb-eval [{layer}]: {report['questions']} vragen uit {name}")
    for k, v in report["recall"].items():
        print(f"  recall{k}: {v}")
    print(f"  MRR: {report['mrr']}")
    if report.get("latency_ms"):
        lm = report["latency_ms"]
        print(f"  latency: p50={lm['p50']}ms p95={lm['p95']}ms")
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


def _run_one(set_path: Path, layer: str, expand=None, latency=False):
    """Laad set, bouw laag-specifieke hits_fn, evalueer. Returns (name, report)
    of (name, foutmelding-str)."""
    try:
        entries = load_set(set_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return set_path.name, f"eval-set niet bruikbaar: {exc}"
    hits_fn, err = _live_hits_fn(layers=(layer,), expand=expand)
    if hits_fn is None:
        return set_path.name, err
    return set_path.name, evaluate(entries, hits_fn, measure_latency=latency)


def main() -> int:
    parser = argparse.ArgumentParser(description="recall@k eval over kb-index.db")
    parser.add_argument("--set", dest="set_path", default=None,
                        help=f"pad naar eval-set (default: beide, <vault>/{DEFAULT_SET} + {MEMORY_SET})")
    parser.add_argument("--layer", choices=("wiki", "memory"), default=None,
                        help="laag voor een custom --set (default: wiki)")
    parser.add_argument("--json", action="store_true", help="machine-leesbare uitvoer")
    parser.add_argument("--verbose", action="store_true", help="toon per vraag de top-k")
    parser.add_argument("--latency", action="store_true",
                        help="meet p50/p95 wall time per recall-aanroep")
    expand_group = parser.add_mutually_exclusive_group()
    expand_group.add_argument("--expand", dest="expand", action="store_true", default=None,
                              help="forceer buur-expansie aan (offline A/B)")
    expand_group.add_argument("--no-expand", dest="expand", action="store_false",
                              help="forceer buur-expansie uit (offline A/B)")
    args = parser.parse_args()

    # Altijd, onvoorwaardelijk: een eval-run mag nooit als gebruik meetellen.
    # Elk pad dat _usage.enabled() checkt (log_injected, mark_used) schrijft
    # hierdoor per constructie niets. try/finally herstelt de vorige waarde,
    # zodat ook een in-process aanroep (langlevend hostproces, tests) het
    # normale leergedrag na afloop teruggeeft — de guard mag nooit blijven
    # plakken buiten de duur van de eval zelf.
    saved_disable = os.environ.get("KB_USAGE_DISABLE")
    os.environ["KB_USAGE_DISABLE"] = "1"
    # Meldingen naar stderr: --json-consumenten lezen stdout en mogen hier
    # geen last van hebben.
    print("kb-eval: usage-telemetrie UIT (KB_USAGE_DISABLE=1) — "
          "deze eval telt niet mee als gebruik", file=sys.stderr)
    try:
        return _run_jobs(args)
    finally:
        if saved_disable is None:
            os.environ.pop("KB_USAGE_DISABLE", None)
            print("kb-eval: usage-telemetrie weer AAN — "
                  "de KennisBank leert weer van gebruik", file=sys.stderr)
        else:
            os.environ["KB_USAGE_DISABLE"] = saved_disable
            print("kb-eval: KB_USAGE_DISABLE stond al vóór deze run in de "
                  "omgeving en blijft staan — usage-telemetrie blijft UIT "
                  "(zie doctor.sh)", file=sys.stderr)


def _run_jobs(args) -> int:
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
        name, res = _run_one(set_path, layer, expand=args.expand, latency=args.latency)
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

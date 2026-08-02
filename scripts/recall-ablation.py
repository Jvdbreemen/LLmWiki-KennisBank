#!/usr/bin/env python3
"""recall-ablation.py - hoeveel van de recall komt van welke helft?

De recall-route is hybride: `_kbindex.search` voegt een dense cosine-ranglijst
en een FTS-ranglijst samen met RRF. Zolang je alleen hele modellen tegen elkaar
zet, blijft onzichtbaar hoeveel elk deel bijdraagt -- en dat bepaalt hoeveel een
betere (of slechtere) embedder ueberhaupt kan uitmaken. Als FTS de meeste
vragen al alleen oplost, is de spreiding tussen embedmodellen klein om een
reden die niets met die modellen te maken heeft.

Drie condities over dezelfde index en dezelfde eval-set:

  hybride     de productieroute: dense + FTS
  alleen-fts  alleen de lexicale ranglijst gaat de RRF-fusie in
  alleen-dens alleen de vectorranglijst gaat de RRF-fusie in

De arm wordt uitgeschakeld door `_kbindex._rrf` te vervangen door een variant
die een van de twee ranglijsten negeert. Een eerdere poging voedde in plaats
daarvan een willekeurige eenheidsvector als query, in de veronderstelling dat
het dense deel dan ruis zou zijn. Dat werkte niet: de dense arm haalt
`min(max(k*4, 20, total), 4096)` documenten op -- bij dit corpus dus ALLE
documenten -- zodat een ruisvector een complete willekeurige ranglijst
oplevert die RRF gewoon meeweegt. De spreiding over vijf trekkingen was 0,10
tot 0,30 op recall, en dat is precies het bewijs dat die opzet niets ableerde.

Alles na de fusie (statusfilter, _rank.rerank met recency en importance,
buur-expansie) blijft in alle drie de condities identiek, zodat het verschil
toe te schrijven is aan de arm en niet aan de nabewerking.

Stdlib only (behalve de index zelf). Alle condities vereisen een bereikbare
embedbackend, ook alleen-fts: de route berekent de queryvector sowieso.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

KS = (1, 3, 5)


def _load_by_path(filename: str):
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_").replace(".py", ""), str(SCRIPTS / filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rank_of(stems, expect) -> int:
    want = set(expect)
    for i, s in enumerate(stems, start=1):
        if s in want:
            return i
    return 0


def _metrics(ranks: list) -> dict:
    n = len(ranks)
    return {**{f"@{k}": round(sum(1 for r in ranks if 0 < r <= k) / n, 3) for k in KS},
            "mrr": round(sum(1.0 / r for r in ranks if r) / n, 3), "n": n}


class ArmSwitch:
    """Context manager die een van de twee ranglijsten uit de RRF-fusie haalt.

    `_kbindex.search` bouwt `rankings = [vec_ranking]` en hangt daar de
    FTS-ranglijst achter als de query een bruikbare FTS-expressie oplevert.
    Door `_rrf` te vervangen kunnen we precies een arm doorlaten zonder de
    zoekfunctie zelf te dupliceren -- die dupliceren zou betekenen dat de
    ablatie na de eerstvolgende wijziging stilletjes iets anders meet dan
    productie.

    keep="fts" op een query zonder FTS-expressie levert een lege fusie en dus
    geen treffers; dat is de juiste uitkomst (er is dan geen lexicaal signaal),
    geen fout."""

    def __init__(self, kbindex, keep: str):
        self.kbindex = kbindex
        self.keep = keep
        self.orig = kbindex._rrf

    def __enter__(self):
        orig, keep = self.orig, self.keep

        def patched(rank_lists, k_const: int = 60):
            if keep == "dense":
                return orig(rank_lists[:1], k_const)
            if keep == "fts":
                return orig(rank_lists[1:], k_const)
            return orig(rank_lists, k_const)

        self.kbindex._rrf = patched
        return self

    def __exit__(self, *exc):
        self.kbindex._rrf = self.orig
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", required=True)
    ap.add_argument("--model", required=True, help="embedmodel waarmee de index gebouwd is")
    ap.add_argument("--layer", choices=("wiki", "memory"), default="wiki")
    ap.add_argument("--set", dest="set_path", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--conditions", default="hybride,alleen-fts,alleen-dens")
    args = ap.parse_args()

    os.environ["KENNISBANK_VAULT"] = args.vault
    os.environ["KB_EMBED_PROVIDER"] = "ollama"
    os.environ["KB_EMBED_MODEL"] = args.model
    os.environ["KB_USAGE_DISABLE"] = "1"

    import _embeddings as emb
    kb_recall = _load_by_path("kb-recall.py")

    vault = Path(args.vault)
    default = ("kb-eval-set-full.json" if args.layer == "wiki"
               else "kb-memory-eval-set-full.json")
    path = Path(args.set_path) if args.set_path else vault / "06-claude" / default
    entries = json.loads(path.read_text(encoding="utf-8"))
    if args.limit:
        entries = entries[:args.limit]
    conds = [c.strip() for c in args.conditions.split(",") if c.strip()]
    print(f"ablatie [{args.layer}] {len(entries)} vragen uit {path.name}, "
          f"index={args.model}", flush=True)

    kmax = max(KS)
    out = {"layer": args.layer, "model": args.model, "n": len(entries),
           "set": path.name, "conditions": {}}

    if emb.embed("ping") is None:
        print("embedding-backend onbereikbaar", file=sys.stderr)
        return 1

    # Queryvectoren eenmalig: de drie condities stellen dezelfde vragen, en
    # opnieuw embedden zou alleen meetruis en wachttijd toevoegen.
    vecs = {}
    for e in entries:
        if e["q"] not in vecs:
            vecs[e["q"]] = emb.embed(e["q"], kind="query")
    print(f"  {len(vecs)} queryvectoren berekend", flush=True)

    def run(keep):
        ranks = []
        with ArmSwitch(kb_recall._kbindex, keep):
            for e in entries:
                rows = kb_recall.recall_hits(vecs[e["q"]], query_text=e["q"],
                                             k=kmax, layers=(args.layer,), min_cos=0.0)
                ranks.append(_rank_of([Path(r["path"]).stem for r in rows], e["expect"]))
        return ranks

    for cond, keep in (("hybride", "beide"), ("alleen-fts", "fts"),
                       ("alleen-dens", "dense")):
        if cond not in conds:
            continue
        out["conditions"][cond] = _metrics(run(keep))
        print(f"  {cond:12} {out['conditions'][cond]}", flush=True)

    dest = vault / f"ablatie-{args.layer}-{args.model.replace(':','-').replace('/','_')}.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nruw: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""rerank-eval.py - meet wat een cross-encoder reranker toevoegt aan de recall.

De vraag die dit beantwoordt: haalt een reranker vragen binnen die de huidige
route mist, en wat kost dat op het hot path?

Meetopzet. De recall-route levert per vraag DEPTH kandidaten (default 20) in
plaats van de 5 die de eval normaal beoordeelt. Die kandidaten gaan door een
cross-encoder, die -- anders dan een bi-encoder -- vraag en document SAMEN
door het model haalt en dus woordvolgorde en ontkenningen ziet. De top-5 na
herordening wordt tegen dezelfde eval-set gescoord als de top-5 ervoor.

Drie getallen maken het interpreteerbaar:

  voor     recall@k van de huidige route (de nulmeting)
  na       recall@k na herordening van dezelfde kandidaten
  plafond  recall@DEPTH -- wat er hooguit te winnen valt, want een reranker
           kan alleen herordenen wat de recall al heeft opgehaald. Zit het
           plafond dicht op "voor", dan is de bottleneck de recall zelf en
           helpt geen enkele reranker.

Latency wordt apart gerapporteerd: DEPTH paren door een 568M-model is een
andere orde dan een enkele embed-call, en dat verschil beslist of dit op het
hot path kan of alleen offline.

Vereist torch + transformers (NIET stdlib -- dit is meetgereedschap, geen
productiecode; de KennisBank-scripts zelf blijven stdlib-only).

Gebruik:
    python rerank-eval.py --vault <vault> --model <ollama-embedmodel> \\
        --reranker BAAI/bge-reranker-v2-m3 --depth 20
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
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


def _pct(vals, q: float) -> float:
    s = sorted(vals)
    if not s:
        return 0.0
    return s[max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))]


def _rank_of(stems, expect) -> int:
    want = set(expect)
    for i, s in enumerate(stems, start=1):
        if s in want:
            return i
    return 0


def _report(ranks: list, types: list, ks=KS) -> dict:
    n = len(ranks)
    rep = {
        "n": n,
        "recall": {f"@{k}": round(sum(1 for r in ranks if 0 < r <= k) / n, 3) for k in ks},
        "mrr": round(sum(1.0 / r for r in ranks if r) / n, 3),
        "by_type": {},
    }
    for t in sorted(set(types)):
        sub = [r for r, tt in zip(ranks, types) if tt == t]
        rep["by_type"][t] = {"n": len(sub),
                             **{f"@{k}": round(sum(1 for r in sub if 0 < r <= k) / len(sub), 3)
                                for k in ks}}
    return rep


class CrossEncoder:
    """Dunne wrapper om een sequence-classification reranker.

    fp16 op GPU: de score is een ordening, geen kansverdeling die tot achter de
    komma moet kloppen, dus halve precisie kost hier niets en halveert zowel
    het geheugen als de tijd."""

    def __init__(self, name: str, max_length: int = 512, batch_size: int = 16):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.torch = torch
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.tok = AutoTokenizer.from_pretrained(name)
        self.model = AutoModelForSequenceClassification.from_pretrained(name)
        if self.dev == "cuda":
            self.model = self.model.half()
        self.model.to(self.dev).eval()
        self.max_length = max_length
        self.batch_size = batch_size

    def scores(self, query: str, docs: list) -> list:
        out = []
        with self.torch.no_grad():
            for i in range(0, len(docs), self.batch_size):
                chunk = docs[i:i + self.batch_size]
                enc = self.tok([query] * len(chunk), chunk, padding=True,
                               truncation=True, max_length=self.max_length,
                               return_tensors="pt").to(self.dev)
                logits = self.model(**enc).logits.view(-1).float()
                out.extend(logits.cpu().tolist())
        return out


def run_layer(entries: list, layer: str, depth: int, ce, doc_cap: int,
              progress_every: int = 100) -> dict:
    import _embeddings as emb
    kb_recall = _load_by_path("kb-recall.py")

    before, after, ceiling, types = [], [], [], []
    embed_ms, recall_ms, rerank_ms = [], [], []
    changed = 0

    for i, e in enumerate(entries, start=1):
        q = e["q"]
        t0 = time.perf_counter()
        qv = emb.embed(q, kind="query")
        t1 = time.perf_counter()
        if qv is None:
            continue
        rows = kb_recall.recall_hits(qv, query_text=q, k=depth, layers=(layer,),
                                     min_cos=0.0)
        t2 = time.perf_counter()
        stems = [Path(r["path"]).stem for r in rows]
        if ce is None:
            # Plafondmeting: geen cross-encoder, alleen "zit het antwoord er
            # ueberhaupt bij". Het beantwoordt of herordenen zin heeft voordat
            # je er 31k modelaanroepen tegenaan gooit.
            t3 = t2
            reranked = stems
        else:
            docs = [emb.doc_text(Path(r["path"]), cap=doc_cap) for r in rows]
            sc = ce.scores(q, docs) if docs else []
            t3 = time.perf_counter()
            order = sorted(range(len(stems)), key=lambda j: sc[j], reverse=True)
            reranked = [stems[j] for j in order]

        before.append(_rank_of(stems[:max(KS)], e["expect"]))
        after.append(_rank_of(reranked[:max(KS)], e["expect"]))
        ceiling.append(_rank_of(stems, e["expect"]))
        types.append(e.get("type", "?"))
        if reranked[:max(KS)] != stems[:max(KS)]:
            changed += 1
        embed_ms.append((t1 - t0) * 1000)
        recall_ms.append((t2 - t1) * 1000)
        rerank_ms.append((t3 - t2) * 1000)
        if i % progress_every == 0:
            print(f"    {layer} {i}/{len(entries)}", flush=True)

    return {
        "layer": layer,
        "depth": depth,
        "before": _report(before, types),
        "after": _report(after, types),
        "ceiling_recall": round(sum(1 for r in ceiling if r) / len(ceiling), 3) if ceiling else 0,
        "top5_order_changed_pct": round(100.0 * changed / len(before), 1) if before else 0,
        "latency_ms": {
            "embed_p50": round(_pct(embed_ms, .50), 1),
            "recall_p50": round(_pct(recall_ms, .50), 1),
            "rerank_p50": round(_pct(rerank_ms, .50), 1),
            "rerank_p95": round(_pct(rerank_ms, .95), 1),
            "total_p50": round(_pct([a + b + c for a, b, c in
                                     zip(embed_ms, recall_ms, rerank_ms)], .50), 1),
            "total_p95": round(_pct([a + b + c for a, b, c in
                                     zip(embed_ms, recall_ms, rerank_ms)], .95), 1),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", required=True)
    ap.add_argument("--model", required=True, help="ollama-embedmodel voor de recall")
    ap.add_argument("--reranker", default="BAAI/bge-reranker-v2-m3")
    ap.add_argument("--depth", type=int, default=20)
    ap.add_argument("--doc-cap", type=int, default=4000,
                    help="tekens document die de reranker ziet. Default gelijk aan "
                         "wat de bi-encoder zag (emb.doc_text), zodat het verschil "
                         "in de MODELLEN zit en niet in de invoer. De tokenizer kapt "
                         "daarna alsnog op max_length; die asymmetrie is echt en "
                         "hoort in de conclusie.")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=512)
    ap.add_argument("--limit", type=int, default=0, help="max vragen per laag (0=alle)")
    ap.add_argument("--sets", default="wiki,memory")
    ap.add_argument("--ceiling-only", action="store_true",
                    help="alleen recall@depth meten (geen cross-encoder): wat "
                         "valt er hoogstens te winnen met herordenen?")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    os.environ["KENNISBANK_VAULT"] = args.vault
    os.environ["KB_EMBED_PROVIDER"] = "ollama"
    os.environ["KB_EMBED_MODEL"] = args.model
    os.environ["KB_RETRIEVE_THRESHOLD"] = "0.0"
    os.environ["KB_MEMORY_THRESHOLD"] = "0.0"
    os.environ["KB_USAGE_DISABLE"] = "1"

    vault = Path(args.vault)
    files = {"wiki": vault / "06-claude" / "kb-eval-set-full.json",
             "memory": vault / "06-claude" / "kb-memory-eval-set-full.json"}

    ce = None
    if not args.ceiling_only:
        print(f"reranker laden: {args.reranker} ...", flush=True)
        t0 = time.perf_counter()
        ce = CrossEncoder(args.reranker, max_length=args.max_length,
                          batch_size=args.batch_size)
        print(f"  geladen op {ce.dev} in {time.perf_counter()-t0:.1f}s", flush=True)

    results = {"embed_model": args.model,
               "reranker": None if args.ceiling_only else args.reranker,
               "depth": args.depth, "doc_cap": args.doc_cap, "layers": {}}
    for layer in [s.strip() for s in args.sets.split(",") if s.strip()]:
        path = files[layer]
        entries = json.loads(path.read_text(encoding="utf-8"))
        if args.limit:
            entries = entries[:args.limit]
        print(f"  {layer}: {len(entries)} vragen uit {path.name}", flush=True)
        results["layers"][layer] = run_layer(entries, layer, args.depth, ce,
                                             args.doc_cap)

    tag = ("ceiling" if args.ceiling_only else "rerank") + f"-d{args.depth}"
    out = Path(args.out) if args.out else vault / f"{tag}-{args.model.replace(':','-').replace('/','_')}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    for layer, r in results["layers"].items():
        b, a = r["before"], r["after"]
        print(f"\n[{layer}] n={b['n']} depth={r['depth']} "
              f"(volgorde top-5 gewijzigd bij {r['top5_order_changed_pct']}%)")
        for k in ("@1", "@3", "@5"):
            d = a["recall"][k] - b["recall"][k]
            print(f"  recall{k}: {b['recall'][k]:.3f} -> {a['recall'][k]:.3f}  ({d:+.3f})")
        print(f"  MRR:      {b['mrr']:.3f} -> {a['mrr']:.3f}  ({a['mrr']-b['mrr']:+.3f})")
        print(f"  plafond (recall@{r['depth']}): {r['ceiling_recall']:.3f}")
        print(f"  latency p50: embed {r['latency_ms']['embed_p50']}ms + "
              f"recall {r['latency_ms']['recall_p50']}ms + "
              f"rerank {r['latency_ms']['rerank_p50']}ms = "
              f"{r['latency_ms']['total_p50']}ms (p95 {r['latency_ms']['total_p95']}ms)")
    print(f"\nruw: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

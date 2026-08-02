#!/usr/bin/env python3
"""embed-sweep.py - vergelijk embedmodellen op kwaliteit EN hot-path-latency.

Waarom dit bestaat: de keuze van een embedmodel is een Pareto-afweging tussen
recall en latency, en geen enkele publieke benchmark meet die op DEZE vault.
MTEB-NL en BEIR-NL geven de relatieve ordening van modellen op Nederlands,
maar de marges daar (2-4 punten) zijn kleiner dan de spreiding tussen corpora.
Dit harnas meet beide assen op de eigen eval-sets, per model, reproduceerbaar.

Wat het per model doet:

  1. latency-probe   koude load + warme p50/p95 over N queries, rechtstreeks op
                     de provider (dus zonder index- of recall-overhead). Dit is
                     het getal dat het hot-path-budget van de prompt-hook haalt
                     of niet haalt.
  2. indexbouw       build-kb-index.py tegen een SCRATCH-vault, nooit de echte:
                     een modelwissel invalideert de embedcache per constructie,
                     en dat mag de werkende installatie niet raken.
  3. eval            kb-eval.py --json over beide lagen met drempel 0.0. De
                     drempels in productie (0.60) zijn gekalibreerd op qwen3;
                     ze meeschalen zou "hoe qwen3-achtig is de cosinusschaal
                     van dit model" meten in plaats van hoe goed het rankt.
                     De drempel voor de winnaar kalibreer je daarna apart.

Cache en index worden per model gesnapshot onder <scratch>/snapshots/<slug>/,
zodat een tweede run van hetzelfde model niets opnieuw embed.

Gebruik:
    python embed-sweep.py --vault <scratch-vault> --models qwen3-embedding:8b,...
    python embed-sweep.py --vault <scratch-vault> --report      # alleen tabel

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

#: Vragen voor de latency-probe. Bewust echte NL-vragen uit de eval-set: de
#: tokenlengte van een query bepaalt de embed-tijd mede, dus een synthetische
#: korte string zou het budget te rooskleurig meten.
PROBE_QUERIES = [
    "Waarom crasht mijn ESP32-S3 als ik BLE active scan aanzet tijdens runtime?",
    "Hoe zet ik inkomende WireGuard-toegang op als mijn MikroTik achter CGNAT zit?",
    "Mijn laptop voelt extreem traag maar de CPU is niet vol, hoe diagnosticeer ik dat?",
    "Welke esptool subcommand-syntax hoort bij welke major versie?",
]


def _pct(vals: list, q: float) -> float:
    s = sorted(vals)
    if not s:
        return 0.0
    i = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[i]


def ollama_embed(model: str, text: str, timeout: float = 300.0):
    payload = json.dumps({"model": model, "prompt": text,
                          "keep_alive": "30m"}).encode("utf-8")
    req = urllib.request.Request("http://localhost:11434/api/embeddings",
                                 data=payload,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    ms = (time.perf_counter() - t0) * 1000.0
    vec = body.get("embedding") or (body.get("embeddings") or [None])[0]
    return ms, vec


def unload_others(keep: str = "") -> list:
    """Zet alle andere geladen ollama-modellen uit de VRAM.

    Zonder dit meet de probe niet het model maar de VRAM-druk van dat moment:
    op een 16GB-kaart waar al 7GB bezet is, wordt een 8.4GB-model tussen twee
    calls door geevicteerd en schiet p95 van 0,5s naar 47s. Dat is een echt
    productieprobleem, maar het hoort in de vergelijking als een APARTE
    observatie, niet als ruis over alle modellen heen."""
    stopped = []
    try:
        r = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=30)
        for line in (r.stdout or "").splitlines()[1:]:
            name = line.split()[0] if line.split() else ""
            if name and name != keep:
                subprocess.run(["ollama", "stop", name], capture_output=True, timeout=60)
                stopped.append(name)
    except Exception:
        pass
    return stopped


def latency_probe(model: str, reps: int = 40) -> dict:
    """Koude load apart, daarna warme metingen. De koude load hoort NIET in de
    warme percentielen: hij gebeurt eenmalig per eviction en wordt in productie
    door warm_async() van het hot path gehaald."""
    cold_ms, vec = ollama_embed(model, "koude load")
    if not vec:
        return {"error": "geen vector terug"}
    warm = []
    for i in range(reps):
        ms, v = ollama_embed(model, PROBE_QUERIES[i % len(PROBE_QUERIES)] + f" ({i})")
        if v:
            warm.append(ms)
    return {
        "dim": len(vec),
        "cold_ms": round(cold_ms),
        "p50_ms": round(_pct(warm, 0.50), 1),
        "p95_ms": round(_pct(warm, 0.95), 1),
        "p99_ms": round(_pct(warm, 0.99), 1),
        "min_ms": round(min(warm), 1) if warm else None,
        "max_ms": round(max(warm), 1) if warm else None,
        "n": len(warm),
    }


def _slug(model: str) -> str:
    return model.replace("/", "_").replace(":", "-")


def _env(vault: Path, model: str, prefixes: dict) -> dict:
    e = os.environ.copy()
    e["KENNISBANK_VAULT"] = str(vault)
    e["KB_EMBED_PROVIDER"] = "ollama"
    e["KB_EMBED_MODEL"] = model
    # Rang-only meten: geen enkele drempel, want de cosinusschaal verschilt per
    # model en een vaste drempel meet dat verschil in plaats van de kwaliteit.
    e["KB_RETRIEVE_THRESHOLD"] = "0.0"
    e["KB_MEMORY_THRESHOLD"] = "0.0"
    e["KB_USAGE_DISABLE"] = "1"
    e["KB_EMBED_QUERY_PREFIX"] = prefixes.get("query", "")
    e["KB_EMBED_DOC_PREFIX"] = prefixes.get("doc", "")
    return e


def _run(cmd: list, env: dict, cwd: Path, timeout: float):
    return subprocess.run(cmd, env=env, cwd=str(cwd), timeout=timeout,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def _snapshot_dir(vault: Path, model: str, prefixes: dict) -> Path:
    tag = _slug(model)
    if prefixes.get("doc"):
        tag += "__" + _slug(prefixes["doc"])[:24]
    return vault / "snapshots" / tag


def _unlink_stubborn(p: Path, tries: int = 30, wait: float = 1.0) -> None:
    """Verwijder p, en wacht als Windows het bestand nog vasthoudt.

    Op Windows blijft een sqlite-bestand vergrendeld zolang enig proces er een
    handle op heeft; een net beeindigde indexbouwer laat die handle nog even
    staan. Hard falen zou de hele sweep afbreken op iets wat binnen een seconde
    vanzelf oplost. Na `tries` pogingen wijkt hij uit naar hernoemen: de sweep
    mag niet stranden op een bestand dat een vreemd proces blijft vasthouden."""
    for i in range(tries):
        if not p.exists():
            return
        try:
            p.unlink()
            return
        except PermissionError:
            time.sleep(wait)
    try:
        p.rename(p.with_name(p.name + f".stale.{os.getpid()}"))
    except OSError as exc:
        raise RuntimeError(
            f"{p} blijft vergrendeld en kan ook niet hernoemd worden: {exc}. "
            f"Draait er nog een indexbouwer op deze vault?") from exc


def _swap_in(vault: Path, snap: Path) -> None:
    """Zet de gesnapshotte cache/index terug, of ruim de vorige op. Zonder dit
    staat er nog een index van het VORIGE model klaar; build-kb-index gooit die
    weg bij embed_id-mismatch, maar de 180MB-cache erbij laten staan kost alleen
    maar leestijd."""
    cache = vault / ".claude" / "embeddings-cache.json"
    db = vault / ".claude" / "kb-index.db"
    for f in (cache, db):
        for p in (f, Path(str(f) + "-wal"), Path(str(f) + "-shm")):
            _unlink_stubborn(p)
    if (snap / "embeddings-cache.json").exists():
        shutil.copy2(snap / "embeddings-cache.json", cache)
    if (snap / "kb-index.db").exists():
        shutil.copy2(snap / "kb-index.db", db)


def _snapshot_out(vault: Path, snap: Path) -> None:
    snap.mkdir(parents=True, exist_ok=True)
    for name in ("embeddings-cache.json", "kb-index.db"):
        src = vault / ".claude" / name
        if src.exists():
            shutil.copy2(src, snap / name)


def sweep_model(vault: Path, model: str, prefixes: dict, reps: int,
                build_timeout: float) -> dict:
    out = {"model": model, "prefixes": prefixes}
    print(f"\n=== {model} " + (f"(prefix {prefixes})" if any(prefixes.values()) else ""),
          flush=True)

    print("  [1/3] latency-probe ...", flush=True)
    out["unloaded_first"] = unload_others(keep=model)
    out["latency"] = latency_probe(model, reps=reps)
    print(f"        {out['latency']}", flush=True)
    if out["latency"].get("error"):
        return out

    snap = _snapshot_dir(vault, model, prefixes)
    _swap_in(vault, snap)
    env = _env(vault, model, prefixes)

    print("  [2/3] index bouwen ...", flush=True)
    t0 = time.perf_counter()
    r = _run([sys.executable, str(SCRIPTS / "build-kb-index.py")], env, SCRIPTS,
             build_timeout)
    out["index_seconds"] = round(time.perf_counter() - t0, 1)
    out["index_stdout"] = (r.stdout or "").strip()[-400:]
    if r.returncode != 0:
        out["error"] = f"indexbouw faalde: {(r.stderr or '')[-400:]}"
        return out
    print(f"        {out['index_seconds']}s | {out['index_stdout']}", flush=True)
    _snapshot_out(vault, snap)

    print("  [3/3] kb-eval ...", flush=True)
    r = _run([sys.executable, str(SCRIPTS / "kb-eval.py"), "--json", "--latency"],
             env, SCRIPTS, build_timeout)
    try:
        out["eval"] = json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        out["error"] = f"eval faalde: {(r.stderr or r.stdout or '')[-600:]}"
        return out
    for layer, rep in out["eval"].items():
        print(f"        {layer}: recall@1={rep['recall']['@1']} "
              f"@3={rep['recall']['@3']} @5={rep['recall']['@5']} "
              f"MRR={rep['mrr']}", flush=True)
    return out


def report(results: list) -> str:
    hdr = (f"{'model':34} {'dim':>5} {'p50':>7} {'p95':>7} {'cold':>7} "
           f"{'wiki@3':>7} {'wikiMRR':>8} {'mem@3':>7} {'memMRR':>7}")
    lines = [hdr, "-" * len(hdr)]
    for r in results:
        lat = r.get("latency", {})
        ev = r.get("eval", {}) or {}
        w = ev.get("wiki", {})
        m = ev.get("memory", {})

        def g(d, path, default="-"):
            try:
                for p in path:
                    d = d[p]
                return d
            except Exception:
                return default
        name = r["model"] + ("*" if any(r.get("prefixes", {}).values()) else "")
        lines.append(
            f"{name:34} {lat.get('dim','-'):>5} {lat.get('p50_ms','-'):>7} "
            f"{lat.get('p95_ms','-'):>7} {lat.get('cold_ms','-'):>7} "
            f"{g(w,['recall','@3']):>7} {g(w,['mrr']):>8} "
            f"{g(m,['recall','@3']):>7} {g(m,['mrr']):>7}")
    lines.append("")
    lines.append("p50/p95/cold in ms, pure embed-call (geen index/recall). "
                 "recall en MRR rang-only (drempel 0.0). * = instructieprefix aan.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", required=True, help="scratch-vault (NIET de echte)")
    ap.add_argument("--models", default="", help="komma-lijst; leeg = alleen rapport")
    ap.add_argument("--query-prefix", default="", help="instructieprefix queryzijde")
    ap.add_argument("--doc-prefix", default="", help="instructieprefix documentzijde")
    ap.add_argument("--reps", type=int, default=40, help="warme latency-metingen")
    ap.add_argument("--build-timeout", type=float, default=7200.0)
    ap.add_argument("--out", default="", help="resultaat-JSON (default <vault>/sweep-results.json)")
    args = ap.parse_args()

    vault = Path(args.vault).resolve()
    if not (vault / "02-wiki").exists():
        print(f"embed-sweep: {vault} ziet er niet uit als een vault", file=sys.stderr)
        return 1
    out_path = Path(args.out) if args.out else vault / "sweep-results.json"
    results = []
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            results = []

    prefixes = {"query": args.query_prefix, "doc": args.doc_prefix}
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    for model in models:
        # Een model dat omvalt (niet gepulld, oninleesbare index, lock) mag de
        # rest van de sweep niet meenemen: dan ben je een uur meten kwijt aan
        # een fout die bij een model hoort, niet bij de run.
        try:
            res = sweep_model(vault, model, prefixes, args.reps, args.build_timeout)
        except Exception as exc:
            print(f"  !! {model} overgeslagen: {exc}", flush=True)
            res = {"model": model, "prefixes": prefixes, "error": str(exc)}
        key = (res["model"], tuple(sorted(res["prefixes"].items())))
        results = [r for r in results
                   if (r["model"], tuple(sorted(r.get("prefixes", {}).items()))) != key]
        results.append(res)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                            encoding="utf-8")

    print("\n" + report(results))
    print(f"\nruwe resultaten: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

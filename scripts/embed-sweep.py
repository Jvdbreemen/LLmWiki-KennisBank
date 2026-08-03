#!/usr/bin/env python3
"""embed-sweep.py - compare embedding models on quality AND hot-path latency.

Why this exists: choosing an embedding model is a Pareto trade-off between
recall and latency, and no public benchmark measures that on THIS vault.
MTEB-NL and BEIR-NL give the relative ordering of models on Dutch, but the
margins there (2-4 points) are smaller than the spread between corpora. This
harness measures both axes on the vault's own eval sets, per model, repeatably.

What it does per model:

  1. latency probe   cold load plus warm p50/p95 over N queries, straight at the
                     provider (so without index or recall overhead). This is the
                     number that either fits the prompt hook's hot-path budget
                     or does not.
  2. index build     build-kb-index.py against a SCRATCH vault, never the real
                     one: a model switch invalidates the embed cache by
                     construction, and that must not touch a working install.
  3. eval            kb-eval.py --json over both layers with floor 0.0. The
                     production floors are calibrated on qwen3; scaling them
                     along would measure "how qwen3-like is this model's cosine
                     scale" instead of how well it ranks. Calibrate the floor
                     for the winner separately afterwards.

Cache and index are snapshotted per model under <scratch>/snapshots/<slug>/, so
a second run of the same model re-embeds nothing.

Usage:
    python embed-sweep.py --vault <scratch-vault> --models qwen3-embedding:8b,...
    python embed-sweep.py --vault <scratch-vault> --report      # table only

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

#: Queries for the latency probe. Deliberately real Dutch questions from the
#: eval set: query token length is part of what determines embed time, so a
#: synthetic short string would measure the budget too optimistically.
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
    """Evict every other loaded ollama model from VRAM.

    Without this the probe measures the VRAM pressure of the moment rather than
    the model: on a 16 GB card with 7 GB already taken, an 8.4 GB model gets
    evicted between two calls and p95 jumps from 0.5 s to 47 s. That is a real
    production problem, but it belongs in the comparison as a SEPARATE
    observation, not as noise smeared over every model."""
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


def gpu_state() -> str:
    """VRAM in use, or empty when nvidia-smi is unavailable.

    Belongs with every row in the report. A measurement on a full card records
    eviction order rather than the model, and that difference cannot be
    recovered from the numbers afterwards -- unless the card state sits next to
    them.
    """
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            used, total = [int(x) for x in out.stdout.strip().split("\n")[0].split(",")]
            return f"{used}/{total} MiB"
    except Exception:
        pass
    return ""


def latency_probe(model: str, reps: int = 40) -> dict:
    """Cold load separately, then warm measurements. The cold load does NOT
    belong in the warm percentiles: it happens once per eviction, and in
    production warm_async() keeps it off the hot path.

    Evict EVERYTHING before this probe, the candidate model included. If it
    stays resident, "cold" here is not cold: cold_ms then measures a second warm
    call and flatters the model."""
    cold_ms, vec = ollama_embed(model, "cold load")
    if not vec:
        return {"error": "no vector returned"}
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
    # Rank-only measurement: no floor at all, because the cosine scale differs
    # per model and a fixed floor measures that difference instead of quality.
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
    """Delete p, waiting while Windows still holds the file.

    On Windows a sqlite file stays locked as long as any process holds a handle
    on it, and an index builder that just exited keeps that handle for a moment.
    Failing hard would abort the whole sweep over something that resolves itself
    within a second. After `tries` attempts it falls back to renaming: the sweep
    must not strand on a file some foreign process keeps holding."""
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
            f"{p} stays locked and cannot be renamed either: {exc}. "
            f"Is an index builder still running against this vault?") from exc


def _swap_in(vault: Path, snap: Path) -> None:
    """Restore the snapshotted cache/index, or clear the previous one. Without
    this an index from the PREVIOUS model is still in place; build-kb-index
    discards it on an embed_id mismatch, but leaving the 180 MB cache beside it
    only costs read time."""
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

    print("  [1/3] latency probe ...", flush=True)
    # Everything out, the candidate included: otherwise the cold load is not a
    # cold load. The card state goes into the report, because a row measured on
    # a full card has to stay identifiable afterwards.
    out["unloaded_first"] = unload_others()
    out["gpu_before"] = gpu_state()
    out["latency"] = latency_probe(model, reps=reps)
    out["gpu_after_load"] = gpu_state()
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
    lines.append("p50/p95/cold in ms, pure embed call (no index/recall). "
                 "recall en MRR rang-only (drempel 0.0). * = instructieprefix aan.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", required=True, help="scratch vault (NOT the real one)")
    ap.add_argument("--models", default="", help="komma-lijst; leeg = alleen rapport")
    ap.add_argument("--query-prefix", default="", help="instructieprefix queryzijde")
    ap.add_argument("--doc-prefix", default="", help="instructieprefix documentzijde")
    ap.add_argument("--reps", type=int, default=40, help="warme latency-metingen")
    ap.add_argument("--build-timeout", type=float, default=7200.0)
    ap.add_argument("--out", default="", help="resultaat-JSON (default <vault>/sweep-results.json)")
    args = ap.parse_args()

    vault = Path(args.vault).resolve()
    if not (vault / "02-wiki").exists():
        print(f"embed-sweep: {vault} does not look like a vault", file=sys.stderr)
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
        # A model that falls over (not pulled, unreadable index, lock) must not
        # take the rest of the sweep with it: otherwise an hour of measurement is
        # lost to a fault that belongs to one model, not to the run.
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

#!/usr/bin/env python3
"""judge-model-sweep.py - compare local judge/extraction models on the real seams.

The judge model is not a taste question: it decides what gets captured, what
lands in quarantine, and what supersedes what. All three seams are fail-safe in
a way that HIDES a weak model instead of surfacing it -- a parse failure means
"no candidates", "unverified", or "ADD" respectively, so the sweep keeps running
while capture quietly degrades. This harness therefore scores the RAW model
response, never the fail-safe fallback.

Three seams, run per arm against identical inputs:

  reconcile  ADD | SUPERSEDE | NOOP, scored per class against the vault's own
             superseded_by links (labels the incumbent produced and the user has
             lived with -- NOT ground truth, and the report must say so) plus an
             equal number of unrelated pairs that should read as ADD.
  extract    JSON list of {title, body, type} from real transcript chunks.
             Scored on conformance and yield; there is no gold set.
  judge      JSON {verdict, importance, reason} over the extracted candidates.
             No labels either, so the arms are compared on agreement and the
             disagreements are printed for inspection.

Plus determinism (repeat rate at temperature 0), latency p50/p95 per seam, and
VRAM per model with the embedding model resident.

READ-ONLY on the vault. Writes one JSON report to --out and nothing else.
Local providers only: a cloud provider in the chain aborts the run, because a
sweep like this would ship the vault's memories off the machine.

Stdlib only.

Usage:
    python3 scripts/judge-model-sweep.py --models qwen3.5:4b,qwen3.5:9b \\
        --pairs 20 --chunks 6 --reps 3 --out judge-sweep.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

import _extract  # noqa: E402
import _judge  # noqa: E402
import _llm  # noqa: E402
import _reconcile  # noqa: E402
import _sweepstate as ss  # noqa: E402
import _sweeputil as su  # noqa: E402

WIKILINK = re.compile(r"\[\[([^\]|]+)")


# --- input building (read-only) ---------------------------------------------

def _memories(vault: Path) -> dict:
    """stem -> {status, body, superseded_by} for every memory file."""
    out = {}
    mem = vault / "09-memory"
    if not mem.exists():
        return out
    for path in sorted(mem.glob("*.md")):
        try:
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(fm, dict):
            continue
        succ = ""
        raw = fm.get("superseded_by")
        if isinstance(raw, str):
            m = WIKILINK.search(raw)
            succ = m.group(1).strip() if m else ""
        elif isinstance(raw, list) and raw:
            m = WIKILINK.search(str(raw[0]))
            succ = m.group(1).strip() if m else ""
        out[path.stem] = {
            "status": str(fm.get("status", "")),
            "body": (body or "").strip(),
            "superseded_by": succ,
        }
    return out


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"\w{4,}", (text or "").lower())}


def supersede_pairs(mems: dict, limit: int, rng: random.Random) -> list:
    """(new, old) pairs the vault itself closed: successor body vs closed body."""
    pairs = []
    for stem, m in mems.items():
        if m["status"] != "superseded" or not m["superseded_by"]:
            continue
        succ = mems.get(m["superseded_by"])
        if not succ or not succ["body"] or not m["body"]:
            continue
        pairs.append({"kind": "supersede", "expected": "SUPERSEDE",
                      "new_stem": m["superseded_by"], "old_stem": stem,
                      "new": succ["body"], "old": m["body"]})
    rng.shuffle(pairs)
    return pairs[:limit]


def unrelated_pairs(mems: dict, limit: int, rng: random.Random,
                    max_jaccard: float = 0.06) -> list:
    """Pairs with almost no vocabulary in common: nothing to supersede here.

    Lexical rather than vector distance on purpose -- this harness must not need
    the embedding index to be present or fresh, and "shares almost no words" is
    a stricter bar for unrelatedness than a cosine close to zero.
    """
    current = [(s, m) for s, m in mems.items() if m["status"] == "current" and m["body"]]
    rng.shuffle(current)
    pairs, seen = [], set()
    for i, (s_a, a) in enumerate(current):
        if len(pairs) >= limit:
            break
        ta = _tokens(a["body"])
        if len(ta) < 8:
            continue
        for s_b, b in current[i + 1:i + 40]:
            if s_b in seen or s_a in seen:
                continue
            tb = _tokens(b["body"])
            if len(tb) < 8:
                continue
            union = ta | tb
            if not union:
                continue
            if len(ta & tb) / len(union) <= max_jaccard:
                pairs.append({"kind": "unrelated", "expected": "ADD",
                              "new_stem": s_a, "old_stem": s_b,
                              "new": a["body"], "old": b["body"]})
                seen.add(s_a)
                seen.add(s_b)
                break
    return pairs[:limit]


def transcript_chunks(vault: Path, limit: int, min_chars: int = 1500) -> list:
    """Real transcript chunks, spread across the archive rather than clustered.

    Parsing goes through _sweepstate.transcript_text, the same function capture
    uses. An earlier version of this harness carried its own copy that understood
    Claude Code's shape only, so it silently skipped every Codex and Copilot
    transcript -- biasing its own sample toward one client while claiming to
    measure the archive. A measurement harness that reads less than the thing it
    measures is worse than no harness.

    Short chunks are skipped: a 200-character fragment has almost nothing to
    extract, so both arms return [] and the comparison learns nothing from it.
    """
    tdir = vault / "01-raw" / "transcripts"
    files = sorted(tdir.glob("*.jsonl")) if tdir.exists() else []
    if not files:
        return []
    step = max(1, len(files) // max(1, limit * 3))
    picked = files[::step]
    out = []
    for path in picked:
        if len(out) >= limit:
            break
        chunks = su.chunk(ss.transcript_text(path))
        if chunks and len(chunks[0]) >= min_chars:
            out.append({"source": path.name, "text": chunks[0]})
    return out


# --- measurement -------------------------------------------------------------

def _call(prompt: str, system: str, timeout: float) -> tuple:
    t = time.perf_counter()
    raw = _llm.generate(prompt, system=system, timeout=timeout)
    return raw, (time.perf_counter() - t) * 1000.0


def parse_reconcile(raw):
    """Mirror _reconcile.judge_reconcile's parse, but report the FALLBACK."""
    if not raw:
        return None, "empty"
    try:
        s, e = raw.find("{"), raw.rfind("}")
        obj = json.loads(raw[s:e + 1]) if s >= 0 and e > s else {}
    except Exception:
        return None, "unparseable"
    action = obj.get("action")
    if action in _reconcile.ACTIONS:
        return action, "ok"
    return None, "no_action_field"


def parse_judge(raw):
    if not raw:
        return None, "empty"
    try:
        s, e = raw.find("{"), raw.rfind("}")
        obj = json.loads(raw[s:e + 1]) if s >= 0 and e > s else {}
    except Exception:
        return None, "unparseable"
    if not isinstance(obj, dict) or "verdict" not in obj:
        return None, "no_verdict_field"
    return {"verdict": obj.get("verdict"), "importance": obj.get("importance")}, "ok"


def parse_extract(raw):
    if not raw:
        return None, "empty"
    try:
        s, e = raw.find("["), raw.rfind("]")
        arr = json.loads(raw[s:e + 1]) if s >= 0 and e > s else None
    except Exception:
        return None, "unparseable"
    if not isinstance(arr, list):
        return None, "not_a_list"
    items = [i for i in arr if isinstance(i, dict) and str(i.get("title", "")).strip()
             and str(i.get("body", "")).strip()]
    return items, "ok"


def run_arm(model: str, data: dict, reps: int, timeout: float, verbose: bool) -> dict:
    os.environ["KB_LLM_MODEL"] = model
    arm = {"model": model, "reconcile": [], "extract": [], "judge": [],
           "determinism": {}, "vram_gb": None}

    for i, pair in enumerate(data["pairs"], 1):
        raw, ms = _call(f"NIEUW:\n{pair['new']}\n\nBESTAAND:\n{pair['old']}\n\nOordeel (JSON):",
                        _reconcile.RECONCILE_SYSTEM, timeout)
        action, status = parse_reconcile(raw)
        arm["reconcile"].append({"kind": pair["kind"], "expected": pair["expected"],
                                 "action": action, "parse": status, "ms": ms,
                                 "new_stem": pair["new_stem"], "old_stem": pair["old_stem"],
                                 "raw": (raw or "")[:600]})
        if verbose:
            print(f"  [{model}] reconcile {i}/{len(data['pairs'])} "
                  f"{pair['expected']}->{action or status} {ms:.0f}ms", flush=True)

    if arm["vram_gb"] is None:
        arm["vram_gb"] = _vram(model)

    for i, ch in enumerate(data["chunks"], 1):
        raw, ms = _call(f"Transcript:\n{ch['text']}\n\nKandidaten (alleen JSON-lijst):",
                        _extract.EXTRACT_SYSTEM, timeout)
        items, status = parse_extract(raw)
        refused = 0
        for it in items or []:
            if _extract.looks_like_refusal(str(it.get("title", ""))) or \
                    _extract.looks_like_refusal(str(it.get("body", ""))):
                refused += 1
        arm["extract"].append({"source": ch["source"], "parse": status, "ms": ms,
                               "n": len(items or []), "refused": refused,
                               "items": items or [], "raw": (raw or "")[:600]})
        if verbose:
            print(f"  [{model}] extract {i}/{len(data['chunks'])} "
                  f"{status} n={len(items or [])} {ms:.0f}ms", flush=True)

    for cand in data["candidates"]:
        raw, ms = _call(f"Kandidaat-geheugen:\n{cand}\n\nOordeel (alleen JSON):",
                        _judge.JUDGE_SYSTEM, timeout)
        obj, status = parse_judge(raw)
        arm["judge"].append({"candidate": cand[:200], "parse": status, "ms": ms,
                             "verdict": (obj or {}).get("verdict"),
                             "importance": (obj or {}).get("importance"),
                             "raw": (raw or "")[:400]})
        if verbose:
            print(f"  [{model}] judge {status} -> {(obj or {}).get('verdict')} {ms:.0f}ms",
                  flush=True)

    # Determinism: the same reconcile prompt repeated. Temperature is 0 in the
    # seam, so anything below 1.00 means a single-run comparison is noise.
    same = []
    for pair in data["pairs"][:4]:
        answers = []
        for _ in range(reps):
            raw, _ms = _call(f"NIEUW:\n{pair['new']}\n\nBESTAAND:\n{pair['old']}\n\nOordeel (JSON):",
                             _reconcile.RECONCILE_SYSTEM, timeout)
            answers.append(parse_reconcile(raw)[0])
        same.append(len(set(answers)) == 1)
    arm["determinism"] = {"items": len(same), "reps": reps,
                          "stable": sum(1 for s in same if s)}
    return arm


def _vram(model: str) -> float | None:
    try:
        req = urllib.request.Request("http://localhost:11434/api/ps", method="GET")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    for e in data.get("models", []):
        if isinstance(e, dict) and e.get("name") in (model, f"{model}:latest"):
            return round((e.get("size_vram") or 0) / 1e9, 2)
    return None


# --- scoring -----------------------------------------------------------------

def _pct(n, d):
    return None if not d else round(100.0 * n / d, 1)


def score(arm: dict) -> dict:
    rec = arm["reconcile"]
    by_class = {}
    for kind in ("supersede", "unrelated"):
        rows = [r for r in rec if r["kind"] == kind]
        if not rows:
            continue
        hit = sum(1 for r in rows if r["action"] == r["expected"])
        # Count the unparseable answers as their own bucket. Keying on str()
        # while comparing on the raw value silently reported them as zero -- the
        # exact "the number looks fine so nobody looks" failure this harness is
        # supposed to catch.
        actions = {}
        for r in rows:
            key = r["action"] if r["action"] is not None else "unparseable"
            actions[key] = actions.get(key, 0) + 1
        by_class[kind] = {
            "n": len(rows),
            "agreement_pct": _pct(hit, len(rows)),
            "actions": dict(sorted(actions.items())),
            "parse_ok_pct": _pct(sum(1 for r in rows if r["parse"] == "ok"), len(rows)),
        }
    ext, jud = arm["extract"], arm["judge"]
    lat = {}
    for name, rows in (("reconcile", rec), ("extract", ext), ("judge", jud)):
        ms = sorted(r["ms"] for r in rows)
        if ms:
            lat[name] = {"p50": round(statistics.median(ms)),
                         "p95": round(ms[min(len(ms) - 1, int(0.95 * len(ms)))])}
    return {
        "model": arm["model"],
        "vram_gb": arm["vram_gb"],
        "reconcile": by_class,
        "extract": {
            "n_chunks": len(ext),
            "parse_ok_pct": _pct(sum(1 for r in ext if r["parse"] == "ok"), len(ext)),
            "candidates_total": sum(r["n"] for r in ext),
            "candidates_per_chunk": round(sum(r["n"] for r in ext) / len(ext), 2) if ext else None,
            "empty_chunks": sum(1 for r in ext if r["n"] == 0),
            "refused_items": sum(r["refused"] for r in ext),
        },
        "judge": {
            "n": len(jud),
            "parse_ok_pct": _pct(sum(1 for r in jud if r["parse"] == "ok"), len(jud)),
            "verdicts": {v: sum(1 for r in jud if r["verdict"] == v)
                         for v in sorted({str(r["verdict"]) for r in jud})},
        },
        "determinism": arm["determinism"],
        "latency_ms": lat,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--models", default="qwen3.5:4b,qwen3.5:9b")
    ap.add_argument("--pairs", type=int, default=20, help="per class (supersede + unrelated)")
    ap.add_argument("--chunks", type=int, default=6)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--candidates", type=int, default=8, help="judge inputs, from the vault")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="judge-sweep.json")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    # Never ship the vault's memories to a cloud provider for a measurement.
    os.environ["KB_LLM_PROVIDERS"] = "ollama"
    chain = _llm.providers()
    if any(p in _llm.CLOUD_PROVIDERS for p in chain):
        print(f"refusing: provider chain is not local ({chain})", file=sys.stderr)
        return 2

    vault = vault_root()
    rng = random.Random(args.seed)
    mems = _memories(vault)
    pairs = supersede_pairs(mems, args.pairs, rng) + unrelated_pairs(mems, args.pairs, rng)
    chunks = transcript_chunks(vault, args.chunks)
    cands = [m["body"][:600] for _s, m in sorted(mems.items())
             if m["status"] == "current" and len(m["body"]) > 80][:args.candidates]

    if not pairs or not chunks:
        print(f"not enough input: {len(pairs)} pairs, {len(chunks)} chunks", file=sys.stderr)
        return 1

    data = {"pairs": pairs, "chunks": chunks, "candidates": cands}
    report = {
        "vault": str(vault),
        "seed": args.seed,
        "inputs": {"supersede_pairs": sum(1 for p in pairs if p["kind"] == "supersede"),
                   "unrelated_pairs": sum(1 for p in pairs if p["kind"] == "unrelated"),
                   "chunks": len(chunks), "judge_candidates": len(cands)},
        "arms": [], "scores": [],
    }
    out = Path(args.out)

    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        if not args.quiet:
            print(f"=== {model} ===", flush=True)
        arm = run_arm(model, data, args.reps, args.timeout, not args.quiet)
        report["arms"].append(arm)
        report["scores"].append(score(arm))
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report["scores"], ensure_ascii=False, indent=2))
    print(f"\nraw responses + metrics: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

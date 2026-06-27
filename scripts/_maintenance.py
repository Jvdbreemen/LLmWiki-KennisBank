#!/usr/bin/env python3
"""_maintenance.py - deterministische cross-memory-primitieven (supersede/cluster).

Levert de bouwstenen voor de onderhoudspas: laad current-memories met hun vectoren,
vind hoog-cosine paren (supersede-kandidaten), en tel verwante buren (cluster-
promotie). Geen LLM hier - dat zit in de seams (_judge / judge_supersede). De
vector-bron is injecteerbaar zodat de plumbing zonder model getest wordt.

Stdlib + _embeddings.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


def current_items(get_cached_fn=None) -> list:
    """Laad alle current-memories uit 09-memory/ met hun embeddings.

    Returns een list[dict] met sleutels: path, title, created, body, vec.
    Items zonder vector worden overgeslagen.

    Args:
        get_cached_fn: optionele injectable get_cached(path, cache, recompute=True)
                       om de echte emb.get_cached te vervangen in tests.
    """
    gc = get_cached_fn or (lambda p, cache, recompute=True: emb.get_cached(p, cache))
    cache = emb.load_cache()
    mdir = vault_root() / "09-memory"
    out = []
    if not mdir.exists():
        return out
    for f in sorted(mdir.glob("**/*.md")):
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if fm.get("status") != "current":
            continue
        vec = gc(f, cache)
        if not vec:
            continue
        out.append({
            "path": str(f),
            "title": fm.get("title", ""),
            "created": fm.get("created", ""),
            "body": body.strip(),
            "vec": vec,
        })
    return out


def similar_pairs(items: list, threshold: float) -> list:
    """Vind alle paren current-items met cosine(a, b) > threshold.

    Returns list[tuple(a, b, sim)] gesorteerd van hoog naar laag sim.
    """
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            s = emb.cosine(items[i]["vec"], items[j]["vec"])
            if s > threshold:
                pairs.append((items[i], items[j], s))
    pairs.sort(key=lambda t: t[2], reverse=True)
    return pairs


def neighbor_counts(items: list, threshold: float) -> dict:
    """Tel het aantal verwante buren (cosine > threshold) per item.

    Returns dict[path -> int]. Symmetric: als a en b elkaars buren zijn
    telt het voor beide.
    """
    counts = {it["path"]: 0 for it in items}
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if emb.cosine(items[i]["vec"], items[j]["vec"]) > threshold:
                counts[items[i]["path"]] += 1
                counts[items[j]["path"]] += 1
    return counts


import json as _json

SUPERSEDE_SYSTEM = (
    "Je beoordeelt of een NIEUWERE memory een OUDERE TEGENSPREEKT of vervangt "
    "(bv. 'Jim zoekt baan' -> 'Jim heeft baan'). Antwoord UITSLUITEND met JSON: "
    "{\"supersede\": true|false, \"reason\": \"<kort>\"}. Bij twijfel: false."
)


def judge_supersede(new_text: str, old_text: str) -> bool:
    import _llm
    raw = _llm.generate(f"NIEUWER:\n{new_text}\n\nOUDER:\n{old_text}\n\nOordeel (JSON):",
                        system=SUPERSEDE_SYSTEM)
    if not raw:
        return False
    try:
        s, e = raw.find("{"), raw.rfind("}")
        obj = _json.loads(raw[s:e + 1]) if s >= 0 and e > s else {}
    except Exception:
        return False
    return obj.get("supersede") is True


def supersede_pass(threshold: float = 0.85, judge_fn=None, get_cached_fn=None) -> int:
    import _memory
    judge_fn = judge_fn or judge_supersede
    items = current_items(get_cached_fn=get_cached_fn)
    done = 0
    superseded_paths = set()
    for a, b, _sim in similar_pairs(items, threshold):
        # bepaal nieuwer/ouder op created (string ISO sorteert correct)
        newer, older = (a, b) if (a["created"] >= b["created"]) else (b, a)
        if older["path"] in superseded_paths or newer["path"] in superseded_paths:
            continue
        if judge_fn(newer["body"], older["body"]):
            if _memory.set_status(older["path"], "superseded",
                                  superseded_by=[Path(newer["path"]).stem]):
                superseded_paths.add(older["path"])
                done += 1
    return done

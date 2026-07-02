#!/usr/bin/env python3
"""kb-calibrate.py - drempel-kalibratie voor het actieve embeddingmodel.

Het systeem hangt aan elkaar van cosine-drempels die getuned zijn op een
specifiek embeddingmodel (qwen3-embedding:8b): dedup (0.92, _sweeputil),
rewrite (find-similar), retrieve (0.60), reconcile (0.75, _reconcile),
conflict (0.62, conflict-scan). Een modelwissel maakt die kalibratie
stilletjes ongeldig. Dit harnas maakt de herijking mechanisch: het embedt
een handgelabelde set tekstparen met het ACTIEVE model en stelt per
drempelklasse een waarde voor, met de separatiemarge erbij.

Gelabelde set (JSON, default <vault>/06-claude/kb-calibrate-set.json):

    [
      {"a": "tekst A", "b": "tekst B", "label": "duplicate"},   # zelfde feit
      {"a": "...",     "b": "...",     "label": "related"},     # zelfde thema
      {"a": "...",     "b": "...",     "label": "unrelated"}
    ]

Twee scheidingen worden geijkt:
  - duplicate-grens (dedup/rewrite): scheidt duplicate van related+unrelated;
  - related-grens (retrieve/reconcile-onderkant/conflict): scheidt
    duplicate+related van unrelated.

Per grens: voorstel = middelpunt van de separatie-gap; bij overlap (geen
schone scheiding) wordt dat gemeld met de botsende paren. Het harnas
SCHRIJFT NIETS: de mens beslist en zet de drempels zelf (governance-lijn
van de vault). Exit: 0 = rapport, 1 = set/embedding onbereikbaar,
2 = overlap gevonden (drempels niet schoon te scheiden met deze set).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

LABELS = ("duplicate", "related", "unrelated")
DEFAULT_SET = "06-claude/kb-calibrate-set.json"

#: Huidige knoppen en welke scheiding ze nodig hebben, ter referentie in het
#: rapport. Waarden zijn de defaults in de code/config.
CURRENT_KNOBS = [
    ("dedup (is_duplicate, _sweeputil)",   0.92, "duplicate"),
    ("rewrite (find-similar)",             0.83, "duplicate"),
    ("reconcile-band ondergrens (_reconcile)", 0.75, "related"),
    ("conflict (KB_CONFLICT_SIM)",         0.62, "related"),
    ("retrieve (retrieve_threshold)",      0.60, "related"),
]


def load_set(path: Path) -> list:
    pairs = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("kalibratieset moet een niet-lege JSON-lijst zijn")
    for i, p in enumerate(pairs):
        if not isinstance(p, dict) or not p.get("a") or not p.get("b"):
            raise ValueError(f"paar {i} mist 'a' of 'b'")
        if p.get("label") not in LABELS:
            raise ValueError(f"paar {i}: label moet een van {LABELS} zijn")
    return pairs


def _separation(positives: list, negatives: list) -> dict:
    """Scheiding tussen twee score-groepen: positives horen BOVEN de grens.

    Returns {clean, suggested, margin, min_pos, max_neg}. Bij overlap is
    clean False en suggested het middelpunt van de overlapzone (beste gok).
    """
    min_pos = min(positives)
    max_neg = max(negatives)
    clean = min_pos > max_neg
    return {
        "clean": clean,
        "suggested": round((min_pos + max_neg) / 2, 3),
        "margin": round(min_pos - max_neg, 3),
        "min_pos": round(min_pos, 3),
        "max_neg": round(max_neg, 3),
    }


def calibrate(scored_pairs: list) -> dict:
    """Bepaal beide grenzen uit gescoorde paren [{label, score, ...}].

    Raises ValueError als een labelklasse ontbreekt (dan valt er niets te
    scheiden).
    """
    by = {lbl: [p["score"] for p in scored_pairs if p["label"] == lbl]
          for lbl in LABELS}
    for lbl, scores in by.items():
        if not scores:
            raise ValueError(f"kalibratieset bevat geen '{lbl}'-paren")
    return {
        "duplicate_boundary": _separation(by["duplicate"],
                                          by["related"] + by["unrelated"]),
        "related_boundary": _separation(by["duplicate"] + by["related"],
                                        by["unrelated"]),
        "counts": {lbl: len(v) for lbl, v in by.items()},
    }


def knob_report(result: dict) -> list:
    """Toets de huidige knoppen tegen de geijkte grenzen.

    Een duplicate-knop hoort >= de duplicate-grens, een related-knop >= de
    related-grens en < de duplicate-grens. Returns lijst regels (str)."""
    dup = result["duplicate_boundary"]["suggested"]
    rel = result["related_boundary"]["suggested"]
    lines = []
    for name, value, kind in CURRENT_KNOBS:
        boundary = dup if kind == "duplicate" else rel
        ok = value >= boundary if kind == "duplicate" else (boundary <= value < dup)
        status = "OK  " if ok else "HERIJK"
        lines.append(f"  [{status}] {name}: huidig {value}, geijkte {kind}-grens {boundary}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="drempel-kalibratie voor het actieve embeddingmodel")
    parser.add_argument("--set", dest="set_path", default=None,
                        help=f"pad naar kalibratieset (default: <vault>/{DEFAULT_SET})")
    parser.add_argument("--json", action="store_true", help="machine-leesbare uitvoer")
    args = parser.parse_args()

    set_path = Path(args.set_path) if args.set_path else vault_root() / DEFAULT_SET
    try:
        pairs = load_set(set_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"kb-calibrate: kalibratieset niet bruikbaar: {exc}", file=sys.stderr)
        return 1

    import _embeddings as emb
    if emb.embed("ping") is None:
        print("kb-calibrate: embedding-backend onbereikbaar", file=sys.stderr)
        return 1

    scored = []
    for p in pairs:
        va, vb = emb.embed(p["a"]), emb.embed(p["b"])
        if va is None or vb is None:
            print("kb-calibrate: embed faalde halverwege; run afgebroken", file=sys.stderr)
            return 1
        scored.append({"label": p["label"], "score": emb.cosine(va, vb),
                       "a": p["a"][:60], "b": p["b"][:60]})

    try:
        result = calibrate(scored)
    except ValueError as exc:
        print(f"kb-calibrate: {exc}", file=sys.stderr)
        return 1
    result["model"] = emb.embed_id()

    overlap = (not result["duplicate_boundary"]["clean"]
               or not result["related_boundary"]["clean"])

    if args.json:
        result["knobs"] = [{"name": n, "current": v, "kind": k} for n, v, k in CURRENT_KNOBS]
        print(json.dumps(result, ensure_ascii=False))
        return 2 if overlap else 0

    print(f"kb-calibrate: model {result['model']}, "
          f"{sum(result['counts'].values())} paren {result['counts']}")
    for key, title in (("duplicate_boundary", "duplicate-grens (dedup/rewrite)"),
                       ("related_boundary", "related-grens (retrieve/reconcile/conflict)")):
        b = result[key]
        sep = "schoon" if b["clean"] else "OVERLAP - geen schone scheiding"
        print(f"  {title}: voorstel {b['suggested']} "
              f"(marge {b['margin']}, laagste-boven {b['min_pos']}, hoogste-onder {b['max_neg']}) [{sep}]")
    print("Huidige knoppen tegen de geijkte grenzen:")
    for line in knob_report(result):
        print(line)
    if overlap:
        print("Let op: overlap betekent dat deze set (of dit model) de klassen niet "
              "schoon scheidt; breid de set uit of kies de drempel handmatig conservatief.")
    return 2 if overlap else 0


if __name__ == "__main__":
    sys.exit(main())

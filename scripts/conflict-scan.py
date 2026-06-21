#!/usr/bin/env python3
"""
conflict-scan.py — Detecteer kandidaat-tegenstrijdige wiki-artikelparen in de KennisBank.

Scant 02-wiki/*.md, laadt ingebedde vectors uit de cache, vindt semantisch
overlappende paren (cosine >= drempel) en scoort elk paar op lexicale
tegenstrijdigheidsignalen. Uitvoer is een voorstel (hoge recall, valspositieven
acceptabel) bedoeld als input voor een toekomstige /reconcile-opdracht.

Gebruik:
    python3 conflict-scan.py [--sim T] [--json]

Drempel: env KB_CONFLICT_SIM (default 0.62, NL-decimaalnotatie toegestaan).
         --sim overschrijft de env-var.

Uitvoer:
    Standaard: Markdown-rapport (naar stdout), gesorteerd op signaal DESC.
    --json: JSON-array met dezelfde velden.
"""
from __future__ import annotations

import json
import os
import re
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _embeddings import cosine, load_cache, doc_text, embed_id  # noqa: E402
from _vaultpath import vault_root  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402


# ---------------------------------------------------------------------------
# Drempel-helper (zelfde patroon als semantic-tiling.py)
# ---------------------------------------------------------------------------

def _threshold(env_var: str, default: float) -> float:
    """Lees een cosine-drempel uit een env-var, NL-decimaal-tolerant."""
    raw = os.environ.get(env_var)
    if raw is None:
        return default
    try:
        return float(raw.strip().replace(",", "."))
    except ValueError:
        print(
            f"waarschuwing: ongeldige {env_var}={raw!r}, val terug op {default}",
            file=sys.stderr,
        )
        return default


# ---------------------------------------------------------------------------
# Pure core 1: kandidaatparen
# ---------------------------------------------------------------------------

def candidate_pairs(embeddings: dict, sim_threshold: float) -> list[tuple]:
    """Vind alle artikelparen waarvan de cosine-gelijkenis >= sim_threshold.

    Args:
        embeddings:     Mapping van path -> vector (list of float).
        sim_threshold:  Minimale cosine-score om een paar op te nemen.

    Returns:
        Gesorteerde lijst van 3-tuples (path_a, path_b, score).
        Geen zelf-paren. (a,b) en (b,a) worden als één paar behandeld.
        Deterministisch gesorteerd: primair op score DESC, secundair op
        (path_a, path_b) ASC zodat de volgorde stabiel is bij gelijke scores.
    """
    paths = sorted(embeddings.keys())  # stabiele iteratievolgorde
    result = []
    for path_a, path_b in combinations(paths, 2):
        vec_a = embeddings[path_a]
        vec_b = embeddings[path_b]
        score = cosine(vec_a, vec_b)
        if score >= sim_threshold:
            result.append((path_a, path_b, float(score)))
    # Deterministisch: hoog score eerst, daarna alfabetisch op paden
    result.sort(key=lambda t: (-t[2], t[0], t[1]))
    return result


# ---------------------------------------------------------------------------
# Pure core 2: tegenstrijdigheidsignaal (lexicaal, geen embeddings)
# ---------------------------------------------------------------------------

# Negatie-tokens (NL + EN)
_NEGATION_TOKENS = frozenset({
    "geen", "niet", "no", "not", "nooit", "never",
    "nee", "noch", "zonder", "nimmer",
})

# Stopwoorden die niet als "gedeelde term" tellen
_STOPWORDS = frozenset({
    "de", "het", "een", "en", "in", "van", "op", "te", "aan", "met",
    "voor", "dat", "die", "zijn", "is", "heeft", "hebben", "worden",
    "wordt", "als", "ook", "nog", "maar", "of", "om", "bij", "uit",
    "over", "naar", "werd", "worden", "zijn", "was", "had", "kan",
    "kan", "zal", "zou", "mag", "moet", "dan", "er", "al", "er",
    "the", "a", "an", "and", "or", "in", "of", "to", "is", "it",
    "be", "at", "by", "for", "on", "with", "this", "that", "are",
    "was", "has", "have", "will", "can", "from", "they", "we",
    "het", "hij", "zij", "ze", "ik", "jij", "je", "wij",
})

_NUMBER_RE = re.compile(r"\b\d{2,}\b")  # getallen van ≥2 cijfers (jaren, bedragen, enz.)


def _tokenize(text: str) -> list[str]:
    """Geef genormaliseerde woordtokens terug (lowercase, alleen alfanumeriek)."""
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9À-ɏ]+\b", text)]


def _significant_tokens(tokens: list[str]) -> set[str]:
    """Filter stopwoorden en negaties uit een tokenlijst; geef set van inhoudswoorden."""
    return {t for t in tokens if t not in _STOPWORDS and t not in _NEGATION_TOKENS and len(t) > 2}


def contradiction_signal(text_a: str, text_b: str) -> float:
    """Schat de kans dat twee teksten elkaar tegenspreken (lexicaal heuristisch).

    Formule (recall-bevooroordeeld, geen embeddings):

    1. Gedeelde inhoudswoorden (shared_ratio):
       |sig_a ∩ sig_b| / max(|sig_a|, |sig_b|, 1)
       Teksten moeten over hetzelfde gaan voor een tegenstrijdigheid te bestaan.

    2. Negatieasymmetrie (neg_score):
       Is een negatie-token aanwezig in A maar niet in B (of omgekeerd), EN
       deelt het tekstpaar minstens één inhoudswoord? Dan is er een aanwijzing
       van een "X is geen Y" vs "X is Y"-patroon.
       neg_score = 1.0 als er asymmetrische negatie + gedeelde term is, anders 0.

    3. Getallenconflict (num_score):
       Hebben A en B minstens één gedeeld inhoudswoord EN minstens één getal
       dat in A voorkomt maar niet in B (of omgekeerd)? Dan is er een
       aanwijzing van strijdige feiten (jaartallen, versienummers, enz.).
       num_score = 0.5 als er een getallenconflict + gedeelde term is, anders 0.

    Eindscore:
        signal = shared_ratio * max(neg_score, num_score)

    Waarden liggen in [0, 1]. Een score > 0 vereist gedeelde inhoud EN een
    tegenstrijdigheidssignaal. Twee instemmende teksten scoren 0 of bijna 0.

    Args:
        text_a: Lichaamstekst van artikel A.
        text_b: Lichaamstekst van artikel B.

    Returns:
        Float in [0.0, 1.0]. Hoger = meer kans op tegenstrijdigheid.
    """
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)

    sig_a = _significant_tokens(tokens_a)
    sig_b = _significant_tokens(tokens_b)

    # 1. Gedeelde inhoudsratio
    shared = sig_a & sig_b
    shared_ratio = len(shared) / max(len(sig_a), len(sig_b), 1)

    if not shared:
        # Geen gedeeld onderwerp: geen tegenstrijdigheid mogelijk
        return 0.0

    # 2. Negatieasymmetrie
    neg_a = _NEGATION_TOKENS & set(tokens_a)
    neg_b = _NEGATION_TOKENS & set(tokens_b)
    # Asymmetrisch: één kant heeft negatie, de andere niet
    neg_asymmetric = bool(neg_a) != bool(neg_b)
    neg_score = 1.0 if neg_asymmetric else 0.0

    # 3. Getallenconflict
    nums_a = set(_NUMBER_RE.findall(text_a))
    nums_b = set(_NUMBER_RE.findall(text_b))
    # Getallen die exclusief in één tekst voorkomen
    exclusive_nums = nums_a.symmetric_difference(nums_b)
    num_score = 0.5 if exclusive_nums else 0.0

    signal = shared_ratio * max(neg_score, num_score)
    # Klem op [0, 1] als veiligheidsmaatregel
    return float(min(max(signal, 0.0), 1.0))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _collapse(text: str, cap: int = 160) -> str:
    """Comprimeer witruimte en kap af."""
    return re.sub(r"\s+", " ", text).strip()[:cap]


def _build_wiki_embeddings(wiki_dir: Path, cache: dict, eid: str) -> dict:
    """Bouw {str(path): vector} van gecachte wiki-artikelen."""
    candidates: dict = {}
    for md in sorted(wiki_dir.glob("*.md")):
        if md.name in ("index.md", "log.md"):
            continue
        key = str(md)
        entry = cache.get(key)
        if not entry:
            continue
        if entry.get("id") != eid:
            continue
        vec = entry.get("embedding")
        if not vec:
            continue
        candidates[key] = vec
    return candidates


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan KennisBank wiki op kandidaat-tegenstrijdige artikelparen.",
    )
    parser.add_argument(
        "--sim",
        type=str,
        default=None,
        metavar="T",
        help="Cosine-drempel voor kandidaatparen (default: env KB_CONFLICT_SIM of 0.62).",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Uitvoer als JSON in plaats van Markdown.",
    )
    args = parser.parse_args()

    # Drempel resolven (CLI > env > default)
    if args.sim is not None:
        try:
            sim_threshold = float(args.sim.strip().replace(",", "."))
        except ValueError:
            print(f"Ongeldige --sim waarde: {args.sim!r}", file=sys.stderr)
            sys.exit(1)
    else:
        sim_threshold = _threshold("KB_CONFLICT_SIM", 0.62)

    vault = vault_root()
    wiki_dir = vault / "02-wiki"

    if not wiki_dir.exists():
        print(f"Wiki-directory niet gevonden: {wiki_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        cache = load_cache()
    except Exception:
        cache = {}

    eid = embed_id()
    embeddings = _build_wiki_embeddings(wiki_dir, cache, eid)

    if not embeddings:
        msg = "Geen gecachte wiki-embeddings gevonden. Draai eerst build-embed-index.py."
        if args.as_json:
            print(json.dumps({"error": msg, "pairs": []}))
        else:
            print(f"# Conflictscan KennisBank\n\n_{msg}_")
        return

    pairs = candidate_pairs(embeddings, sim_threshold=sim_threshold)

    # Bereken tegenstrijdigheidsignaal voor elk paar
    results = []
    for path_a, path_b, cos_score in pairs:
        body_a = doc_text(path_a)
        body_b = doc_text(path_b)
        signal = contradiction_signal(body_a, body_b)

        # Frontmatter voor datums
        try:
            fm_a, _ = parse_frontmatter(Path(path_a).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            fm_a = {}
        try:
            fm_b, _ = parse_frontmatter(Path(path_b).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            fm_b = {}

        updated_a = fm_a.get("updated") or fm_a.get("date") or ""
        updated_b = fm_b.get("updated") or fm_b.get("date") or ""

        results.append({
            "path_a": path_a,
            "path_b": path_b,
            "updated_a": updated_a,
            "updated_b": updated_b,
            "cosine": round(cos_score, 4),
            "signal": round(signal, 4),
            "excerpt_a": _collapse(body_a),
            "excerpt_b": _collapse(body_b),
        })

    # Sorteer op signaal DESC (cosine als tiebreaker)
    results.sort(key=lambda r: (-r["signal"], -r["cosine"]))

    if args.as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    # Markdown-rapport
    from datetime import date as _date
    today = _date.today().isoformat()
    print(f"## Kandidaat-tegenstrijdige artikelparen (drempel: {sim_threshold}, {today})\n")

    if not results:
        print("Geen kandidaatparen gevonden boven de drempel.")
        return

    for i, r in enumerate(results, start=1):
        name_a = Path(r["path_a"]).name
        name_b = Path(r["path_b"]).name
        print(f"### {i}. {name_a} ↔ {name_b}")
        print(f"- **Cosine-gelijkenis:** {r['cosine']}")
        print(f"- **Tegenstrijdigheidssignaal:** {r['signal']}")
        print(f"- **Bijgewerkt A:** {r['updated_a'] or '(onbekend)'}")
        print(f"- **Bijgewerkt B:** {r['updated_b'] or '(onbekend)'}")
        print(f"- **Fragment A:** _{r['excerpt_a'] or '(leeg)'}_")
        print(f"- **Fragment B:** _{r['excerpt_b'] or '(leeg)'}_")
        print()

    print(f"Totaal: {len(results)} kandidaatpaar(en) gevonden.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Semantic tiling check voor KennisBank wiki.

Vergelijkt een wiki-artikel met alle andere via de gedeelde embedding-provider
(_embeddings.py) en flaggt near-duplicates op cosine similarity. De
embedding-backend is instelbaar (lokaal Ollama qwen3-embedding:8b standaard, of
een API-provider) via kennisbank-embed.json of de KB_EMBED_* env-vars; deze
check hoeft daar niets van te weten.

Gebruik: python3 semantic-tiling.py <pad-naar-artikel>

Drempels zijn modelspecifiek (verschillende modellen spreiden anders in de
cosine-ruimte). Default voor qwen3-embedding:8b: 0,85 (error) / 0,62 (review).
Wissel je van model, herijk dan via TILING_THRESHOLD_ERROR / TILING_THRESHOLD_REVIEW
zonder de code te wijzigen. De embedding-cache wordt per backend gesleuteld
(embed_id), dus cross-model vergelijkingen kunnen niet per ongeluk gebeuren.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

VAULT_ROOT = vault_root()
WIKI_DIR = VAULT_ROOT / "02-wiki"


def _threshold(env_var: str, default: float) -> float:
    """Lees een cosine-drempel uit een env-var, robuust tegen onzin.

    Accepteert NL-decimaalnotatie (0,85) en spaties; bij een lege of ongeldige
    waarde valt het terug op de default met een waarschuwing op stderr.
    """
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


THRESHOLD_ERROR = _threshold("TILING_THRESHOLD_ERROR", 0.85)
THRESHOLD_REVIEW = _threshold("TILING_THRESHOLD_REVIEW", 0.62)


def main() -> None:
    if len(sys.argv) < 2:
        print("Gebruik: semantic-tiling.py <pad-naar-artikel>", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()
    if not target.exists():
        print(f"Bestand niet gevonden: {target}", file=sys.stderr)
        sys.exit(1)

    cache = emb.load_cache()

    # Prune cache entries voor verdwenen wiki-bestanden.
    existing = {str(p) for p in WIKI_DIR.glob("**/*.md")}
    for k in [k for k in cache if k.startswith(str(WIKI_DIR)) and k not in existing]:
        del cache[k]

    if not emb.doc_text(target).strip():
        print("Leeg bestand, tiling overgeslagen.")
        emb.save_cache(cache)
        return

    target_embedding = emb.get_cached(target, cache)
    if target_embedding is None:
        print(
            f"Embedding mislukt. Is de backend bereikbaar? (backend: {emb.embed_id()})",
            file=sys.stderr,
        )
        sys.exit(1)

    errors = []
    reviews = []

    for wiki_file in sorted(WIKI_DIR.glob("**/*.md")):
        if wiki_file.resolve() == target:
            continue
        if wiki_file.name in ("index.md", "log.md"):
            continue

        other_embedding = emb.get_cached(wiki_file, cache)
        if other_embedding is None:
            continue

        score = emb.cosine(target_embedding, other_embedding)
        rel_path = wiki_file.relative_to(WIKI_DIR)

        if score >= THRESHOLD_ERROR:
            errors.append((score, str(rel_path)))
        elif score >= THRESHOLD_REVIEW:
            reviews.append((score, str(rel_path)))

    emb.save_cache(cache)

    if not errors and not reviews:
        print(f"OK - geen near-duplicates gevonden voor {target.name}")
        return

    if errors:
        print(f"\nERROR - mogelijke duplicaten (score >= {THRESHOLD_ERROR}):")
        for score, path in sorted(errors, reverse=True):
            print(f"  {score:.3f}  {path}")

    if reviews:
        print(f"\nREVIEW - verwante artikelen ({THRESHOLD_REVIEW}-{THRESHOLD_ERROR - 0.001:.3f}):")
        for score, path in sorted(reviews, reverse=True):
            print(f"  {score:.3f}  {path}")

    print("\nActie: samenvoegen, verwijzen vanuit het nieuwe artikel, of negeren als de overlap inhoudelijk gerechtvaardigd is.")


if __name__ == "__main__":
    main()

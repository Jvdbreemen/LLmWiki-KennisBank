#!/usr/bin/env python3
"""
Semantic tiling check voor KennisBank wiki.
Vergelijkt een wiki-artikel met alle andere artikelen via Ollama-embeddings.
Flaggt near-duplicates op basis van cosine similarity.

Gebruik: python3 semantic-tiling.py <pad-naar-artikel>

Vereist: ollama met een embedding-model (default: nomic-embed-text).
  ollama pull nomic-embed-text
Model instelbaar via de OLLAMA_EMBED_MODEL omgevingsvariabele (bv. een
meertalig model als qwen3-embedding:8b; nomic-embed-text v1.5 is Engels-only).
"""

import os
import sys
import json
import math
import hashlib
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _frontmatter import split_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

VAULT_ROOT = vault_root()
WIKI_DIR = VAULT_ROOT / "02-wiki"
CACHE_FILE = VAULT_ROOT / ".claude" / "embeddings-cache.json"
OLLAMA_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")

THRESHOLD_ERROR = 0.90
THRESHOLD_REVIEW = 0.80


def get_text(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8")
        # Strip YAML frontmatter (anchored fence; avoids horizontal-rule false positives)
        _, body = split_frontmatter(content)
        return body.strip()[:4000]  # Cap at ~4k chars for embedding
    except Exception:
        return ""


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]


def get_embedding(text: str) -> list[float] | None:
    """
    Roept de Ollama HTTP API aan voor embeddings.
    De CLI-subcommand `ollama embed` bestaat niet meer in recente Ollama versies;
    de HTTP API op localhost:11434 is de stabiele route.
    """
    import urllib.request
    import urllib.error
    try:
        payload = json.dumps({"model": OLLAMA_MODEL, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("embedding") or data.get("embeddings", [None])[0]
    except Exception:
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def get_cached_embedding(path: Path, cache: dict) -> list[float] | None:
    key = str(path)
    h = file_hash(path)
    entry = cache.get(key)
    if entry and entry.get("hash") == h and entry.get("model") == OLLAMA_MODEL:
        return entry["embedding"]
    # Recompute
    text = get_text(path)
    if not text:
        return None
    embedding = get_embedding(text)
    if embedding:
        cache[key] = {"hash": h, "model": OLLAMA_MODEL, "embedding": embedding}
    return embedding


def prune_cache(cache: dict) -> None:
    existing = {str(p) for p in WIKI_DIR.glob("**/*.md")}
    stale = [k for k in cache if k not in existing]
    for k in stale:
        del cache[k]


def main() -> None:
    if len(sys.argv) < 2:
        print("Gebruik: semantic-tiling.py <pad-naar-artikel>", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()
    if not target.exists():
        print(f"Bestand niet gevonden: {target}", file=sys.stderr)
        sys.exit(1)

    cache = load_cache()
    prune_cache(cache)

    target_text = get_text(target)
    if not target_text.strip():
        print("Leeg bestand, tiling overgeslagen.")
        save_cache(cache)
        return

    target_embedding = get_cached_embedding(target, cache)
    if target_embedding is None:
        print("Embedding mislukt. Is nomic-embed-text geïnstalleerd?", file=sys.stderr)
        sys.exit(1)

    errors = []
    reviews = []

    for wiki_file in sorted(WIKI_DIR.glob("**/*.md")):
        if wiki_file.resolve() == target:
            continue
        if wiki_file.name in ("index.md", "log.md"):
            continue

        other_embedding = get_cached_embedding(wiki_file, cache)
        if other_embedding is None:
            continue

        score = cosine_similarity(target_embedding, other_embedding)
        rel_path = wiki_file.relative_to(WIKI_DIR)

        if score >= THRESHOLD_ERROR:
            errors.append((score, str(rel_path)))
        elif score >= THRESHOLD_REVIEW:
            reviews.append((score, str(rel_path)))

    save_cache(cache)

    if not errors and not reviews:
        print(f"OK — geen near-duplicates gevonden voor {target.name}")
        return

    if errors:
        print(f"\nERROR — mogelijke duplicaten (score >= {THRESHOLD_ERROR}):")
        for score, path in sorted(errors, reverse=True):
            print(f"  {score:.3f}  {path}")

    if reviews:
        print(f"\nREVIEW — verwante artikelen ({THRESHOLD_REVIEW}–{THRESHOLD_ERROR - 0.001:.3f}):")
        for score, path in sorted(reviews, reverse=True):
            print(f"  {score:.3f}  {path}")

    print("\nActie: samenvoegen, verwijzen vanuit het nieuwe artikel, of negeren als de overlap inhoudelijk gerechtvaardigd is.")


if __name__ == "__main__":
    main()

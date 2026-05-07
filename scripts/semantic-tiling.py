#!/usr/bin/env python3
"""
Semantic tiling check voor KennisBank wiki.
Vergelijkt een wiki-artikel met alle andere artikelen via Ollama-embeddings.
Flaggt near-duplicates op basis van cosine similarity.

Gebruik: python3 semantic-tiling.py <pad-naar-artikel>

Vereist: ollama met nomic-embed-text model
  ollama pull nomic-embed-text
"""

import sys
import json
import math
import hashlib
import subprocess
from pathlib import Path

WIKI_DIR = Path.home() / "KennisBank" / "02-wiki"
CACHE_FILE = Path.home() / "KennisBank" / ".claude" / "embeddings-cache.json"
OLLAMA_MODEL = "nomic-embed-text"

THRESHOLD_ERROR = 0.90
THRESHOLD_REVIEW = 0.80


def get_text(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8")
        # Strip YAML frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()
        return content[:4000]  # Cap at ~4k chars for embedding
    except Exception:
        return ""


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]


def get_embedding(text: str) -> list[float] | None:
    try:
        result = subprocess.run(
            ["ollama", "embed", "--model", OLLAMA_MODEL],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
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
    if entry and entry.get("hash") == h:
        return entry["embedding"]
    # Recompute
    text = get_text(path)
    if not text:
        return None
    embedding = get_embedding(text)
    if embedding:
        cache[key] = {"hash": h, "embedding": embedding}
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
        if wiki_file.name == "index.md":
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

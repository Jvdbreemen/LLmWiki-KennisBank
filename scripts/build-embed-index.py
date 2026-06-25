#!/usr/bin/env python3
"""Warm/refresh the KennisBank wiki embedding cache.

Runs OFF the per-prompt latency path: invoked once per session from a
SessionStart hook (and runnable standalone). Embeds every wiki article whose
file hash or embed_id() has changed, prunes vanished files, and clears the
graphify .needs-rebuild flag. Steady-state (cache warm) is just hash checks and
near-instant; only new/changed files or a model switch trigger real embed calls.

It also warms the local embedding model: the first embed loads it, so by the
time the user types a real prompt the per-prompt retrieval hook is fast.

Stdlib only. Usage: python build-embed-index.py
"""
import os
import sys
from pathlib import Path

# Self-locate the vault so the hook works even if KENNISBANK_VAULT is not present
# in the hook subprocess env: this script lives at <vault>/.claude/scripts/.
os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

VAULT = vault_root()
WIKI = VAULT / "02-wiki"
REBUILD_FLAG = VAULT / "graphify-out" / ".needs-rebuild"
SKIP = {"index.md", "log.md"}


def main() -> None:
    # Toggle-gate: ververs de embed-index alleen als embed_index aanstaat.
    # Fail-open: kan de toggle niet gelezen worden, val terug op de default
    # (True = aan). De gate zit vóór de .needs-rebuild-clear en elke embed-call.
    try:
        import _settings
        if not _settings.get("embed_index", True):
            print("embed-index: uitgeschakeld via settings (embed_index=false)")
            return
    except Exception:
        pass
    if not WIKI.exists():
        print("embed-index: geen 02-wiki/, overgeslagen")
        return

    cache = emb.load_cache()

    # Prune cache entries for wiki files that no longer exist.
    existing = {str(p) for p in WIKI.glob("**/*.md")}
    wiki_prefix = str(WIKI)
    for k in [k for k in cache if k.startswith(wiki_prefix) and k not in existing]:
        del cache[k]

    embedded = 0
    failed = 0
    files = [f for f in sorted(WIKI.glob("**/*.md")) if f.name not in SKIP]
    for f in files:
        before = cache.get(str(f), {})
        vec = emb.get_cached(f, cache)
        after = cache.get(str(f), {})
        if vec is None:
            failed += 1
        elif after.get("hash") != before.get("hash") or after.get("id") != before.get("id"):
            embedded += 1

    emb.save_cache(cache)

    # Best-effort clear of the rebuild flag (graphify-out/.needs-rebuild).
    try:
        if REBUILD_FLAG.exists():
            REBUILD_FLAG.unlink()
    except Exception:
        pass

    print(f"embed-index: {len(files)} wiki files, {embedded} (re)embedded, "
          f"{failed} failed, backend={emb.embed_id()}")
    if failed and embedded == 0:
        # Backend unreachable (e.g. ollama down / API key missing): not fatal.
        print("embed-index: embedding-backend onbereikbaar; retrieval valt stil terug",
              file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Never fail a SessionStart hook.
        print(f"embed-index: overgeslagen ({e})", file=sys.stderr)

#!/usr/bin/env python3
"""UserPromptSubmit hook: inject relevant KennisBank wiki snippets for a prompt.

Embeds the user's prompt once, cosine-matches it against the cached wiki
embeddings (built off-path by build-embed-index.py), and injects the top matches
above a threshold as additionalContext.

FAIL-OPEN, ALWAYS: any error, missing backend, empty cache, or trivial prompt
results in no output and exit 0. The hook never blocks, never raises, and never
delays a prompt beyond the embed call. A wrong-but-silent outcome here is a miss,
not a breakage.

Cross-model safety: only cache entries whose stored embed_id() (provider:model)
matches the active backend are eligible, and dimensions must match. After a model
switch the cache is cold until the next SessionStart rebuild; until then this
hook simply injects nothing.

Output contract (verified against the local caveman UserPromptSubmit hook):
  stdout = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                    "additionalContext": "..."}}

Requires KENNISBANK_VAULT in the environment (set in the global settings env).
"""
import json
import os
import sys
from pathlib import Path

# Trivial prompts that are not worth an embed (continuation/ack/command noise).
_TRIVIAL = {
    "go", "continue", "keep going", "yes", "no", "ok", "okay", "y", "n",
    "next", "stop", "proceed", "do it", "ja", "nee", "ga door", "verder",
    "klaar", "done", "thanks", "thank you", "dank je", "more", "again",
}


def _emit(ctx: str) -> None:
    if ctx:
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": ctx,
            }
        }))


def _num(env: str, cfg: dict, key: str, default):
    raw = os.environ.get(env)
    if raw is None and isinstance(cfg.get(key), (int, float)):
        return type(default)(cfg[key])
    if raw is None:
        return default
    try:
        return type(default)(str(raw).strip().replace(",", "."))
    except ValueError:
        return default


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        return
    try:
        data = json.loads(raw)
    except Exception:
        return
    prompt = (data.get("prompt") or "").strip()

    # Cheap pre-filter BEFORE spending an embed: short, slash-command, or trivial.
    low = prompt.lower()
    if len(prompt) < 15 or prompt.startswith("/") or low in _TRIVIAL:
        return

    # Self-locate the vault if KENNISBANK_VAULT is absent from the hook env
    # (this script lives at <vault>/.claude/scripts/).
    os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import _embeddings as emb
        from _vaultpath import vault_root
    except Exception:
        return

    cache = emb.load_cache()
    if not cache:
        return

    eid = emb.embed_id()
    wiki_prefix = str(vault_root() / "02-wiki")
    candidates = [
        (k, v) for k, v in cache.items()
        if k.startswith(wiki_prefix) and v.get("id") == eid and v.get("embedding")
    ]
    if not candidates:
        return

    cfg = {}
    cfg_file = vault_root() / ".claude" / "kennisbank-embed.json"
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}

    timeout = _num("KB_RETRIEVE_TIMEOUT", cfg, "retrieve_timeout", 20.0)
    qvec = emb.embed(prompt, timeout=timeout)
    if not qvec:
        return

    top_n = _num("KB_RETRIEVE_TOP_N", cfg, "retrieve_top_n", 3)
    threshold = _num("KB_RETRIEVE_THRESHOLD", cfg, "retrieve_threshold", 0.60)

    scored = []
    for k, v in candidates:
        if v.get("dim") and v["dim"] != len(qvec):
            continue
        s = emb.cosine(qvec, v["embedding"])
        if s >= threshold:
            scored.append((s, k))
    if not scored:
        return

    scored.sort(reverse=True)
    lines = ["KennisBank-wiki (semantisch gematcht op je prompt; raadpleeg bij twijfel):"]
    for s, k in scored[:int(top_n)]:
        p = Path(k)
        snippet = emb.doc_text(p, cap=280).replace("\n", " ").strip()
        lines.append(f"- [[{p.stem}]] ({s:.2f}): {snippet}")
    _emit("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail-open: never break a prompt

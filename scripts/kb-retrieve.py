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


def _wiki_block(prompt, emb, vault_root, cfg):
    """Bestaande wiki-cosine-logica. Geeft (wiki_tekst_of_leeg, qvec_of_None).

    qvec wordt teruggegeven zodat de memory-lookup 'm kan hergebruiken."""
    cache = emb.load_cache()
    if not cache:
        return "", None
    eid = emb.embed_id()
    wiki_prefix = str(vault_root() / "02-wiki")
    candidates = [
        (k, v) for k, v in cache.items()
        if k.startswith(wiki_prefix) and v.get("id") == eid and v.get("embedding")
    ]
    if not candidates:
        return "", None
    timeout = _num("KB_RETRIEVE_TIMEOUT", cfg, "retrieve_timeout", 20.0)
    qvec = emb.embed(prompt, timeout=timeout)
    if not qvec:
        return "", None
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
        return "", qvec
    scored.sort(reverse=True)
    lines = ["KennisBank-wiki (semantisch gematcht op je prompt; raadpleeg bij twijfel):"]
    for s, k in scored[:int(top_n)]:
        p = Path(k)
        snippet = emb.doc_text(p, cap=280).replace("\n", " ").strip()
        lines.append(f"- [[{p.stem}]] ({s:.2f}): {snippet}")
    return "\n".join(lines), qvec


def _memory_block(qvec, prompt, cfg):
    """Additief memory-blok via kb-recall. Leeg bij geen hits / fail-soft."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
        kb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(kb)
        top_n = _num("KB_RECALL_TOP_N", cfg, "memory_top_n", 3)
        hits = kb.memory_hits(qvec, query_text=prompt, k=int(top_n))
    except Exception:
        return ""
    if not hits:
        return ""
    lines = ["KennisBank-geheugen (eerdere sessies/lessons; mogelijk relevant):"]
    for h in hits:
        stem = Path(h["path"]).stem
        lines.append(f"- [[{stem}]] ({h['score']:.2f}): {h['snippet']}")
    return "\n".join(lines)


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        return
    try:
        data = json.loads(raw)
    except Exception:
        return
    prompt = (data.get("prompt") or "").strip()
    low = prompt.lower()
    if len(prompt) < 15 or prompt.startswith("/") or low in _TRIVIAL:
        return

    os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import _embeddings as emb
        from _vaultpath import vault_root
    except Exception:
        return

    cfg = {}
    cfg_file = vault_root() / ".claude" / "kennisbank-embed.json"
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}

    wiki_text, qvec = _wiki_block(prompt, emb, vault_root, cfg)

    mem_text = ""
    try:
        import _settings
        memory_on = _settings.get("memory_recall", True)
    except Exception:
        memory_on = True
    if memory_on:
        if qvec is None:
            timeout = _num("KB_RETRIEVE_TIMEOUT", cfg, "retrieve_timeout", 20.0)
            qvec = emb.embed(prompt, timeout=timeout)
        if qvec:
            mem_text = _memory_block(qvec, prompt, cfg)

    parts = [t for t in (wiki_text, mem_text) if t]
    if parts:
        _emit("\n\n".join(parts))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail-open: never break a prompt

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
import importlib.util as _ilu
import json
import os
import sys
from pathlib import Path

# kb-recall als module-globaal zodat tests het kunnen patchen (idem kb-presearch).
kb_recall = None
try:
    _krspec = _ilu.spec_from_file_location(
        "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
    kb_recall = _ilu.module_from_spec(_krspec)
    _krspec.loader.exec_module(kb_recall)
except Exception:
    kb_recall = None

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
    """Hybride wiki-injectie. Gate = cosine-relevant OF FTS-keyword-match.
    Selectie via kb_recall.wiki_hits (hybride); fallback naar de cosine-cache.
    Geeft (wiki_tekst_of_leeg, qvec_of_None)."""
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
    top_n = int(_num("KB_RETRIEVE_TOP_N", cfg, "retrieve_top_n", 3))
    threshold = _num("KB_RETRIEVE_THRESHOLD", cfg, "retrieve_threshold", 0.60)

    # cosine-signaal (ongewijzigde semantische gate) + de cosine-cache-fallback-lijst
    scored = []
    for k, v in candidates:
        if v.get("dim") and v["dim"] != len(qvec):
            continue
        s = emb.cosine(qvec, v["embedding"])
        scored.append((s, k))
    scored.sort(reverse=True)
    cosine_relevant = bool(scored) and scored[0][0] >= threshold

    # FTS-signaal (exacte termen die vector mist)
    fts_relevant = False
    if kb_recall is not None:
        try:
            fts_relevant = kb_recall.has_fts_match(prompt, layer="wiki")
        except Exception:
            fts_relevant = False

    if not (cosine_relevant or fts_relevant):
        return "", qvec

    # Selectie: hybride via kb-index; fallback naar cosine-cache-top-N.
    # Graafbuur-expansie (één hop langs wikilinks) staat default aan;
    # uitschakelen met KB_RETRIEVE_EXPAND=0 of "retrieve_expand": 0 in config.
    expand = bool(int(_num("KB_RETRIEVE_EXPAND", cfg, "retrieve_expand", 1)))
    hits = []
    if kb_recall is not None:
        try:
            hits = kb_recall.wiki_hits(qvec, query_text=prompt, k=top_n, expand=expand)
        except Exception:
            hits = []
    lines = ["KennisBank-wiki (semantisch gematcht op je prompt; raadpleeg bij twijfel):"]
    if hits:
        for h in hits:
            stem = Path(h.get("path", "")).stem
            label = " (buur)" if h.get("neighbor") else f" ({h.get('score', 0.0):.2f})"
            lines.append(f"- [[{stem}]]{label}: {h.get('snippet', '')}")
    else:
        # fallback: oude cosine-cache-selectie (alleen treffers >= drempel)
        relevant = [(s, k) for s, k in scored if s >= threshold][:top_n]
        if not relevant:
            return "", qvec
        for s, k in relevant:
            p = Path(k)
            snippet = emb.doc_text(p, cap=280).replace("\n", " ").strip()
            lines.append(f"- [[{p.stem}]] ({s:.2f}): {snippet}")
    return "\n".join(lines), qvec


def _memory_block(qvec, prompt, cfg, hits_fn=None):
    """Additief memory-blok via kb-recall. Leeg bij geen hits / fail-soft.

    hits_fn: optionele injectable callable met dezelfde signatuur als
    kb_recall.memory_hits (qvec, query_text, k) -> list. Standaard wordt
    kb-recall.py via importlib geladen (gedrag ongewijzigd). Testbaar zonder
    Ollama door hits_fn=<stub> mee te geven (MINOR 2).
    """
    try:
        if hits_fn is None:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
            kb = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(kb)
            hits_fn = kb.memory_hits
        top_n = _num("KB_RECALL_TOP_N", cfg, "memory_top_n", 3)
        hits = hits_fn(qvec, query_text=prompt, k=int(top_n))
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

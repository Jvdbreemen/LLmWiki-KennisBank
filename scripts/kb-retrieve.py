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
import math
import os
import sys
from pathlib import Path

# The Claude hook ceiling is deliberately much larger, but the interactive
# embedding request must leave ample time for local ranking, JSON emission, and
# process shutdown. A cold or unavailable model is a cache miss, not a reason
# to hold the user's prompt.
_DEFAULT_PROMPT_EMBED_TIMEOUT = 2.0

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
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": ctx,
            }
        }))


def _emit_notice(text: str) -> None:
    """Meld een gemiste injectie ZICHTBAAR, in plaats van stil terug te keren.

    Verschil met _emit: suppressOutput staat hier op False. Een geslaagde
    injectie hoort onzichtbaar te zijn (noord-ster: uit de weg blijven), maar
    een MISSER hoort de gebruiker te bereiken -- anders denkt hij dat de
    kennisbank meekeek terwijl dat niet zo was, en dat is erger dan geen
    kennisbank. De tekst gaat ook als additionalContext mee, zodat het model
    weet dat het deze beurt zonder vault-context werkt.
    """
    if not text:
        return
    sys.stdout.write(json.dumps({
        "suppressOutput": False,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": text,
        }
    }))


#: Onder deze leeftijd (seconden) draait er al een warm-up van een eerdere
#: prompt; dan is "wordt nu opgewarmd" onwaar en past een andere formulering.
#: Spiegelt het min_interval van _embeddings.warm_async().
_WARM_SENTINEL_WINDOW = 60.0


def _warm_already_running(emb) -> bool:
    """True als er binnen het sentinel-venster al een warm-up gestart is."""
    try:
        import time as _time
        marker = emb._warm_marker()
        return marker.exists() and (_time.time() - marker.stat().st_mtime) < _WARM_SENTINEL_WINDOW
    except Exception:
        return False


def _cold_notice(already_warming: bool, timeout: float) -> str:
    """Bouw de melding voor een gemiste injectie door een koud model."""
    kern = (f"KennisBank: geen kennis opgehaald bij deze prompt. Het lokale "
            f"embedding-model reageerde niet binnen {timeout:g}s "
            f"(hot-path-budget); een koude modelload duurt tientallen seconden.")
    if already_warming:
        staart = ("Er loopt al een opwarm-actie op de achtergrond. Stel je vraag zo "
                  "nog eens; zodra het model geladen is werkt het ophalen weer.")
    else:
        staart = ("Het model wordt nu op de achtergrond geladen. Deze hook kan niet "
                  "zelf opnieuw proberen (dat zou je prompt blokkeren), dus: stel je "
                  "vraag over ~30 seconden opnieuw, dan komt de context er wel bij.")
    return kern + " " + staart


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


def _prompt_embed_timeout(cfg: dict) -> float:
    """Return the bounded timeout for the interactive embedding request.

    ``KB_RETRIEVE_TIMEOUT`` remains the requested timeout for compatibility,
    but cannot exceed the prompt-hook ceiling by accident. Raising
    ``KB_PROMPT_HOOK_MAX_EMBED_TIMEOUT`` (or its config equivalent) is the
    explicit opt-in for a slower interactive path.
    """
    requested = float(_num(
        "KB_RETRIEVE_TIMEOUT",
        cfg,
        "retrieve_timeout",
        _DEFAULT_PROMPT_EMBED_TIMEOUT,
    ))
    ceiling = float(_num(
        "KB_PROMPT_HOOK_MAX_EMBED_TIMEOUT",
        cfg,
        "prompt_hook_max_embed_timeout",
        _DEFAULT_PROMPT_EMBED_TIMEOUT,
    ))
    if not math.isfinite(requested):
        requested = _DEFAULT_PROMPT_EMBED_TIMEOUT
    if not math.isfinite(ceiling):
        ceiling = _DEFAULT_PROMPT_EMBED_TIMEOUT
    return min(max(requested, 0.1), max(ceiling, 0.1))


def _wiki_block(prompt, emb, vault_root, cfg, qvec):
    """Hybride wiki-injectie voor een reeds berekende query-embedding qvec.
    Gate = cosine-relevant OF FTS-keyword-match. Selectie via kb_recall.wiki_hits
    (hybride); fallback naar de cosine-cache. Geeft wiki-tekst of "".

    qvec wordt eenmalig in main() berekend en aan zowel dit blok als het memory-
    blok doorgegeven: op de hot path embedden we nooit twee keer."""
    top_n = int(_num("KB_RETRIEVE_TOP_N", cfg, "retrieve_top_n", 3))
    threshold = _num("KB_RETRIEVE_THRESHOLD", cfg, "retrieve_threshold", 0.60)
    expand = bool(int(_num("KB_RETRIEVE_EXPAND", cfg, "retrieve_expand", 1)))

    # Snelle weg: de index doet zelf de poort (min_cos) en de selectie. Alleen
    # wanneer de index dat ECHT kan -- geldig voor het live model en met
    # genormaliseerde vectoren. Op een index van vóór die wijziging negeert
    # search() de drempel, en zou dit blok onvoorwaardelijk gaan injecteren:
    # slechter dan het cache-pad hieronder. Eén sqlite-open, geen JSON van
    # tientallen megabytes.
    if kb_recall is not None:
        try:
            if kb_recall.index_is_gated():
                hits = kb_recall.wiki_hits(qvec, query_text=prompt, k=top_n,
                                           expand=expand, min_cos=threshold)
                if not hits:
                    return ""
                lines = ["KennisBank-wiki (semantisch gematcht op je prompt; raadpleeg bij twijfel):"]
                for h in hits:
                    stem = Path(h.get("path", "")).stem
                    label = " (buur)" if h.get("neighbor") else f" ({h.get('score', 0.0):.2f})"
                    lines.append(f"- [[{stem}]]{label}: {h.get('snippet', '')}")
                return "\n".join(lines)
        except Exception:
            pass  # val terug op het cache-pad hieronder

    # Terugvalweg: ontbrekende, ongeldige of nog niet genormaliseerde index.
    # Parseert de volledige embedding-cache (tientallen MB) en scoort in pure
    # Python -- traag, maar het houdt een vault met kapotte index werkend.
    cache = emb.load_cache()
    if not cache:
        return ""
    eid = emb.embed_id()
    wiki_prefix = str(vault_root() / "02-wiki")
    candidates = [
        (k, v) for k, v in cache.items()
        if k.startswith(wiki_prefix) and v.get("id") == eid and v.get("embedding")
    ]
    if not candidates:
        return ""
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
        return ""

    # Selectie: hybride via kb-index; fallback naar cosine-cache-top-N.
    # Graafbuur-expansie (één hop langs wikilinks) staat default aan;
    # uitschakelen met KB_RETRIEVE_EXPAND=0 of "retrieve_expand": 0 in config.
    hits = []
    if kb_recall is not None:
        try:
            # Zelfde drempel als de poort hierboven: wat de gate niet zou
            # openen, hoort ook niet als losse treffer geinjecteerd te worden.
            hits = kb_recall.wiki_hits(qvec, query_text=prompt, k=top_n,
                                       expand=expand, min_cos=threshold)
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
            return ""
        for s, k in relevant:
            p = Path(k)
            snippet = emb.doc_text(p, cap=280).replace("\n", " ").strip()
            lines.append(f"- [[{p.stem}]] ({s:.2f}): {snippet}")
    return "\n".join(lines)


def _provenance_tag(path: str) -> str:
    """Deterministische herkomst/status-tag voor een geinjecteerde MEMORY.

    Leest evidence_basis + status uit de frontmatter van het memory-bestand
    (die velden zitten NIET in het hit-dict) via de bestaande frontmatter-parser
    en delegeert de vormgeving aan _memory.provenance_tag. Puur lookup, geen LLM.
    Fail-soft: welke fout dan ook -> "" (geen tag, nooit crash).
    """
    try:
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from _frontmatter import parse_frontmatter
        import _memory
        fm, _ = parse_frontmatter(
            Path(path).read_text(encoding="utf-8", errors="replace"))
        return _memory.provenance_tag(fm.get("evidence_basis", ""), fm.get("status", ""))
    except Exception:
        return ""


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
        # Herkomst-tag per memory (evidence_basis+status uit frontmatter). WIKI-hits
        # in _wiki_block blijven bewust ongetagd: die zijn evergreen/gecureerd.
        tag = _provenance_tag(h.get("path", ""))
        tag_txt = f" {tag}" if tag else ""
        lines.append(f"- [[{stem}]] ({h['score']:.2f}){tag_txt}: {h['snippet']}")
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

    # Eén embed voor de hele hook. Hot path (noord-ster #1): sub-seconde, korte
    # timeout. Bij een cold model komt qvec niet op tijd terug -> we injecteren
    # niets deze prompt (fail-soft: een miss, geen breuk) en vuren een detached
    # warm zodat de VOLGENDE prompt hot is. Nooit blokkeren, nooit 2x embedden.
    timeout = _prompt_embed_timeout(cfg)
    qvec = emb.embed(prompt, timeout=timeout)
    if qvec is None:
        # Stil terugkeren was hier de fout: de gebruiker denkt dan dat de
        # kennisbank meekeek terwijl er niets is opgehaald. Melden dus, en
        # daarna alsnog de detached warm zodat de volgende prompt hot is.
        already = _warm_already_running(emb)
        try:
            emb.warm_async()
        except Exception:
            pass
        try:
            _emit_notice(_cold_notice(already, timeout))
        except Exception:
            pass  # fail-open blijft leidend: een melding mag nooit de prompt breken
        return

    wiki_text = _wiki_block(prompt, emb, vault_root, cfg, qvec)

    mem_text = ""
    try:
        import _settings
        memory_on = _settings.get("memory_recall", True)
    except Exception:
        memory_on = True
    if memory_on:
        mem_text = _memory_block(qvec, prompt, cfg)

    parts = [t for t in (wiki_text, mem_text) if t]
    if parts:
        ctx = "\n\n".join(parts)
        _emit(ctx)
        # Feedbackloop: registreer welke stems geinjecteerd zijn, zodat
        # kb-usage-scan.py (SessionEnd) daadwerkelijk gebruik kan meten.
        # Fail-open: telemetrie mag de hook nooit vertragen of breken.
        try:
            import re as _re2
            import _usage
            stems = sorted({m for m in _re2.findall(r"\[\[([^\[\]|#]+)\]\]", ctx)})
            _usage.log_injected(stems, session_id=str(data.get("session_id") or ""))
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail-open: never break a prompt

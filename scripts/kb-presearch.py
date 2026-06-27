#!/usr/bin/env python3
"""kb-presearch.py - PreToolUse-hook: check eerst je eigen geheugen.

Vuurt vlak vóór een WebSearch/WebFetch. Embedt de zoekquery, haalt relevante
memory(current)+wiki-hits uit kb-index.db, en injecteert ze als additionalContext
met permissionDecision 'defer' (de tool gaat gewoon door). Zo raadpleegt de agent
ALTIJD eerst z'n eigen kennis bij een externe zoekactie, niet alleen aan turn-start.

FAIL-OPEN: elke fout / lege query / geen hits / model onbereikbaar -> geen output,
exit 0. Blokkeert nooit een tool. Gegate op memory_recall.

Output-contract (PreToolUse):
  {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                          "permissionDecision": "defer",
                          "additionalContext": "..."}}
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

_SEARCH_TOOLS = {"WebSearch", "WebFetch"}

# ---------------------------------------------------------------------------
# Module-level kb_recall attribuut — geladen bij import zodat tests het kunnen
# monkeypatchen via m.kb_recall.recall_hits = ...
# Fail-open: als laden mislukt (b.v. sqlite_vec ontbreekt), blijft het None
# en de fallback in main() doet een latere poging.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

kb_recall = None
try:
    _spec = importlib.util.spec_from_file_location(
        "kb_recall", os.path.join(_SCRIPTS_DIR, "kb-recall.py"))
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    kb_recall = _mod
except Exception:
    pass


def query_of(tool_name: str, tool_input: dict) -> str:
    """Extraheer de effectieve zoektekst uit het tool-input-dict."""
    if not isinstance(tool_input, dict):
        return ""
    if tool_name == "WebSearch":
        return str(tool_input.get("query", "")).strip()
    if tool_name == "WebFetch":
        url = str(tool_input.get("url", "")).strip()
        prompt = str(tool_input.get("prompt", "")).strip()
        return (url + " " + prompt).strip()
    return ""


def build_context(hits: list) -> str:
    """Bouw een leesbare tekst van recall-hits voor additionalContext."""
    if not hits:
        return ""
    lines = ["Je eigen KennisBank bevat hier mogelijk al kennis over (check dit eerst):"]
    for h in hits:
        tag = "geheugen" if h.get("layer") == "memory" else "wiki"
        stem = Path(h.get("path", "")).stem
        title = h.get("title", "") or stem
        lines.append(f"- [{tag}] [[{stem}|{title}]] ({h.get('score', 0.0):.2f}): {h.get('snippet', '')}")
    return "\n".join(lines)


def _emit(ctx: str) -> None:
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "defer",
            "additionalContext": ctx,
        }
    }))


def main(stdin_text: str | None = None) -> int:
    """Hook-entrypoint. stdin_text=None leest van stdin (productie);
    anders gebruikt main() de meegegeven tekst (testpad)."""
    raw = stdin_text if stdin_text is not None else sys.stdin.read()
    if not raw or not raw.strip():
        return 0
    try:
        data = json.loads(raw)
    except Exception:
        return 0

    tool_name = data.get("tool_name", "")
    if tool_name not in _SEARCH_TOOLS:
        return 0

    # Memory_recall-gate: fail-open als _settings niet laadbaar is.
    try:
        import _settings
        if not _settings.get("memory_recall", True):
            return 0
    except Exception:
        pass

    query = query_of(tool_name, data.get("tool_input", {}))
    if len(query) < 4:
        return 0

    try:
        import _embeddings as emb
        qvec = emb.embed(query)
        if not qvec:
            return 0

        # Gebruik het module-globale kb_recall (patchbaar door tests).
        # BELANGRIJK: wijs NIET toe aan kb_recall zelf — dat maakt het lokaal
        # in Python's scoping en breekt de monkeypatch. Gebruik een alias.
        kr = kb_recall
        if kr is None:
            # Productie-fallback als het module-level laden misluke.
            _s = importlib.util.spec_from_file_location(
                "kb_recall", os.path.join(_SCRIPTS_DIR, "kb-recall.py"))
            _m = importlib.util.module_from_spec(_s)
            _s.loader.exec_module(_m)
            kr = _m

        hits = kr.recall_hits(qvec, query_text=query, k=4, layers=("wiki", "memory"))
    except Exception:
        return 0

    ctx = build_context(hits)
    if ctx:
        _emit(ctx)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

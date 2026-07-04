#!/usr/bin/env python3
"""kb-mcp.py - lokale stdio MCP-server over de KennisBank (memory + wiki).

Het universele, ecosysteem-onafhankelijke oppervlak van de KennisBank (TASK-22):
elke MCP-client die op DEZELFDE machine draait (Claude Code, Cursor, Codex CLI,
GitHub Copilot in VS Code, Cline, Windsurf, LM Studio, Claude Desktop) kan de
vault gebruiken zonder platform-specifieke hook. MCP is het enige protocol dat
al die omgevingen al spreken, dus dit is het brede-bereik-oppervlak.

Drie primitieven:
  - recall (tool)        : doorzoek geheugen+wiki (PULL-retrieval). Read-only.
  - capture (tool)       : leg een nieuwe memory vast (PULL-write). Landt als
                           unverified/agent zodat de sweep-judge of de mens 'm
                           later promoot (mens = update-autoriteit).
  - instructions (resource): de pull-nudge die een client zonder push-hook toch
                           naar recall stuurt. NB: GitHub Copilot ondersteunt
                           GEEN MCP-resources, alleen tools -> zet de nudge daar
                           in .github/copilot-instructions.md (zie README).

Soevereiniteitsgrens (HARD): local-only. stdio-transport, geen netwerk-bind. De
vault verlaat de machine nooit. Remote/gehoste agents (cloud-ChatGPT) kunnen een
lokale stdio-server per definitie niet bereiken; daarvoor is er de manuele
export-bridge (kb-ask.py), niet een tunnel. Zie README / TASK-22.

De waarde zit in recall_tool()/capture_tool() (puur, testbaar zonder mcp/model);
de MCP-transport is een dunne, optioneel-gegate schil. Vereist `pip install mcp`
om de server te DRAAIEN; ontbreekt het pakket, dan blijven de *_tool-functies
bruikbaar. Stdlib + optioneel mcp.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Optionele MCP-SDK (nieuwe naam MCPServer, oudere FastMCP). Afwezig -> None.
MCPServer = None
try:
    try:
        from mcp.server.mcpserver import MCPServer as MCPServer  # type: ignore
    except Exception:
        from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore
except Exception:
    MCPServer = None

# kb-recall via importlib (hyphen); module-globaal zodat tests het kunnen patchen.
kb_recall = None
try:
    _spec = importlib.util.spec_from_file_location(
        "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
    kb_recall = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(kb_recall)
except Exception:
    kb_recall = None


def recall_tool(query: str, k: int = 5) -> str:
    """Doorzoek de KennisBank (geheugen + wiki) en geef relevante kennis als tekst."""
    q = (query or "").strip()
    if not q:
        return ""
    try:
        import _embeddings as emb
        qvec = emb.embed(q)
        if not qvec or kb_recall is None:
            return "Geen treffers (model onbereikbaar of index ontbreekt)."
        hits = kb_recall.recall_hits(qvec, query_text=q, k=int(k),
                                     layers=("wiki", "memory"))
    except Exception:
        return "Geen treffers (fout bij ophalen)."
    if not hits:
        return "Geen treffers in de KennisBank."
    lines = []
    for h in hits:
        tag = "geheugen" if h.get("layer") == "memory" else "wiki"
        stem = Path(h.get("path", "")).stem
        title = h.get("title", "")
        lines.append(f"- [{tag}] [[{stem}|{title}]] ({h.get('score', 0.0):.2f}): "
                     f"{h.get('snippet', '')}")
    return "KennisBank-treffers:\n" + "\n".join(lines)


def capture_tool(title: str, body: str, memory_type: str = "feit",
                 importance: int = 3) -> str:
    """Leg een nieuwe memory vast in de KennisBank (PULL-write).

    Voor agents die geen KennisBank-hooks hebben (Codex, Cursor, ...) en toch
    kennis willen bijdragen. De memory landt bewust als status=unverified,
    evidence_basis=agent: de sweep-judge of de mens promoot 'm later naar
    current (mens = update-autoriteit). Geen write-time reconcile hier — dat
    doet de eerstvolgende sweep, die embeddings heeft. Fail-soft: bij een lege
    titel/body of schrijffout een nette melding, nooit een crash.
    """
    t = (title or "").strip()
    b = (body or "").strip()
    if not t or not b:
        return "Niets vastgelegd: titel en inhoud zijn beide vereist."
    try:
        import _memory
        mt = _memory.coerce_memory_type(memory_type) if hasattr(_memory, "coerce_memory_type") else memory_type
        path = _memory.write(
            t, b,
            status="unverified",
            evidence_basis="agent",
            memory_type=mt,
            importance=_memory.coerce_importance(importance) if hasattr(_memory, "coerce_importance") else importance,
        )
        return (f"Vastgelegd als unverified memory: {Path(path).name}. "
                f"De volgende sweep of jij bevestigt 'm (mens = autoriteit).")
    except Exception as e:
        return f"Kon de memory niet vastleggen ({type(e).__name__}). Niets geschreven."


# Pull-nudge voor MCP-clients zonder push-hook (zie module-docstring). Aangeboden
# als resource; clients die resources ondersteunen (Cursor, Claude Desktop) tonen
# 'm. Copilot ondersteunt geen resources -> README verwijst naar copilot-instructions.md.
INSTRUCTIONS_TEXT = (
    "Je hebt een lokale KennisBank (persoonlijk geheugen + gecureerde wiki) via de "
    "MCP-tools `recall` en `capture`.\n\n"
    "- Roep `recall` aan VOORDAT je extern zoekt of een aanname doet: je eigen "
    "eerdere lessen, beslissingen en bugfixes staan er mogelijk al in.\n"
    "- Roep `capture` aan wanneer er een herbruikbaar feit, voorkeur, procedure of "
    "beslissing ontstaat die je in een volgende sessie terug wilt zien.\n"
    "- De KennisBank is lokaal en soeverein: er gaat niets naar de cloud."
)


def build_server():
    """Bouw de MCP-server met recall + capture + instructions. None als mcp ontbreekt."""
    if MCPServer is None:
        return None
    srv = MCPServer("kennisbank-geheugen")

    @srv.tool()
    def recall(query: str, k: int = 5) -> str:
        """Doorzoek je eigen KennisBank (geheugen + wiki) op relevante kennis
        vóór je extern zoekt. Geef een korte query; krijg de beste treffers terug."""
        return recall_tool(query, k=k)

    @srv.tool()
    def capture(title: str, body: str, memory_type: str = "feit",
                importance: int = 3) -> str:
        """Leg een herbruikbaar feit/voorkeur/procedure/beslissing vast in je
        KennisBank. Landt als unverified; de sweep of jijzelf bevestigt 'm later."""
        return capture_tool(title, body, memory_type=memory_type, importance=importance)

    # Instructions-resource (best-effort: niet elke MCP-SDK-versie kent .resource()).
    try:
        @srv.resource("kennisbank://instructions")
        def instructions() -> str:
            """Hoe je de KennisBank-tools inzet (pull-nudge)."""
            return INSTRUCTIONS_TEXT
    except Exception:
        pass

    return srv


def main() -> int:
    srv = build_server()
    if srv is None:
        sys.stderr.write("kb-mcp: 'pip install mcp' nodig om de MCP-server te draaien.\n")
        return 0
    srv.run()  # stdio-transport (default)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

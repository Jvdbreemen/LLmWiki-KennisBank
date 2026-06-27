#!/usr/bin/env python3
"""kb-mcp.py - lokale stdio MCP-server over de KennisBank (memory + wiki).

Exposeert een `recall`-tool aan lokale MCP-clients (Cursor, LM Studio, Claude
Desktop). De waarde zit in recall_tool() (puur, testbaar zonder mcp/model); de
MCP-transport is een dunne, optioneel-gegate schil. Read-only over kb-index.db,
lokaal-only (stdio, geen netwerk-bind). Fail-soft.

Vereist `pip install mcp` om de server te DRAAIEN; ontbreekt het pakket, dan blijft
recall_tool bruikbaar (en raakt de afwezigheid niets anders). Stdlib + optioneel mcp.
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


def build_server():
    """Bouw de MCP-server met de recall-tool. None als het mcp-pakket ontbreekt."""
    if MCPServer is None:
        return None
    srv = MCPServer("kennisbank-geheugen")

    @srv.tool()
    def recall(query: str, k: int = 5) -> str:
        """Doorzoek je eigen KennisBank (geheugen + wiki) op relevante kennis
        vóór je extern zoekt. Geef een korte query; krijg de beste treffers terug."""
        return recall_tool(query, k=k)

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

# Agent-geheugen — Lokale MCP-server (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Een dunne lokale **stdio** MCP-server `kb-mcp.py` die de KennisBank (memory + wiki) als `recall`-tool blootlegt aan lokale MCP-clients (Cursor, LM Studio, Claude Desktop). De waarde zit in de testbare core (`recall_tool`); de MCP-transport is een dunne, optioneel-gegate schil.

**Architecture:** `recall_tool(query, k)` is een pure functie (embed query → `kb_recall.recall_hits` over beide lagen → tekst) die **zonder** het `mcp`-pakket unit-getest wordt. De MCP-server-wrapper importeert `mcp` **achter try/except**: ontbreekt het pakket, dan kan de server niet draaien maar raakt het **niets** anders (hook-recall, tests, no-cloud blijven heel). Read-only over `kb-index.db`. Lokaal-only (stdio, geen netwerk).

**Tech Stack:** Python 3.10+ (stdlib), `kb-recall`/`_embeddings`, optioneel `mcp` (pip, niet vereist voor de tests), `unittest`.

## Global Constraints

- **`mcp`-import gegate:** achter try/except. Afwezig → `recall_tool` werkt nog (testbaar), alleen de server start niet (nette stderr-melding, exit 0). De afwezigheid mag de hook-recall, de no-cloud-test of welke andere test dan ook **nooit** raken.
- **Lokaal-only (#4):** stdio-transport, geen netwerk-bind. De enige netwerk-call is de lokale Ollama-embed (via `_embeddings`), fail-soft.
- **Read-only:** hergebruikt `kb_recall.recall_hits` dat de index read-only opent (de sweep is een concurrent writer).
- **Fail-soft:** geen query / geen hits / model onbereikbaar / geen index → nette lege/duidelijke tekst, nooit een exceptie naar de MCP-client.
- **Testbaar zonder mcp + zonder model:** `recall_tool`-tests monkeypatchen `emb.embed` + `kb_recall.recall_hits`. De server-bouw-test asserteert alleen dat `build_server()` `None` geeft als `mcp` ontbreekt (huidige omgeving) — geen transport-test.
- **Decoupling:** `kb-recall.py`, `kb-retrieve.py`, `_embeddings.py`, `_kbindex.py` ongemoeid. Nieuw bestand `kb-mcp.py`.

---

### Task 1: `kb-mcp.py` — recall-tool core + gegate server

**Files:**
- Create: `scripts/kb-mcp.py`
- Test: `tests/test_kb_mcp.py`

**Interfaces:**
- Produces:
  - `recall_tool(query: str, k: int = 5) -> str` — embed query → `kb_recall.recall_hits(qvec, query_text=query, k=k, layers=("wiki","memory"))` → mens-leesbare tekst (één regel per hit met laag-tag + `[[stem|title]]` + snippet). Lege query/geen hits/fout → een korte "geen treffers"/"" tekst. Nooit raise.
  - `build_server()` — bouwt de MCP-server met de `recall`-tool; `None` als `mcp` ontbreekt.
  - `main()` — `build_server().run()` of een nette stderr-melding als `mcp` ontbreekt (exit 0).
  - module-globaal `kb_recall` (importlib-geladen, patchbaar in tests) en `MCPServer` (of None).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_kb_mcp.py`:

```python
"""Tests voor scripts/kb-mcp.py - recall-tool core (zonder mcp-pakket/model)."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("kb_mcp", str(SCRIPTS_DIR / "kb-mcp.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class KbMcpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-mcp-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.m = _load()
        if getattr(self.m, "kb_recall", None) is None:
            self.skipTest("kb_recall niet beschikbaar (sqlite_vec ontbreekt?)")
        import _embeddings as emb
        self._orig_embed = emb.embed
        emb.embed = lambda text, timeout=30.0: [0.1, 0.2, 0.3]
        self.emb = emb
        self._orig_recall = self.m.kb_recall.recall_hits
        self.m.kb_recall.recall_hits = lambda *a, **k: [
            {"path": "/v/09-memory/x.md", "layer": "memory", "title": "Oude bug",
             "created": "2026-06-01", "score": 0.9, "snippet": "token expiry < ipv <="}]

    def tearDown(self):
        import shutil
        self.emb.embed = self._orig_embed
        self.m.kb_recall.recall_hits = self._orig_recall
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recall_tool_formats_hits(self):
        out = self.m.recall_tool("token expiry bug")
        self.assertIn("Oude bug", out)
        self.assertIn("geheugen", out)

    def test_recall_tool_empty_query(self):
        self.assertEqual(self.m.recall_tool("").strip(), "")

    def test_recall_tool_no_hits(self):
        self.m.kb_recall.recall_hits = lambda *a, **k: []
        out = self.m.recall_tool("iets")
        self.assertIn("geen", out.lower())

    def test_recall_tool_embed_fail_is_soft(self):
        self.emb.embed = lambda *a, **k: None
        self.assertIn("geen", self.m.recall_tool("iets").lower())

    def test_build_server_none_without_mcp(self):
        # in deze omgeving is mcp niet geinstalleerd -> build_server geeft None
        if self.m.MCPServer is None:
            self.assertIsNone(self.m.build_server())
        else:
            self.assertIsNotNone(self.m.build_server())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_kb_mcp.py -v`
Expected: FAIL — `kb-mcp.py` bestaat niet.

- [ ] **Step 3: Implement `scripts/kb-mcp.py`**

Create `scripts/kb-mcp.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_kb_mcp.py -v`
Expected: PASS (5 tests; `build_server` geeft None want `mcp` is niet geïnstalleerd in deze omgeving).

- [ ] **Step 5: Run the full suite (no regressions, no-cloud-guard intact)**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS — bevestig dat de no-cloud-guard en de overige tests niet geraakt zijn door het nieuwe bestand.

- [ ] **Step 6: Commit**

```bash
git add scripts/kb-mcp.py tests/test_kb_mcp.py
git commit -m "feat(memory): kb-mcp lokale stdio MCP-server (recall-tool, mcp optioneel/gegate)"
```

---

### Task 2: documentatie + optionele dep

**Files:**
- Modify: `CONFIGURATION.md`, `CHANGELOG.md`

**Interfaces:**
- Produces: documentatie om de MCP-server te registreren bij een lokale MCP-client + de optionele `mcp`-dep.

- [ ] **Step 1: Document the MCP-server in `CONFIGURATION.md`**

Voeg een sectie toe (mirror de stijl van de bestaande secties):

```markdown
### Lokale MCP-server (kb-mcp.py, optioneel)

`kb-mcp.py` exposeert je KennisBank (geheugen + wiki) als `recall`-tool aan lokale
MCP-clients (Cursor, LM Studio, Claude Desktop) via **stdio** — lokaal, geen netwerk.
Vereist eenmalig `pip install mcp`. Registreer bij je MCP-client met commando:

​```
python3 "$HOME/KennisBank/.claude/scripts/kb-mcp.py"
​```

(Windows: `py -3 "%USERPROFILE%/KennisBank/.claude/scripts/kb-mcp.py"`.)
De server opent `kb-index.db` read-only; embedt query's lokaal via Ollama. Zonder
het `mcp`-pakket meldt het script netjes dat de dep ontbreekt — de rest van
KennisBank (hook-recall, sweep) werkt onafhankelijk door.
```

- [ ] **Step 2: Update `CHANGELOG.md`**

Eén regel: lokale stdio MCP-server (`kb-mcp.py`) met een `recall`-tool over geheugen + wiki (optionele `mcp`-dep).

- [ ] **Step 3: Run the full suite (sanity)**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 4: Commit**

```bash
git add CONFIGURATION.md CHANGELOG.md
git commit -m "docs(memory): registreer kb-mcp lokale MCP-server (optionele mcp-dep)"
```

---

## Self-Review

**Spec coverage (MCP):**
- Lokale stdio MCP-server met `recall`-tool over beide lagen → Task 1. ✓
- `mcp`-import gegate; afwezig raakt niets → Task 1 (`MCPServer = None`, `build_server() -> None`). ✓
- Read-only + fail-soft + lokaal-only → Task 1 (`recall_tool` via `recall_hits`). ✓
- Testbaar zonder mcp + zonder model → `recall_tool`-tests monkeypatchen emb+recall_hits; server-test asserteert None. ✓
- Registratie-docs + optionele dep → Task 2. ✓

**Placeholder scan:** geen TBD/TODO; alle code + testcode volledig.

**Type consistency:** `recall_tool(query, k) -> str`; `build_server() -> server|None`; `kb_recall.recall_hits(...)` matcht fase A; `MCPServer`/`kb_recall` module-globalen patchbaar.

**Geverifieerd vóór uitvoering:** MCP-SDK-API bevestigd (Context7): `MCPServer`/`FastMCP` + `@srv.tool()` + `srv.run()` (stdio default). `mcp` is NIET geïnstalleerd in deze omgeving → `build_server()` geeft `None`, en de tests dekken precies dat pad (de transport zelf is bewust ongetest — de advisor: "unit-test de lib, smoke-test de wrapper; de protocol-laag is niet waar de waarde zit"). `recall_hits` (fase A) bestaat en geeft beide lagen.

**Aandachtspunt uitvoerder:** de `recall_tool`-tests patchen `m.kb_recall.recall_hits`; `recall_tool` moet het module-globale `kb_recall` lezen (geen lokale her-import), anders ziet de patch niets — idem het patroon uit `kb-presearch.py`. Bevestig dat de no-cloud-guard-test groen blijft (het nieuwe bestand bevat geen externe hosts; de optionele cloud zit in `_llm`, niet hier).

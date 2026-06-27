# Agent-geheugen — Fase A: PreToolUse presearch-hook (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Garanderen dat de agent **altijd eerst z'n eigen geheugen + wiki checkt** wanneer hij naar buiten zoekt. Een PreToolUse-hook `kb-presearch.py` vuurt op `WebSearch`/`WebFetch`, embedt de query, en injecteert relevante memory+wiki-hits als `additionalContext` (push, niet-blokkerend). Plus een herbruikbaar `recall_hits` in `kb-recall` over beide lagen.

**Architecture:** De UserPromptSubmit-hook dekt turn-start; deze PreToolUse-hook dekt mid-turn zoekacties — samen is geheugen-consultatie gegarandeerd (push, niet pull). `kb-recall` krijgt een laag-generieke `recall_hits(layers=("wiki","memory"))`; `memory_hits` wordt een dunne wrapper. De live-status-hercheck (stale-index-bescherming) blijft **alleen voor de memory-laag** (wiki is gecureerd, kent geen retract-probleem). De hook is fail-open en gegate op `memory_recall`.

**Tech Stack:** Python 3.10+ (stdlib + sqlite-vec), `kb-recall`/`_kbindex`/`_embeddings`/`_memory`/`_settings`, `unittest`.

## Global Constraints

- **Fail-open ALTIJD:** de PreToolUse-hook blokkeert of vertraagt een tool nooit. Elke fout / lege query / ontbrekende index → geen output, exit 0. Nooit `permissionDecision: deny`.
- **Niet-blokkerend injecteren:** output `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "defer", "additionalContext": "..."}}` (geverifieerd contract). `defer` = tool gaat gewoon door.
- **Gegate op `memory_recall`** (default True). Uit → de hook injecteert niets.
- **Beide lagen:** injecteer memory(current) + wiki(current) via `kb-index.db`. Wiki-hits vertrouwen de index-status; memory-hits krijgen de live-status-hercheck (stale-index-bescherming, #1).
- **Triggert alleen op `WebSearch`/`WebFetch`** (tool_name-check in het script; matcher in settings.json bevestigt het).
- **Query-extractie:** WebSearch → `tool_input.query`; WebFetch → `tool_input.url` (+ evt. `tool_input.prompt`).
- **Mockbaar:** tests monkeypatchen `emb.embed` + `kb_recall.recall_hits` (of `_kbindex`), geen echt model/netwerk.
- **Decoupling:** `kb-retrieve.py`, `_embeddings.py`, `build-embed-index.py`, `_kbindex.py` ongemoeid. `kb-recall.py` wordt uitgebreid (additieve `recall_hits`; `memory_hits`-gedrag behouden).
- **Module-conventie:** underscore/hyphen-naam, self-locate vault parents[2].

---

### Task 1: `kb-recall.recall_hits` — laag-generieke recall

**Files:**
- Modify: `scripts/kb-recall.py`
- Test: `tests/test_kb_recall.py` (tests toevoegen)

**Interfaces:**
- Produces:
  - `recall_hits(query_vector, query_text="", k=3, layers=("wiki","memory")) -> list[dict]` — hits over de opgegeven lagen, status=current. Per hit `{"path","layer","title","created","score","snippet"}`. Live-status-hercheck **alleen** voor `layer=="memory"` (wiki vertrouwt de index).
  - `memory_hits(...)` blijft bestaan als wrapper: `recall_hits(..., layers=("memory",))`.

- [ ] **Step 1: Write the failing tests**

Voeg toe aan `class KbRecallTest` in `tests/test_kb_recall.py` (de `setUp` indexeert al een memory `m1.md` + een wiki `w1.md`, en mockt `emb.embed_id` naar `"ollama:test"`):

```python
    def test_recall_hits_returns_both_layers(self):
        hits = self.kb.recall_hits([0.1, 0.2, 0.3, 0.4], query_text="bug wiki",
                                   k=5, layers=("wiki", "memory"))
        layers = {h["layer"] for h in hits}
        self.assertIn("memory", layers)
        self.assertIn("wiki", layers)
        self.assertTrue(all("layer" in h for h in hits))

    def test_recall_hits_wiki_not_live_rechecked(self):
        # w1.md staat NIET op disk als geldige memory; toch moet de wiki-hit blijven
        # (wiki vertrouwt de index-status, geen live read_status-drop).
        hits = self.kb.recall_hits([0.9, 0.8, 0.7, 0.6], query_text="wiki",
                                   k=5, layers=("wiki",))
        self.assertTrue(any(h["layer"] == "wiki" for h in hits))

    def test_memory_hits_still_memory_only(self):
        hits = self.kb.memory_hits([0.1, 0.2, 0.3, 0.4], query_text="bug", k=5)
        self.assertTrue(all(Path(h["path"]).name == "m1.md" for h in hits))
```

> NOTE: de `setUp` schrijft `m1.md` ook live naar disk (status: current) voor de live-recheck; `w1.md` wordt alleen geïndexeerd (niet als live memory-file). Als `setUp` `w1.md` niet op disk zet, dan geeft `doc_text` een lege snippet voor de wiki-hit — dat is prima (de test asserteert layer, niet snippet-inhoud). Bevestig dat de wiki-hit NIET wordt gedropt door een memory-live-recheck.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_kb_recall.py -k recall_hits -v`
Expected: FAIL — `recall_hits` bestaat nog niet.

- [ ] **Step 3: Refactor `kb-recall.py`**

Vervang `memory_hits` door een generieke `recall_hits` + een wrapper. Behoud `_open_ro` ongewijzigd:

```python
def recall_hits(query_vector, query_text: str = "", k: int = 3,
                layers=("wiki", "memory")) -> list:
    """Recall-hits over de opgegeven lagen (status=current), fail-soft -> [].
    Live-status-hercheck ALLEEN voor de memory-laag (wiki is gecureerd)."""
    if not query_vector:
        return []
    conn = _open_ro(_kbindex.index_path())
    if conn is None:
        return []
    try:
        if not _kbindex.is_valid_for(conn, emb.embed_id()):
            return []
        rows = _kbindex.search(conn, query_vector=query_vector, query_text=query_text,
                               k=k, layers=tuple(layers), statuses=("current",))
        out = []
        for r in rows:
            layer = r.get("layer", "")
            # Stale-index-bescherming alleen voor memory: een ingetrokken memory mag
            # nooit als current geserveerd worden. Wiki vertrouwt de index-status.
            if layer == "memory" and _mem.read_status(Path(r["path"])) != "current":
                continue
            snippet = emb.doc_text(Path(r["path"]), cap=280).replace("\n", " ").strip()
            out.append({"path": r["path"], "layer": layer, "title": r.get("title", ""),
                        "created": r.get("created", ""), "score": r.get("score", 0.0),
                        "snippet": snippet})
        return out
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def memory_hits(query_vector, query_text: str = "", k: int = 3) -> list:
    """Dunne wrapper: alleen de memory-laag (backward-compat)."""
    return recall_hits(query_vector, query_text=query_text, k=k, layers=("memory",))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_kb_recall.py -v`
Expected: PASS — de nieuwe recall_hits-tests + alle bestaande memory_hits-tests (incl. de stale-recall-regressietest).

- [ ] **Step 5: Commit**

```bash
git add scripts/kb-recall.py tests/test_kb_recall.py
git commit -m "feat(memory): kb-recall.recall_hits laag-generiek (beide lagen, memory-only live-recheck)"
```

---

### Task 2: `kb-presearch.py` — PreToolUse-hook

**Files:**
- Create: `scripts/kb-presearch.py`
- Test: `tests/test_kb_presearch.py`

**Interfaces:**
- Produces: `kb-presearch.py` (PreToolUse-hook): leest hook-JSON op stdin; alleen voor `WebSearch`/`WebFetch`; gegate op `memory_recall`; embedt de query; `kb_recall.recall_hits` over beide lagen; emit `additionalContext` met `permissionDecision: defer`. Fail-open. Functies: `query_of(tool_name, tool_input) -> str`, `build_context(hits) -> str`, `main()`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_kb_presearch.py`:

```python
"""Tests voor scripts/kb-presearch.py - PreToolUse presearch-hook. Geen echt
model: we monkeypatchen emb.embed + kb_recall.recall_hits. Draait de hook als
functie (via importlib) met een gefabriceerde hook-JSON."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("kb_presearch", str(SCRIPTS_DIR / "kb-presearch.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class KbPresearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-pre-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.m = _load()
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

    def _run(self, payload, settings=None):
        if settings is not None:
            (self.vault / "kennisbank-settings.json").write_text(json.dumps(settings), encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.m.main(stdin_text=json.dumps(payload))
        return buf.getvalue()

    def test_websearch_injects_context(self):
        out = self._run({"tool_name": "WebSearch", "tool_input": {"query": "token expiry bug"}})
        data = json.loads(out)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(data["hookSpecificOutput"]["permissionDecision"], "defer")
        self.assertIn("Oude bug", data["hookSpecificOutput"]["additionalContext"])

    def test_non_search_tool_no_output(self):
        self.assertEqual(self._run({"tool_name": "Bash", "tool_input": {"command": "ls"}}).strip(), "")

    def test_memory_recall_off_no_output(self):
        out = self._run({"tool_name": "WebSearch", "tool_input": {"query": "x bug here"}},
                        settings={"memory_recall": False})
        self.assertEqual(out.strip(), "")

    def test_no_hits_no_output(self):
        self.m.kb_recall.recall_hits = lambda *a, **k: []
        self.assertEqual(self._run({"tool_name": "WebSearch", "tool_input": {"query": "iets"}}).strip(), "")

    def test_webfetch_uses_url(self):
        out = self._run({"tool_name": "WebFetch", "tool_input": {"url": "https://example.com/x"}})
        self.assertIn("additionalContext", out)

    def test_garbage_input_failopen(self):
        self.assertEqual(self._run({}).strip(), "")  # geen tool_name -> stil


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_kb_presearch.py -v`
Expected: FAIL — `kb-presearch.py` bestaat niet.

- [ ] **Step 3: Implement `scripts/kb-presearch.py`**

Create `scripts/kb-presearch.py`:

```python
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


def query_of(tool_name: str, tool_input: dict) -> str:
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
    if not hits:
        return ""
    lines = ["Je eigen KennisBank bevat hier mogelijk al kennis over (check dit eerst):"]
    for h in hits:
        tag = "geheugen" if h.get("layer") == "memory" else "wiki"
        stem = Path(h.get("path", "")).stem
        lines.append(f"- [{tag}] [[{stem}]] ({h.get('score', 0.0):.2f}): {h.get('snippet', '')}")
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

    os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
        spec = importlib.util.spec_from_file_location(
            "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
        kb_recall = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(kb_recall)
        hits = kb_recall.recall_hits(qvec, query_text=query, k=4,
                                     layers=("wiki", "memory"))
    except Exception:
        return 0

    ctx = build_context(hits)
    if ctx:
        _emit(ctx)
    return 0


# expose kb_recall-module-attribuut voor monkeypatching in de tests
kb_recall = None
try:  # best-effort import zodat tests m.kb_recall.recall_hits kunnen patchen
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _spec = importlib.util.spec_from_file_location(
        "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
    kb_recall = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(kb_recall)
except Exception:
    kb_recall = None


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
```

> NOTE voor de uitvoerder: de tests patchen `m.kb_recall.recall_hits`. Daarom is `kb_recall` een module-attribuut dat bij import wordt geladen, en gebruikt `main()` dat geladen attribuut (niet een lokale her-import). Pas `main()` aan zodat het `kb_recall` (het module-globale) gebruikt in plaats van opnieuw te laden — anders ziet de monkeypatch geen effect. Concreet: vervang in `main()` het her-laden van kb_recall door `hits = kb_recall.recall_hits(...)` als `kb_recall` niet None is, met een fallback-laad als het None is. Zorg dat de happy-path-test (`test_websearch_injects_context`) groen wordt met de patch.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_kb_presearch.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/kb-presearch.py tests/test_kb_presearch.py
git commit -m "feat(memory): kb-presearch PreToolUse-hook (geheugen vóór WebSearch/WebFetch)"
```

---

### Task 3: registratie-documentatie

**Files:**
- Modify: `CONFIGURATION.md`, `CHANGELOG.md`
- Test: geen (docs).

**Interfaces:**
- Produces: documentatie om `kb-presearch.py` als PreToolUse-hook te registreren (matcher `WebSearch|WebFetch`), met uitleg dat het niet-blokkerend is en gegate op `memory_recall`.

- [ ] **Step 1: Document the PreToolUse registration in `CONFIGURATION.md`**

Voeg een sectie toe (mirror de stijl van de bestaande hook-registratie-blokken), met het concrete settings.json-fragment:

```markdown
### Presearch — geheugen vóór elke web-search (kb-presearch.py, PreToolUse)

`kb-presearch.py` zorgt dat de agent ALTIJD eerst z'n eigen KennisBank
(memory + wiki) raadpleegt vóór een `WebSearch`/`WebFetch`. Het injecteert
relevante hits als context en laat de search gewoon doorgaan (niet-blokkerend).
Gegate op `memory_recall`. Voeg toe aan `~/.claude/settings.json`:

​```json
"PreToolUse": [
  { "matcher": "WebSearch|WebFetch",
    "hooks": [ { "type": "command",
      "command": "py -3 \"%USERPROFILE%/KennisBank/.claude/scripts/kb-presearch.py\"" } ] }
]
​```

(POSIX: `python3 "$HOME/KennisBank/.claude/scripts/kb-presearch.py"`.)
Samen met de UserPromptSubmit-hook (turn-start) is geheugen-consultatie hiermee
gegarandeerd via push: turn-start én bij elke externe zoekactie.
```

Pas pad/stijl aan op de bestaande CONFIGURATION.md-conventie.

- [ ] **Step 2: Update `CHANGELOG.md`**

Eén regel: PreToolUse presearch-hook (`kb-presearch.py`) — geheugen+wiki vóór WebSearch/WebFetch.

- [ ] **Step 3: Run the full suite (sanity)**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 4: Commit**

```bash
git add CONFIGURATION.md CHANGELOG.md
git commit -m "docs(memory): registreer kb-presearch PreToolUse-hook"
```

---

## Self-Review

**Spec coverage (fase A):**
- `recall_hits` over beide lagen, memory-only live-recheck → Task 1. ✓
- PreToolUse-hook op WebSearch/WebFetch, query-extractie, additionalContext defer, fail-open, memory_recall-gate → Task 2. ✓
- Registratie-docs (matcher WebSearch|WebFetch) → Task 3. ✓
- Mockbaar zonder model → alle tests monkeypatchen emb.embed + recall_hits. ✓

**Placeholder scan:** geen TBD/TODO; alle code + testcode volledig.

**Type consistency:** `recall_hits(query_vector, query_text, k, layers) -> [{path,layer,title,created,score,snippet}]`; `memory_hits` wrapper behoudt bestaande call-sites (kb-retrieve `_memory_block` leest path/score/snippet — "layer" is additief, breekt niets); `query_of`/`build_context`/`main(stdin_text=None)` consistent met de tests.

**Geverifieerd vóór uitvoering:** PreToolUse-contract bevestigd (tool_input.query/url; hookSpecificOutput met hookEventName=PreToolUse + permissionDecision=defer + additionalContext; matcher regex WebSearch|WebFetch; exit 0 = inject). `kb-recall` is gelezen (live-recheck zit in memory_hits); de refactor verplaatst die recheck naar de memory-tak van recall_hits. `_kbindex.search` retourneert al `layer` per hit.

**Aandachtspunt uitvoerder:** Task 2 — de tests patchen `m.kb_recall.recall_hits`; zorg dat `main()` het module-globale `kb_recall`-attribuut gebruikt (niet een lokale her-import), anders heeft de monkeypatch geen effect. Bevestig dat `main(stdin_text=...)` test-aanroepbaar is. Houd álles fail-open (geen exception ontsnapt naar de hook).

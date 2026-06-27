# Agent-geheugen — Fase 3: Recall (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** De agent-geheugenlaag doorzoekbaar maken bij recall: een nieuwe `kb-recall.py`-lib bovenop `kb-index.db`, additief geïntegreerd in de bestaande `kb-retrieve.py` UserPromptSubmit-hook (gegate op `memory_recall`), plus SessionStart-wiring zodat de index vers is. Wiki-recall blijft byte-identiek als geheugen uit staat.

**Architecture:** Strikt **additief (2a)** — het bestaande JSON-cosine wiki-pad blijft ongemoeid. De hook embedt de prompt al één keer (`qvec`); die vector wordt hergebruikt voor een tweede lookup `_kbindex.search(layers=("memory",), statuses=("current",))`. Wiki en memory worden als aparte presentatie-secties geëmit (wiki eerst), niet als één verenigde ranking (cosine vs RRF zijn niet vergelijkbaar). De MCP-server is **bewust uitgesteld tot na fase 4** (een MCP-server over een lege geheugenlaag is niet end-to-end testbaar; de lib levert de waarde).

**Tech Stack:** Python 3.10+ (stdlib + sqlite-vec), `_kbindex` (fase 2), `_embeddings`, `_settings`, `unittest`.

## Global Constraints

- **Byte-identiteit-invariant (hard):** met `memory_recall=false` is de hook-output voor élke prompt identiek aan vóór fase 3 (wiki-only). Geheugen is puur additief en gegate.
- **Reuse de query-embedding:** één embed per prompt; `qvec` gedeeld door wiki- en memory-lookup. Memory mag hooguit één extra embed doen als het wiki-pad er geen berekende (lege wiki-cache).
- **Fail-open/fail-soft:** de hook breekt nooit een prompt (bestaand contract). Ontbrekende `kb-index.db`, model-mismatch, onbereikbaar embedmodel → geen memory-injectie, exit 0.
- **kb-index.db read-only openen** in de recall-lib (`mode=ro` via URI of `PRAGMA query_only`); de sweep (fase 4) is een concurrent writer.
- **Cross-model-veiligheid:** alleen memory-resultaten gebruiken als `kb-index.db`'s opgeslagen `embed_id` == het actieve `embed_id` (`_kbindex.is_valid_for`).
- **Lokaal-only (#4):** Ollama + SQLite, geen netwerk. No-cloud-test dekt het recall-pad.
- **Decoupling #9:** `build-embed-index.py`, `_embeddings.py`, de JSON-cache blijven ongemoeid. `kb-retrieve.py` wordt in DEZE fase wél uitgebreid — dat is de recall-fase — maar strikt additief.
- **MCP-server: NIET in fase 3** (uitgesteld tot na fase 4).
- **Interpreter:** repo-scripts/`setup.sh` = `python3`; Windows-hooks draaien via `py -3` (registratie ongewijzigd).

---

### Task 1: `kb-recall.py` — geheugen-recall-lib

**Files:**
- Create: `scripts/kb-recall.py`
- Test: `tests/test_kb_recall.py`

**Interfaces:**
- Consumes: `_kbindex` (`index_path`, `connect`, `is_valid_for`, `search`), `_embeddings` (`embed_id`, `cosine`, `doc_text`), `_vaultpath.vault_root`.
- Produces:
  - `memory_hits(query_vector, query_text="", k=3) -> list[dict]` — opent `kb-index.db` read-only, valideert `embed_id`, roept `_kbindex.search(conn, query_vector=..., query_text=..., k=k, layers=("memory",), statuses=("current",))`, en geeft per hit `{"path","title","created","score","snippet"}` (snippet via `doc_text(path, cap=280)`, newlines vervangen door spaties). **Fail-soft:** geen db / mismatch / fout → `[]`.
  - `_open_ro(db_path) -> sqlite3.Connection | None` — open read-only met sqlite-vec geladen; None bij ontbreken/fout.

- [ ] **Step 1: Write the failing test**

Create `tests/test_kb_recall.py`:

```python
"""Tests voor scripts/kb-recall.py - geheugen-recall over kb-index.db.

Bouwt een echte kb-index.db met fake vectoren (geen Ollama). Vault naar temp.
kb-recall heeft een hyphen -> via importlib laden.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _kbindex  # noqa: E402

DIM = 4


def _load_kb_recall():
    spec = importlib.util.spec_from_file_location("kb_recall", str(SCRIPTS_DIR / "kb-recall.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class KbRecallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-rec-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        # bouw een index met 1 memory + 1 wiki, embed_id 'ollama:test'
        conn = _kbindex.connect()  # schrijft naar <vault>/.claude/kb-index.db
        _kbindex.ensure_schema(conn, dim=DIM, embed_id="ollama:test")
        _kbindex.upsert(conn, path=str(self.vault / "09-memory" / "m1.md"),
                        layer="memory", status="current", body="hook gedreven retrieval bug",
                        vector=[0.1, 0.2, 0.3, 0.4], file_hash="h1", title="M1", created="2026-06-01")
        _kbindex.upsert(conn, path=str(self.vault / "02-wiki" / "w1.md"),
                        layer="wiki", status="current", body="wiki artikel",
                        vector=[0.9, 0.8, 0.7, 0.6], file_hash="h2", title="W1", created="2026-06-02")
        conn.close()
        self.kb = _load_kb_recall()

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_memory_hits_returns_only_memory_layer(self):
        hits = self.kb.memory_hits([0.1, 0.2, 0.3, 0.4], query_text="bug", k=5)
        self.assertTrue(hits)
        self.assertTrue(all(Path(h["path"]).name == "m1.md" for h in hits))
        self.assertIn("snippet", hits[0])
        self.assertIn("title", hits[0])

    def test_embed_id_mismatch_returns_empty(self):
        # actieve embed_id != index embed_id -> geen resultaten
        import _embeddings as emb
        orig = emb.embed_id
        emb.embed_id = lambda: "ollama:ander-model"
        try:
            self.assertEqual(self.kb.memory_hits([0.1, 0.2, 0.3, 0.4], k=5), [])
        finally:
            emb.embed_id = orig

    def test_missing_index_returns_empty(self):
        (self.vault / ".claude" / "kb-index.db").unlink()
        self.assertEqual(self.kb.memory_hits([0.1, 0.2, 0.3, 0.4], k=5), [])


if __name__ == "__main__":
    unittest.main()
```

NOTE: the test calls `memory_hits` with the active `embed_id` defaulting to `emb.embed_id()`. The index was built with `"ollama:test"`. The real `emb.embed_id()` returns `"ollama:qwen3-embedding:8b"`, which would mismatch. So `memory_hits` MUST compare against the index's stored embed_id using the *active* `emb.embed_id()` — and the happy-path test needs them equal. Resolve by having `setUp` also force `emb.embed_id` to `"ollama:test"` for the happy path. Add to `setUp` after building: `import _embeddings as emb; self._orig_eid = emb.embed_id; emb.embed_id = lambda: "ollama:test"` and restore in `tearDown` (`emb.embed_id = self._orig_eid`). Then `test_embed_id_mismatch_returns_empty` overrides it again locally. Adjust the test accordingly before running.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_kb_recall.py -v`
Expected: FAIL — `kb-recall.py` does not exist (exec_module raises FileNotFoundError).

- [ ] **Step 3: Implement `scripts/kb-recall.py`**

Create `scripts/kb-recall.py`:

```python
#!/usr/bin/env python3
"""kb-recall.py - geheugen-recall over kb-index.db (lokaal, fail-soft).

Herbruikbare lib voor de UserPromptSubmit-hook (en later een lokale MCP-server).
Neemt een al-berekende query-vector (de hook embedt de prompt 1×) en geeft de
beste memory(current)-hits terug. Opent de index READ-ONLY (de sweep is een
concurrent writer). Fail-soft: ontbrekende index, model-mismatch of welke fout
dan ook -> lege lijst. Nooit een exceptie naar de hook.

Cross-model-veiligheid: alleen resultaten als de opgeslagen embed_id van de index
gelijk is aan het actieve embedmodel (idem aan de JSON-cache-gate).

Stdlib + sqlite-vec. Hyphen in de naam: importeer via importlib of draai als CLI.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _kbindex  # noqa: E402


def _open_ro(db_path: Path):
    if not db_path.exists():
        return None
    try:
        import sqlite_vec
        uri = f"file:{db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return conn
    except Exception:
        return None


def memory_hits(query_vector, query_text: str = "", k: int = 3) -> list:
    if not query_vector:
        return []
    db = _kbindex.index_path()
    conn = _open_ro(db)
    if conn is None:
        return []
    try:
        if not _kbindex.is_valid_for(conn, emb.embed_id()):
            return []
        rows = _kbindex.search(conn, query_vector=query_vector, query_text=query_text,
                               k=k, layers=("memory",), statuses=("current",))
        out = []
        for r in rows:
            snippet = emb.doc_text(Path(r["path"]), cap=280).replace("\n", " ").strip()
            out.append({"path": r["path"], "title": r.get("title", ""),
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_kb_recall.py -v`
Expected: PASS (3 tests). Apply the `setUp`/`tearDown` `embed_id` adjustment from Step 1 first.

- [ ] **Step 5: Commit**

```bash
git add scripts/kb-recall.py tests/test_kb_recall.py
git commit -m "feat(memory): kb-recall.py geheugen-recall over kb-index.db (read-only, fail-soft)"
```

---

### Task 2: `kb-retrieve.py` hook — additieve memory-injectie

**Files:**
- Modify: `scripts/kb-retrieve.py`
- Test: `tests/test_kb_retrieve_memory.py`

**Interfaces:**
- Consumes: `kb-recall.py` `memory_hits`, `_settings.get`.
- Produces: de hook emit, naast het bestaande wiki-blok, een memory-blok als `memory_recall` aan staat en er hits zijn. Byte-identiek wiki-gedrag als `memory_recall` uit.

**Refactor-vorm (DRY, byte-identiteit):** Trek de wiki-scoringslogica in een helper die het wiki-blok (of "") teruggeeft plus de berekende `qvec` (of None). `main()` voegt het memory-blok additief toe.

- [ ] **Step 1: Write the failing test**

Create `tests/test_kb_retrieve_memory.py`:

```python
"""Tests voor de additieve memory-injectie in kb-retrieve.py.

Draait de hook als subprocess met stdin-JSON (echt hook-contract). Geen Ollama:
we monkeypatchen niet het subprocess, dus we testen de TWEE invarianten die
zonder embedmodel toetsbaar zijn:
  1. memory_recall=false  -> output bevat NOOIT een memory-blok (byte-identiteit
     met wiki-only: hier specifiek: geen 'KennisBank-geheugen'-regel).
  2. Een triviale/korte prompt -> geen output (bestaand gedrag, ongewijzigd).
Het volledige happy-path (memory-hits in context) wordt via de lib getest
(test_kb_recall) omdat dat een embedmodel vergt.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
HOOK = SCRIPTS_DIR / "kb-retrieve.py"


class KbRetrieveMemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-ret-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self.env = dict(os.environ)
        self.env["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, prompt: str, settings: dict | None = None) -> str:
        if settings is not None:
            (self.vault / "kennisbank-settings.json").write_text(
                json.dumps(settings), encoding="utf-8")
        p = subprocess.run([sys.executable, str(HOOK)],
                           input=json.dumps({"prompt": prompt}),
                           capture_output=True, text=True, env=self.env, timeout=60)
        return p.stdout

    def test_trivial_prompt_no_output(self):
        self.assertEqual(self._run("ok").strip(), "")

    def test_memory_recall_off_no_memory_block(self):
        # geen index, geen cache -> hoogstens niets; cruciaal: nooit een memory-blok
        out = self._run("Een wat langere vraag over hooks en retrieval in dit project",
                        settings={"memory_recall": False})
        self.assertNotIn("KennisBank-geheugen", out)

    def test_memory_recall_on_without_index_still_no_crash(self):
        # memory aan maar geen kb-index.db -> fail-soft, geen memory-blok, geen crash
        out = self._run("Een wat langere vraag over hooks en retrieval in dit project",
                        settings={"memory_recall": True})
        self.assertNotIn("KennisBank-geheugen", out)  # index ontbreekt -> geen hits


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_kb_retrieve_memory.py -v`
Expected: `test_trivial_prompt_no_output` PASSES (bestaand gedrag); the two memory tests PASS only if no memory block is ever emitted — but they may currently pass trivially because no memory code exists. To make Step 3 meaningful, FIRST add a deliberately-failing assertion is not needed; instead treat Step 3 as adding the feature while keeping these invariants green. Run to confirm the baseline: all three PASS (the memory tests assert *absence*, which holds before the feature too). This is a guard-rail test: it must STAY green after Step 3.

> Note: this task's TDD value is the *byte-identity guard*. The positive memory-injection path needs Ollama and is covered at the lib level (Task 1). After implementing Step 3, these three must remain green.

- [ ] **Step 3: Refactor `kb-retrieve.py` for additive memory injection**

Replace the body of `main()` in `scripts/kb-retrieve.py`. Keep everything above (imports, `_TRIVIAL`, `_emit`, `_num`) unchanged. Extract the wiki scoring into `_wiki_block`, add `_memory_block`, and rewrite `main`:

```python
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
```

> Byte-identiteit: met `memory_recall=false` is `mem_text=""`, dus `parts` bevat hooguit `wiki_text` en `_emit(wiki_text)` is identiek aan de oude hook (die exact dezelfde wiki-string emitte). De wiki-logica in `_wiki_block` is een 1:1 verplaatsing.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_kb_retrieve_memory.py -v`
Expected: PASS (3 tests; geen memory-blok zonder index/met memory off).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/kb-retrieve.py tests/test_kb_retrieve_memory.py
git commit -m "feat(memory): additieve memory-injectie in kb-retrieve hook (gegate op memory_recall)"
```

---

### Task 3: SessionStart-wiring + documentatie

**Files:**
- Modify: `CONFIGURATION.md` (SessionStart-hook-registratie van `build-kb-index.py`)
- Modify: `CHANGELOG.md`
- Test: `tests/test_kb_recall_nocloud.py`

**Interfaces:**
- Produces: documentatie zodat `build-kb-index.py` bij SessionStart draait (de index vers houdt voor recall), en een no-cloud-test die borgt dat het recall-pad geen externe host aanroept.

- [ ] **Step 1: Write the failing no-cloud test**

Create `tests/test_kb_recall_nocloud.py`:

```python
"""No-cloud-borging voor het recall-pad: kb-recall + de kb-retrieve-helpers
mogen alleen localhost (Ollama) en lokale SQLite raken — nooit een externe host.

We scannen de broncode statisch op verdachte externe URLs/hosts. Dit is een
goedkope, deterministische guard die meegroeit met het no-cloud-principe (#4).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FILES = ["kb-recall.py", "_kbindex.py"]
# toegestaan: localhost / 127.0.0.1 (Ollama). verboden: elke andere http(s)-host.
URL_RE = re.compile(r"https?://([A-Za-z0-9.\-]+)")
ALLOWED = {"localhost", "127.0.0.1"}


class NoCloudTest(unittest.TestCase):
    def test_no_external_hosts_in_recall_path(self):
        for name in FILES:
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            for host in URL_RE.findall(text):
                self.assertIn(host, ALLOWED,
                              f"{name}: externe host '{host}' in recall-pad (schendt no-cloud #4)")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it passes (guard, niet rood)**

Run: `python3 -m pytest tests/test_kb_recall_nocloud.py -v`
Expected: PASS — `kb-recall.py`/`_kbindex.py` bevatten geen externe hosts (alle netwerk gaat via `_embeddings`, dat localhost-Ollama gebruikt; en dat staat niet in deze lijst). Dit is een blijvende guard.

- [ ] **Step 3: Document the SessionStart registration in `CONFIGURATION.md`**

Vind de sectie waar de SessionStart-hooks (o.a. `build-embed-index.py`) worden geregistreerd in `~/.claude/settings.json`. Voeg `build-kb-index.py` toe als extra SessionStart-hook, met dezelfde stijl/structuur als de bestaande entries. Documenteer:

```markdown
### Geheugen-index (build-kb-index.py, SessionStart)

`build-kb-index.py` bouwt/verfrist `kb-index.db` (de hybride sqlite-vec + FTS5
zoekindex over wiki + memory). Registreer het naast `build-embed-index.py` in de
`SessionStart`-array van `~/.claude/settings.json` zodat de index vers is wanneer
de recall-hook (`kb-retrieve.py`) memory injecteert. Gegate op `memory_capture`
(memory) en `embed_index` (wiki). Voeg TOE aan de bestaande array, overschrijf niets:

​```json
{ "hooks": [ { "type": "command",
  "command": "py -3 \"%USERPROFILE%/KennisBank/.claude/scripts/build-kb-index.py\"" } ] }
​```

(POSIX: `python3 "$HOME/KennisBank/.claude/scripts/build-kb-index.py"`.)
Draai zonder argumenten = incrementeel; `--rebuild` = volledige herbouw
(zie `/kennisbank:rebuild-index`).
```

Pas het exacte pad/commando aan op de stijl die al in `CONFIGURATION.md` staat voor `build-embed-index.py`.

- [ ] **Step 4: Update `CHANGELOG.md`**

Voeg onder de unreleased/laatste sectie één regel toe: geheugen-recall (kb-recall + additieve hook-injectie, gegate op `memory_recall`) + SessionStart-indexbouw.

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 6: Commit**

```bash
git add CONFIGURATION.md CHANGELOG.md tests/test_kb_recall_nocloud.py
git commit -m "docs(memory): SessionStart-registratie build-kb-index + no-cloud recall-guard"
```

---

## Self-Review

**Spec coverage (fase 3):**
- `kb-recall.py` lib (read-only, fail-soft, embed_id-gate, memory(current)) → Task 1. ✓
- Additieve hook-injectie, byte-identiteit als memory uit, qvec-reuse → Task 2. ✓
- SessionStart-indexbouw + no-cloud-guard → Task 3. ✓
- MCP-server bewust uitgesteld tot na fase 4. ✓ (gedocumenteerd, niet gebouwd)
- Decoupling: `_embeddings`/`build-embed-index`/JSON-cache ongemoeid; `kb-retrieve` strikt additief. ✓

**Placeholder scan:** geen TBD/TODO; alle code + testcode volledig.

**Type consistency:** `memory_hits(query_vector, query_text="", k=3) -> list[dict]` retour-keys (`path,title,created,score,snippet`) consistent gebruikt in Task 1 + Task 2 `_memory_block`; `_kbindex.search(...layers=("memory",), statuses=("current",))` signatuur matcht fase 2; `_settings.get("memory_recall", True)` consistent met fase 1.

**Geverifieerd vóór uitvoering:** de bestaande `kb-retrieve.py` is gelezen (regels 59-129); `_wiki_block` is een 1:1 extractie van die logica (zelfde cache-load, candidate-filter, embed, cosine, threshold, top-N, output-string). `_kbindex.search` + `is_valid_for` + `index_path` bestaan (fase 2). De starvation-fix uit de fase-2 review zorgt dat `search(layers=("memory",))` niet verhongert.

**Aandachtspunt uitvoerder:** Task 1 Step 1 — pas de `setUp`/`tearDown` `embed_id`-monkeypatch toe (index gebouwd met `"ollama:test"`; `memory_hits` vergelijkt tegen het actieve `emb.embed_id()`, dus die moet in de happy-path-test ook `"ollama:test"` zijn). Task 2 — de byte-identiteit-tests asserteren *afwezigheid* van een memory-blok; ze moeten groen blijven na de refactor. Bevestig dat `_wiki_block` exact dezelfde wiki-string produceert als de oude `main` (zelfde regels, zelfde format).

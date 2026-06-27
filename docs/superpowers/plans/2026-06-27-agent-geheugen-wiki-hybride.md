# Agent-geheugen — Wiki-recall → hybride kb-index (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** De UserPromptSubmit-hook (`kb-retrieve.py`) wiki-recall migreren van pure JSON-cosine naar de **hybride** `kb-index.db` (vector RRF + FTS5), zodat exacte termen (eigennamen, codes, functienamen) die pure vector mist tóch wiki-treffers opleveren — zonder regressie op de bestaande semantische treffers en zonder de hook ooit te breken.

**Architecture:** Strikt **geen regressie + fail-open**. De wiki-injectie krijgt een **dual-signaal gate**: injecteer als (a) de bestaande cosine-relevantie over de JSON-cache ≥ drempel (semantisch relevant, ongewijzigde trigger) OF (b) een FTS5-keyword-match in de wiki-laag van `kb-index.db` (exacte-term-signaal dat vector miste). Als de gate slaagt → injecteer de **hybride** selectie via `kb_recall.recall_hits(layers=("wiki",))`. **Fallback:** ontbreekt/leeg de index, dan val terug op de oude cosine-cache-selectie. De memory-injectie en fail-open blijven ongewijzigd.

**Tech Stack:** Python 3.10+ (stdlib + sqlite-vec), `kb-recall`/`_kbindex`/`_embeddings`, `unittest`.

## Global Constraints

- **Geen regressie (AC #2):** elke prompt die vóór deze migratie wiki injecteerde (cosine ≥ drempel) doet dat nog steeds. De cosine-gate blijft als één van de twee signalen.
- **FTS-winst (AC #4):** een exacte-term-prompt met lage cosine maar een keyword-match in een wiki-artikel triggert nu wél (via het FTS-signaal) en levert dat artikel. Aantoonbaar in de eval.
- **Fail-open (AC #3):** elke fout / ontbrekende index / model onbereikbaar → de hook breekt nooit; ontbreekt de index, dan valt de selectie terug op de cosine-cache (oude gedrag). De hele `main` blijft in try/except.
- **Geen over-trigger:** het FTS-signaal matcht alleen op betekenisvolle tokens (lengte ≥ 4) ge-OR'd; raw-prompt-syntax-fouten in FTS5 → False (geen trigger). Drempels empirisch te tunen (eval).
- **`memory_recall`/embed-gating** en de memory-injectie ongewijzigd. Byte-identiteit van het wiki-pad wordt **bewust losgelaten** (gebruiker akkoord); de gate-trigger blijft echter een superset (cosine OF FTS), dus geen verlies.
- **Decoupling:** `_embeddings.py`, `build-embed-index.py`, `_kbindex.py` ongemoeid (alleen lezen). `kb-recall.py` krijgt een additieve helper; `kb-retrieve.py` `_wiki_block` wordt herschreven.
- **JSON-cache blijft** als compute-cache (build-kb-index hergebruikt 'm) én als fallback-selectie + cosine-gate.

---

### Task 1: `kb_recall` FTS-signaal + wiki-helpers

**Files:**
- Modify: `scripts/kb-recall.py`
- Test: `tests/test_kb_recall.py`

**Interfaces:**
- Produces:
  - `has_fts_match(query_text, layer="wiki") -> bool` — opent `kb-index.db` read-only; tokeniseert de query (woorden ≥ 4 tekens, ge-OR'd); `SELECT 1 FROM fts_docs JOIN docs ON docs.doc_id=fts_docs.rowid WHERE fts_docs MATCH ? AND docs.layer=? LIMIT 1`. True bij een match. Fail-soft (geen index / FTS-syntaxfout / fout → False).
  - `wiki_hits(query_vector, query_text="", k=3) -> list[dict]` — wrapper: `recall_hits(..., layers=("wiki",))`.

- [ ] **Step 1: Write the failing tests**

Voeg toe aan `class KbRecallTest` in `tests/test_kb_recall.py` (de setUp indexeert een memory `m1.md` + wiki `w1.md` met body "wiki artikel"; `emb.embed_id` is gemockt op "ollama:test"):

```python
    def test_has_fts_match_finds_keyword(self):
        # 'artikel' staat in de wiki-body -> FTS-match in de wiki-laag
        self.assertTrue(self.kb.has_fts_match("artikel", layer="wiki"))

    def test_has_fts_match_no_keyword(self):
        self.assertFalse(self.kb.has_fts_match("zwaluwparadox", layer="wiki"))

    def test_has_fts_match_failsoft_bad_query(self):
        # FTS5-syntax-tekens mogen niet crashen -> False
        self.assertFalse(self.kb.has_fts_match('"("', layer="wiki"))

    def test_wiki_hits_only_wiki(self):
        hits = self.kb.wiki_hits([0.9, 0.8, 0.7, 0.6], query_text="wiki", k=5)
        self.assertTrue(all(h["layer"] == "wiki" for h in hits))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_kb_recall.py -k "fts or wiki_hits" -v`
Expected: FAIL — `has_fts_match`/`wiki_hits` ontbreken.

- [ ] **Step 3: Implement the helpers in `kb-recall.py`**

Append to `scripts/kb-recall.py`:

```python
import re as _re


def has_fts_match(query_text: str, layer: str = "wiki") -> bool:
    """True als een FTS5-keyword-match bestaat in de gegeven laag. Fail-soft.

    Tokeniseert op woorden >= 4 tekens (ge-OR'd) zodat stopwoorden en losse
    leestekens geen vals signaal of FTS5-syntaxfout geven."""
    tokens = [t for t in _re.findall(r"[\w]{4,}", (query_text or "").lower())]
    if not tokens:
        return False
    match_expr = " OR ".join(tokens)
    conn = _open_ro(_kbindex.index_path())
    if conn is None:
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM fts_docs JOIN docs ON docs.doc_id = fts_docs.rowid "
            "WHERE fts_docs MATCH ? AND docs.layer = ? LIMIT 1",
            (match_expr, layer)).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def wiki_hits(query_vector, query_text: str = "", k: int = 3) -> list:
    """Dunne wrapper: alleen de wiki-laag (hybride)."""
    return recall_hits(query_vector, query_text=query_text, k=k, layers=("wiki",))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_kb_recall.py -v`
Expected: PASS — de nieuwe + alle bestaande.

- [ ] **Step 5: Commit**

```bash
git add scripts/kb-recall.py tests/test_kb_recall.py
git commit -m "feat(memory): kb-recall has_fts_match + wiki_hits (FTS-signaal voor hybride wiki)"
```

---

### Task 2: `_wiki_block` → hybride (dual-gate + fallback)

**Files:**
- Modify: `scripts/kb-retrieve.py`
- Test: `tests/test_kb_retrieve_wiki.py`

**Interfaces:**
- Produces: `_wiki_block` injecteert wiki hybride. Gate = `cosine_max >= threshold` OR `has_fts_match(prompt, "wiki")`. Bij gate-pass: selectie via `kb_recall.wiki_hits(qvec, prompt, k=top_n)`; lege/fout → fallback naar de cosine-cache-top-N (oude selectie). Return `(wiki_text_of_leeg, qvec)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_kb_retrieve_wiki.py`:

```python
"""Tests voor de hybride wiki-injectie in kb-retrieve._wiki_block. Geen model:
we injecteren qvec/cosine/hits via monkeypatch op de helpers."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_hook():
    spec = importlib.util.spec_from_file_location("kb_retrieve", str(SCRIPTS_DIR / "kb-retrieve.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class WikiBlockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-wiki-"))
        self.vault = self.tmp / "vault"
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.m = _load_hook()
        import _embeddings as emb
        from _vaultpath import vault_root
        self.emb, self.vault_root = emb, vault_root
        # fake emb: één wiki-kandidaat in de cache, embed geeft qvec
        self._orig = (emb.load_cache, emb.embed, emb.cosine, emb.doc_text, emb.embed_id)
        wpath = str(self.vault / "02-wiki" / "art.md")
        emb.embed_id = lambda: "ollama:test"
        emb.load_cache = lambda: {wpath: {"id": "ollama:test", "embedding": [0.1, 0.2], "dim": 2}}
        emb.embed = lambda text, timeout=20.0: [0.1, 0.2]
        emb.doc_text = lambda p, cap=280: "wiki body"

    def tearDown(self):
        import shutil
        (self.emb.load_cache, self.emb.embed, self.emb.cosine,
         self.emb.doc_text, self.emb.embed_id) = self._orig
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cfg(self):
        return {}

    def test_cosine_relevant_injects_hybrid(self):
        self.emb.cosine = lambda a, b: 0.9  # boven drempel -> gate slaagt
        self.m.kb_recall.wiki_hits = lambda qv, query_text="", k=3: [
            {"path": "/v/02-wiki/art.md", "layer": "wiki", "title": "Art",
             "created": "2026-06-01", "score": 0.5, "snippet": "hybride treffer"}]
        text, qvec = self.m._wiki_block("een relevante vraag over het artikel",
                                        self.emb, self.vault_root, self._cfg())
        self.assertIn("hybride treffer", text)
        self.assertIsNotNone(qvec)

    def test_fts_only_triggers_when_cosine_low(self):
        self.emb.cosine = lambda a, b: 0.1  # onder drempel -> alleen FTS kan triggeren
        self.m.kb_recall.has_fts_match = lambda q, layer="wiki": True
        self.m.kb_recall.wiki_hits = lambda qv, query_text="", k=3: [
            {"path": "/v/02-wiki/art.md", "layer": "wiki", "title": "Art",
             "created": "2026-06-01", "score": 0.5, "snippet": "exacte-term-treffer"}]
        text, _ = self.m._wiki_block("FunctieNaamXYZ aanroep",
                                     self.emb, self.vault_root, self._cfg())
        self.assertIn("exacte-term-treffer", text)

    def test_irrelevant_no_injection(self):
        self.emb.cosine = lambda a, b: 0.1
        self.m.kb_recall.has_fts_match = lambda q, layer="wiki": False
        text, _ = self.m._wiki_block("totaal iets anders zonder match",
                                     self.emb, self.vault_root, self._cfg())
        self.assertEqual(text, "")

    def test_fallback_to_cosine_when_hybrid_empty(self):
        self.emb.cosine = lambda a, b: 0.9  # gate slaagt
        self.m.kb_recall.wiki_hits = lambda qv, query_text="", k=3: []  # index leeg
        text, _ = self.m._wiki_block("relevante vraag over het artikel",
                                     self.emb, self.vault_root, self._cfg())
        # fallback naar cosine-cache-selectie: het wiki-artikel staat er
        self.assertIn("[[art]]", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_kb_retrieve_wiki.py -v`
Expected: FAIL — `_wiki_block` is nog de pure cosine-versie (geen hybride/FTS-gate/fallback) en `kb_recall` is nog geen patchbaar module-globaal.

- [ ] **Step 3: Rewrite `_wiki_block` in `kb-retrieve.py`**

Maak `kb_recall` een module-globaal (zoals in `kb-presearch.py`), en herschrijf `_wiki_block`. Voeg bovenin (na de imports) een patchbare loader toe:

```python
# kb-recall als module-globaal zodat tests het kunnen patchen (idem kb-presearch).
import importlib.util as _ilu
kb_recall = None
try:
    _krspec = _ilu.spec_from_file_location(
        "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
    kb_recall = _ilu.module_from_spec(_krspec)
    _krspec.loader.exec_module(kb_recall)
except Exception:
    kb_recall = None
```

Vervang `_wiki_block`:

```python
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
    hits = []
    if kb_recall is not None:
        try:
            hits = kb_recall.wiki_hits(qvec, query_text=prompt, k=top_n)
        except Exception:
            hits = []
    lines = ["KennisBank-wiki (semantisch gematcht op je prompt; raadpleeg bij twijfel):"]
    if hits:
        for h in hits:
            stem = Path(h.get("path", "")).stem
            lines.append(f"- [[{stem}]] ({h.get('score', 0.0):.2f}): {h.get('snippet', '')}")
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
```

> Byte-identiteit-noot: de fallback-tak reproduceert exact de oude cosine-output (header + `- [[stem]] (s.ss): snippet`), zodat bij een ontbrekende index het gedrag identiek is aan vóór de migratie. Met index aanwezig wint de hybride selectie.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_kb_retrieve_wiki.py tests/test_kb_retrieve_memory.py -v`
Expected: PASS — de nieuwe wiki-tests + de bestaande memory-guard-tests (memory-off-gedrag ongewijzigd).

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/kb-retrieve.py tests/test_kb_retrieve_wiki.py
git commit -m "feat(memory): hybride wiki-recall in de hook (dual-gate cosine|FTS + fallback)"
```

---

### Task 3: before/after-eval + docs

**Files:**
- Create: `scripts/eval-wiki-recall.py` (eenmalige eval-helper, geen test-target)
- Modify: `CHANGELOG.md`
- Test: geen (eval is een demo-script).

**Interfaces:**
- Produces: een klein eval-script dat in een tijdelijke vault een paar wiki-artikelen + een index bouwt en aantoont dat de hybride gate een exacte-term-query vindt die de oude vector-only-gate miste. De uitvoerder draait het en plakt de uitkomst in het report.

- [ ] **Step 1: Implement `scripts/eval-wiki-recall.py`**

Create `scripts/eval-wiki-recall.py`:

```python
#!/usr/bin/env python3
"""eval-wiki-recall.py - before/after-demo voor de hybride wiki-recall.

Bouwt in de ACTIEVE vault (KENNISBANK_VAULT) niets nieuws; vergelijkt voor een
paar queries het oude vector-only-signaal met het nieuwe FTS-signaal over de
bestaande kb-index. Read-only. Bedoeld als handmatige eval, niet als test.

Usage: KENNISBANK_VAULT=<vault> python3 eval-wiki-recall.py "query1" "query2" ...
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
import _embeddings as emb

_spec = importlib.util.spec_from_file_location(
    "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
kb_recall = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kb_recall)


def main(argv):
    queries = argv or ["voorbeeldquery"]
    for q in queries:
        qv = emb.embed(q)
        fts = kb_recall.has_fts_match(q, "wiki")
        hits = kb_recall.wiki_hits(qv, query_text=q, k=3) if qv else []
        print(f"\nQUERY: {q!r}")
        print(f"  FTS-keyword-match (wiki): {fts}")
        print(f"  hybride treffers: {[ (Path(h['path']).stem, round(h['score'],3)) for h in hits ]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 2: Run the eval (manual, real model)**

Bouw een kleine eval-vault met twee wiki-artikelen — één semantisch over "tijd-vergelijkingen", één met een exacte term als `qwen3-embedding:8b` — bouw de index (`build-kb-index.py`), en draai:

```bash
KENNISBANK_VAULT=<eval-vault> python3 scripts/eval-wiki-recall.py \
  "hoe vergelijk je tijdstempels" "qwen3-embedding:8b"
```

Verwacht: de semantische query vindt het tijd-artikel (vector); de exacte-term-query `qwen3-embedding:8b` geeft `FTS-keyword-match: True` en vindt het juiste artikel — terwijl pure vector dat (waarschijnlijk) miste. Plak de uitvoer in het report als before/after-bewijs (AC #4). Bij gelijke/betere uitkomst: geen regressie (AC #2).

- [ ] **Step 3: Update `CHANGELOG.md`**

Eén regel: hybride wiki-recall in de UserPromptSubmit-hook (dual-gate cosine|FTS5 + cosine-fallback) — exacte termen vinden nu ook wiki-artikelen.

- [ ] **Step 4: Run the full suite (sanity)**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/eval-wiki-recall.py CHANGELOG.md
git commit -m "feat(memory): wiki-recall eval-script + changelog (hybride before/after)"
```

---

## Self-Review

**Spec coverage (TASK-10):**
- Wiki-recall via kb-index hybride (vector+FTS5) i.p.v. JSON-cosine (AC #1) → Task 2 selectie via `wiki_hits`. ✓
- Geen regressie op kern-queries (AC #2) → cosine-gate blijft één van de twee signalen; fallback reproduceert oude output. ✓
- Fail-open; index ontbreekt → fallback/geen crash (AC #3) → Task 2 fallback-tak + try/except. ✓
- FTS vangt exacte-term-queries die vector miste (AC #4) → `has_fts_match`-signaal (Task 1) + eval (Task 3). ✓
- Mockbaar: wiki-tests patchen cosine/has_fts_match/wiki_hits. ✓

**Placeholder scan:** geen TBD/TODO; alle code + testcode volledig.

**Type consistency:** `has_fts_match(query_text, layer)->bool`, `wiki_hits(qvec, query_text, k)->[{path,layer,title,created,score,snippet}]` consistent; `_wiki_block(prompt, emb, vault_root, cfg)->(str, qvec)` ongewijzigde signatuur (de memory-tak hergebruikt qvec); `kb_recall` module-globaal patchbaar (idem kb-presearch/kb-mcp).

**Geverifieerd vóór uitvoering:** `recall_hits(layers=("wiki",))` (fase A) bestaat; `_kbindex` FTS-tabel heet `fts_docs` met `rowid`=doc_id, `docs` heeft `layer`; de hook embedt al qvec één keer; `kb-retrieve` `_wiki_block` is gelezen (de cosine-logica + output-format wordt in de fallback exact gereproduceerd). De memory-tak (`_memory_block`) en `main` blijven ongewijzigd.

**Aandachtspunt uitvoerder:** Task 2 — maak `kb_recall` een module-globaal en lees het in `_wiki_block` (geen lokale her-import), zodat de tests `m.kb_recall.wiki_hits`/`has_fts_match` kunnen patchen (idem kb-presearch). Bevestig dat de bestaande `test_kb_retrieve_memory`-guard-tests groen blijven (memory-off-gedrag + triviale-prompt ongewijzigd). De FTS-`MATCH`-query gebruikt ge-OR'de tokens ≥4 tekens — bevestig dat een prompt met FTS5-syntaxtekens geen exceptie geeft (fail-soft → False).

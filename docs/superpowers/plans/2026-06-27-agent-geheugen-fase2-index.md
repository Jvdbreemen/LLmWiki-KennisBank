# Agent-geheugen — Fase 2: kb-index.db (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Een lokale, herbouwbare hybride zoekindex `kb-index.db` (sqlite-vec `vec0` brute-force KNN + FTS5 keyword) over `02-wiki/` en `09-memory/`(current), plus een `build-kb-index.py`-bouwer en het `/kennisbank:rebuild-index`-commando. Additief — raakt geen bestaand gedrag.

**Architecture:** Nieuwe module `scripts/_kbindex.py` (pure functies: connect, schema, upsert, prune, search) bovenop SQLite met de `sqlite-vec`-extensie en FTS5 (stdlib). De vector-dimensie wordt afgeleid van het **live embedmodel** (geverifieerd: `qwen3-embedding:8b` → 4096), nooit gehardcode. `build-kb-index.py` hergebruikt `_embeddings.get_cached` (de bestaande JSON compute-cache) zodat vectoren niet opnieuw berekend worden; `kb-index.db` is de afgeleide zoekstructuur ernaast. Bestaande `kb-retrieve.py`/`build-embed-index.py` blijven ongemoeid (decoupling #9); recall verhuist pas in fase 3.

**Tech Stack:** Python 3.10+ (stdlib `sqlite3`), `sqlite-vec` (pip, gepind `v0.1.9`), FTS5 (in stdlib sqlite), `unittest`.

## Global Constraints

- **sqlite-vec gepind op `v0.1.9`** (geverifieerd ladend op Windows/py3.14: `vec_version()=v0.1.9`). Brute-force `vec0`; GEEN experimentele IVF/DiskANN.
- **Dimensie afgeleid van live model**, nooit literal. Geverifieerd: `emb.embed("...")` → `len`=4096 voor `qwen3-embedding:8b`. Opslaan in `meta`-tabel samen met `embed_id()`.
- **`embed_id()`-gate:** verschilt het opgeslagen `embed_id` van het actieve → index is ongeldig, volledige rebuild (zelfde cross-model-veiligheid als de JSON-cache).
- **Index-pad:** `<vault>/.claude/kb-index.db`.
- **Toggle-gates:** wiki indexeren onder bestaande `embed_index`; memory(`status: current`) onder `memory_capture`. `_settings.get(key, default)`.
- **Decoupling #9:** geen wijziging aan `kb-retrieve.py`, `build-embed-index.py`, of de JSON-cache. `kb-index.db` is volledig nieuw/additief.
- **Herbouwbaar #6:** `--rebuild` reconstrueert de db volledig uit de markdown-files. Raakt nooit markdown.
- **Stdlib + één pip-dep (`sqlite-vec`).** Module-conventie als bestaande scripts: `os.environ.setdefault("KENNISBANK_VAULT", parents[2])`, `sys.path.insert`, underscore-naam.
- **Testbaarheid zonder Ollama:** `_kbindex`-functies nemen vectoren als argument (geen embed-call binnenin). Bouwer-tests monkeypatchen `_embeddings.embed`/`get_cached` met een deterministische fake-vector. Geen test mag een echt embedmodel vereisen.
- **API (geverifieerd):** vector-KNN `SELECT doc_id, distance FROM vec_docs WHERE embedding MATCH ? ORDER BY distance LIMIT ?` met `sqlite_vec.serialize_float32(vec)`; FTS `SELECT rowid, rank FROM fts_docs WHERE fts_docs MATCH ? ORDER BY rank LIMIT ?`. Lagere `distance`/`rank` = relevanter.

---

### Task 1: `_kbindex.py` — verbinding + schema + dimensie

**Files:**
- Create: `scripts/_kbindex.py`
- Test: `tests/test_kbindex_schema.py`

**Interfaces:**
- Consumes: `_vaultpath.vault_root`, `_embeddings.embed_id`.
- Produces:
  - `INDEX_PATH -> Path` helper `index_path() = <vault>/.claude/kb-index.db`
  - `connect(path=None) -> sqlite3.Connection` — opent, laadt sqlite-vec, zet pragmas
  - `ensure_schema(conn, dim: int, embed_id: str) -> None` — maakt tabellen + `meta` indien afwezig (idempotent)
  - `meta_get(conn, key) -> str | None`
  - `is_valid_for(conn, embed_id: str) -> bool` — True als opgeslagen `embed_id` gelijk is
  - Tabellen: `meta(key TEXT PRIMARY KEY, value TEXT)`; `docs(doc_id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, layer TEXT, status TEXT, hash TEXT, title TEXT, created TEXT)`; `vec_docs USING vec0(doc_id INTEGER PRIMARY KEY, embedding float[dim])`; `fts_docs USING fts5(body)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_kbindex_schema.py`:

```python
"""Tests voor scripts/_kbindex.py - verbinding + schema.

Gebruikt een echte sqlite-vec (pip-dep), maar geen embedmodel: vectoren zijn
fake. Vault naar temp via KENNISBANK_VAULT.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _kbindex  # noqa: E402


class KbIndexSchemaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-idx-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_index_path_under_claude(self):
        self.assertEqual(_kbindex.index_path(), self.vault / ".claude" / "kb-index.db")

    def test_connect_loads_sqlite_vec(self):
        conn = _kbindex.connect(":memory:")
        ver = conn.execute("select vec_version()").fetchone()[0]
        self.assertTrue(ver.startswith("v"))
        conn.close()

    def test_ensure_schema_idempotent_and_stores_meta(self):
        conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(conn, dim=8, embed_id="ollama:test")
        _kbindex.ensure_schema(conn, dim=8, embed_id="ollama:test")  # twice = no error
        self.assertEqual(_kbindex.meta_get(conn, "embed_id"), "ollama:test")
        self.assertEqual(_kbindex.meta_get(conn, "dim"), "8")
        tables = {r[0] for r in conn.execute(
            "select name from sqlite_master where type in ('table','view')")}
        self.assertIn("docs", tables)
        self.assertIn("meta", tables)
        conn.close()

    def test_is_valid_for(self):
        conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(conn, dim=8, embed_id="ollama:m1")
        self.assertTrue(_kbindex.is_valid_for(conn, "ollama:m1"))
        self.assertFalse(_kbindex.is_valid_for(conn, "ollama:m2"))
        conn.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_kbindex_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_kbindex'`.

- [ ] **Step 3: Implement `_kbindex.py` (connection + schema portion)**

Create `scripts/_kbindex.py`:

```python
#!/usr/bin/env python3
"""_kbindex.py - lokale hybride zoekindex (sqlite-vec vec0 + FTS5).

Afgeleide, herbouwbare index over de vault-markdown. Markdown blijft bron van
waarheid; deze .db is een wegwerp-cache (rm + rebuild). Brute-force vec0 KNN +
FTS5 keyword. Dimensie komt van het live embedmodel (nooit gehardcode); embed_id
wordt opgeslagen zodat een modelwissel de index ongeldig maakt.

Pure functies: vectoren komen als argument binnen (geen embed-call hier), zodat
de module testbaar is zonder embedmodel. sqlite-vec is een pip-dep (gepind).

Stdlib + sqlite-vec.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402


def index_path() -> Path:
    return vault_root() / ".claude" / "kb-index.db"


def connect(path=None) -> sqlite3.Connection:
    import sqlite_vec
    p = str(path) if path is not None else str(index_path())
    if path is None:
        index_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection, dim: int, embed_id: str) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS docs ("
        "doc_id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, "
        "layer TEXT, status TEXT, hash TEXT, title TEXT, created TEXT)")
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_docs USING vec0("
        f"doc_id INTEGER PRIMARY KEY, embedding float[{int(dim)}])")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_docs USING fts5(body)")
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('dim', ?)", (str(int(dim)),))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('embed_id', ?)", (embed_id,))
    conn.commit()


def meta_get(conn: sqlite3.Connection, key: str):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def is_valid_for(conn: sqlite3.Connection, embed_id: str) -> bool:
    return meta_get(conn, "embed_id") == embed_id
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_kbindex_schema.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_kbindex.py tests/test_kbindex_schema.py
git commit -m "feat(memory): _kbindex.py verbinding + schema (sqlite-vec vec0 + FTS5)"
```

---

### Task 2: upsert + prune + incrementeel

**Files:**
- Modify: `scripts/_kbindex.py` (functies toevoegen)
- Test: `tests/test_kbindex_upsert.py`

**Interfaces:**
- Consumes: Task 1's `connect`, `ensure_schema`.
- Produces:
  - `upsert(conn, *, path, layer, status, body, vector, file_hash, title="", created="") -> int` — insert/replace een doc over de drie tabellen (gedeelde `doc_id`); return `doc_id`
  - `indexed_hash(conn, path) -> str | None` — opgeslagen hash of None (voor incrementeel overslaan)
  - `prune(conn, keep_paths: set[str]) -> int` — verwijder docs (+ fts/vec) wier `path` niet in `keep_paths` zit; return aantal verwijderd
  - `count(conn) -> int` — aantal docs

- [ ] **Step 1: Write the failing test**

Create `tests/test_kbindex_upsert.py`:

```python
from __future__ import annotations

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


def _vec(seed: float):
    return [seed, seed + 0.1, seed + 0.2, seed + 0.3]


class KbIndexUpsertTest(unittest.TestCase):
    def setUp(self):
        self.conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(self.conn, dim=DIM, embed_id="ollama:test")

    def tearDown(self):
        self.conn.close()

    def test_upsert_inserts_one_doc_across_tables(self):
        _kbindex.upsert(self.conn, path="a.md", layer="wiki", status="current",
                        body="hook gedreven retrieval", vector=_vec(0.1),
                        file_hash="h1", title="A", created="2026-06-27")
        self.assertEqual(_kbindex.count(self.conn), 1)
        n_vec = self.conn.execute("SELECT count(*) FROM vec_docs").fetchone()[0]
        n_fts = self.conn.execute("SELECT count(*) FROM fts_docs").fetchone()[0]
        self.assertEqual((n_vec, n_fts), (1, 1))

    def test_upsert_same_path_replaces_not_duplicates(self):
        _kbindex.upsert(self.conn, path="a.md", layer="wiki", status="current",
                        body="oud", vector=_vec(0.1), file_hash="h1")
        _kbindex.upsert(self.conn, path="a.md", layer="wiki", status="current",
                        body="nieuw", vector=_vec(0.2), file_hash="h2")
        self.assertEqual(_kbindex.count(self.conn), 1)
        self.assertEqual(_kbindex.indexed_hash(self.conn, "a.md"), "h2")
        body = self.conn.execute("SELECT body FROM fts_docs").fetchone()[0]
        self.assertEqual(body, "nieuw")

    def test_indexed_hash_missing_is_none(self):
        self.assertIsNone(_kbindex.indexed_hash(self.conn, "ontbreekt.md"))

    def test_prune_removes_absent_paths(self):
        _kbindex.upsert(self.conn, path="a.md", layer="wiki", status="current",
                        body="a", vector=_vec(0.1), file_hash="h1")
        _kbindex.upsert(self.conn, path="b.md", layer="memory", status="current",
                        body="b", vector=_vec(0.2), file_hash="h2")
        removed = _kbindex.prune(self.conn, keep_paths={"a.md"})
        self.assertEqual(removed, 1)
        self.assertEqual(_kbindex.count(self.conn), 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM vec_docs").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_kbindex_upsert.py -v`
Expected: FAIL — `AttributeError: module '_kbindex' has no attribute 'upsert'`.

- [ ] **Step 3: Add upsert/prune/indexed_hash/count to `_kbindex.py`**

Append to `scripts/_kbindex.py`:

```python
def _serialize(vector):
    from sqlite_vec import serialize_float32
    return serialize_float32(list(vector))


def indexed_hash(conn: sqlite3.Connection, path: str):
    row = conn.execute("SELECT hash FROM docs WHERE path=?", (path,)).fetchone()
    return row[0] if row else None


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT count(*) FROM docs").fetchone()[0]


def upsert(conn: sqlite3.Connection, *, path: str, layer: str, status: str,
           body: str, vector, file_hash: str, title: str = "",
           created: str = "") -> int:
    """Insert/replace een doc over docs+fts_docs+vec_docs onder één doc_id."""
    row = conn.execute("SELECT doc_id FROM docs WHERE path=?", (path,)).fetchone()
    if row:
        doc_id = row[0]
        conn.execute(
            "UPDATE docs SET layer=?, status=?, hash=?, title=?, created=? WHERE doc_id=?",
            (layer, status, file_hash, title, created, doc_id))
        conn.execute("DELETE FROM fts_docs WHERE rowid=?", (doc_id,))
        conn.execute("DELETE FROM vec_docs WHERE doc_id=?", (doc_id,))
    else:
        cur = conn.execute(
            "INSERT INTO docs(path, layer, status, hash, title, created) "
            "VALUES (?,?,?,?,?,?)", (path, layer, status, file_hash, title, created))
        doc_id = cur.lastrowid
    conn.execute("INSERT INTO fts_docs(rowid, body) VALUES (?, ?)", (doc_id, body))
    conn.execute("INSERT INTO vec_docs(doc_id, embedding) VALUES (?, ?)",
                 (doc_id, _serialize(vector)))
    conn.commit()
    return doc_id


def prune(conn: sqlite3.Connection, keep_paths: set) -> int:
    rows = conn.execute("SELECT doc_id, path FROM docs").fetchall()
    gone = [(d, p) for (d, p) in rows if p not in keep_paths]
    for doc_id, _ in gone:
        conn.execute("DELETE FROM docs WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM fts_docs WHERE rowid=?", (doc_id,))
        conn.execute("DELETE FROM vec_docs WHERE doc_id=?", (doc_id,))
    conn.commit()
    return len(gone)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_kbindex_upsert.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_kbindex.py tests/test_kbindex_upsert.py
git commit -m "feat(memory): _kbindex upsert/prune/incrementeel"
```

---

### Task 3: hybride zoek (vector + FTS, layer/status-filter)

**Files:**
- Modify: `scripts/_kbindex.py`
- Test: `tests/test_kbindex_search.py`

**Interfaces:**
- Consumes: Task 1-2.
- Produces:
  - `search(conn, *, query_vector, query_text="", k=8, layers=None, statuses=("current",)) -> list[dict]`
    - Resultaat-dict: `{"path","layer","status","title","created","score"}`, gesorteerd hoog→laag `score`.
    - Fusie: Reciprocal Rank Fusion (RRF) over de vector-rangschikking (oplopende `distance`) en de FTS-rangschikking (oplopende `rank`). `query_text=""` → alleen vector. `statuses=None` → geen statusfilter.

- [ ] **Step 1: Write the failing test**

Create `tests/test_kbindex_search.py`:

```python
from __future__ import annotations

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


class KbIndexSearchTest(unittest.TestCase):
    def setUp(self):
        self.conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(self.conn, dim=DIM, embed_id="ollama:test")
        # twee dichtbij, één ver weg
        _kbindex.upsert(self.conn, path="near.md", layer="memory", status="current",
                        body="hook gedreven retrieval bug", vector=[0.10, 0.20, 0.30, 0.40],
                        file_hash="h1", created="2026-06-01")
        _kbindex.upsert(self.conn, path="far.md", layer="wiki", status="current",
                        body="sqlite vector index", vector=[0.90, 0.80, 0.70, 0.60],
                        file_hash="h2", created="2026-06-02")
        _kbindex.upsert(self.conn, path="hidden.md", layer="memory", status="unverified",
                        body="hook geheim", vector=[0.11, 0.21, 0.31, 0.41],
                        file_hash="h3", created="2026-06-03")

    def tearDown(self):
        self.conn.close()

    def test_vector_only_orders_by_proximity(self):
        res = _kbindex.search(self.conn, query_vector=[0.10, 0.20, 0.30, 0.40], k=5)
        paths = [r["path"] for r in res]
        self.assertEqual(paths[0], "near.md")  # exact match bovenaan
        self.assertIn("far.md", paths)

    def test_status_filter_excludes_unverified(self):
        res = _kbindex.search(self.conn, query_vector=[0.11, 0.21, 0.31, 0.41], k=5,
                              statuses=("current",))
        self.assertNotIn("hidden.md", [r["path"] for r in res])

    def test_layer_filter(self):
        res = _kbindex.search(self.conn, query_vector=[0.10, 0.20, 0.30, 0.40], k=5,
                              layers=("wiki",))
        self.assertEqual([r["path"] for r in res], ["far.md"])

    def test_hybrid_uses_keyword(self):
        # vector wijst naar far, maar keyword 'bug' staat alleen in near
        res = _kbindex.search(self.conn, query_vector=[0.90, 0.80, 0.70, 0.60],
                              query_text="bug", k=5)
        self.assertIn("near.md", [r["path"] for r in res])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_kbindex_search.py -v`
Expected: FAIL — `AttributeError: module '_kbindex' has no attribute 'search'`.

- [ ] **Step 3: Add `search` to `_kbindex.py`**

Append to `scripts/_kbindex.py`:

```python
def _rrf(rank_lists, k_const: int = 60) -> dict:
    """Reciprocal Rank Fusion: doc_id -> gefuseerde score (hoger = beter)."""
    scores: dict = {}
    for ranking in rank_lists:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k_const + rank)
    return scores


def search(conn: sqlite3.Connection, *, query_vector, query_text: str = "",
           k: int = 8, layers=None, statuses=("current",)) -> list:
    pool = max(k * 4, 20)
    vec_ranking = [r[0] for r in conn.execute(
        "SELECT doc_id FROM vec_docs WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
        (_serialize(query_vector), pool)).fetchall()]
    rankings = [vec_ranking]
    if query_text.strip():
        try:
            fts_ranking = [r[0] for r in conn.execute(
                "SELECT rowid FROM fts_docs WHERE fts_docs MATCH ? ORDER BY rank LIMIT ?",
                (query_text, pool)).fetchall()]
            rankings.append(fts_ranking)
        except sqlite3.OperationalError:
            pass  # FTS-syntaxfout (rare query) -> alleen vector
    fused = _rrf(rankings)
    if not fused:
        return []
    placeholders = ",".join("?" for _ in fused)
    meta = {r[0]: r for r in conn.execute(
        f"SELECT doc_id, path, layer, status, title, created FROM docs "
        f"WHERE doc_id IN ({placeholders})", tuple(fused)).fetchall()}
    out = []
    for doc_id, score in fused.items():
        row = meta.get(doc_id)
        if not row:
            continue
        _, path, layer, status, title, created = row
        if layers is not None and layer not in layers:
            continue
        if statuses is not None and status not in statuses:
            continue
        out.append({"path": path, "layer": layer, "status": status,
                    "title": title, "created": created, "score": score})
    out.sort(key=lambda d: d["score"], reverse=True)
    return out[:k]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_kbindex_search.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_kbindex.py tests/test_kbindex_search.py
git commit -m "feat(memory): _kbindex hybride zoek (RRF over vector + FTS)"
```

---

### Task 4: `build-kb-index.py` bouwer + `/kennisbank:rebuild-index`

**Files:**
- Create: `scripts/build-kb-index.py`
- Create: `commands/kennisbank/rebuild-index.md`
- Test: `tests/test_build_kb_index.py`

**Interfaces:**
- Consumes: `_kbindex` (Task 1-3), `_embeddings` (`get_cached`, `embed_id`, `file_hash`, `doc_text`, `load_cache`, `save_cache`), `_settings.get`, `_memory.read_status`, `_frontmatter.parse_frontmatter`, `_vaultpath.vault_root`.
- Produces:
  - `build-kb-index.py` met `main(rebuild=False)`:
    - Embed_id-mismatch OF `rebuild=True` → verwijder `kb-index.db`, verse schema.
    - Itereer `02-wiki/**/*.md` (skip `index.md`,`log.md`) als `embed_index` aan, layer `wiki`, status `current`.
    - Itereer `09-memory/**/*.md` (skip `archive/`-only? nee: incl.) als `memory_capture` aan, layer `memory`, alleen `status==current` (via `_memory.read_status`).
    - Per file: `emb.get_cached` voor de vector (hergebruikt JSON-cache); incrementeel overslaan als `indexed_hash==file_hash` en geen rebuild. `upsert`. `prune` op de verzameling geziene paden.
    - Print één-regel samenvatting.
  - CLI: `python3 build-kb-index.py [--rebuild]`.
  - `commands/kennisbank/rebuild-index.md`: commando dat `python3 "$VAULT/.claude/scripts/build-kb-index.py" --rebuild` draait en de samenvatting toont.

- [ ] **Step 1: Write the failing test**

Create `tests/test_build_kb_index.py`:

```python
"""Tests voor build-kb-index.py - de bouwer.

Monkeypatcht _embeddings zodat geen echt embedmodel nodig is: get_cached geeft
een deterministische fake-vector. Vault naar temp.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

DIM = 8


def _fake_vec(path, cache, recompute=True):
    # deterministisch op basis van de bestandsnaam
    h = sum(bytes(str(path), "utf-8")) % 97
    return [float((h + i) % 13) / 13.0 for i in range(DIM)]


class BuildKbIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-build-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        # wiki-artikel
        (self.vault / "02-wiki" / "alpha.md").write_text(
            "---\ntitle: Alpha\nstatus: concept\n---\n\nAlpha body hook.", encoding="utf-8")
        # memory current + unverified
        (self.vault / "09-memory" / "m1.md").write_text(
            "---\ntitle: M1\ntype: memory\nstatus: current\ncreated: 2026-06-27\n---\n\nMemory een.",
            encoding="utf-8")
        (self.vault / "09-memory" / "m2.md").write_text(
            "---\ntitle: M2\ntype: memory\nstatus: unverified\ncreated: 2026-06-27\n---\n\nMemory twee.",
            encoding="utf-8")
        # importeer modules met de temp-vault actief
        for m in ("_vaultpath", "_embeddings", "_kbindex"):
            if m in sys.modules:
                importlib.reload(sys.modules[m])
        import _embeddings as emb
        self._orig_get_cached = emb.get_cached
        emb.get_cached = _fake_vec  # geen echt model
        emb.embed_id = lambda: "ollama:fake"
        self.emb = emb

    def tearDown(self):
        import shutil
        self.emb.get_cached = self._orig_get_cached
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, rebuild=False):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_kb_index", str(SCRIPTS_DIR / "build-kb-index.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main(rebuild=rebuild)
        return mod

    def test_build_indexes_wiki_and_current_memory_only(self):
        self._build(rebuild=True)
        import _kbindex
        conn = _kbindex.connect()
        paths = {r[0] for r in conn.execute("SELECT path FROM docs").fetchall()}
        conn.close()
        names = {Path(p).name for p in paths}
        self.assertIn("alpha.md", names)   # wiki
        self.assertIn("m1.md", names)      # memory current
        self.assertNotIn("m2.md", names)   # memory unverified -> niet geindexeerd

    def test_rebuild_is_idempotent(self):
        self._build(rebuild=True)
        self._build(rebuild=True)
        import _kbindex
        conn = _kbindex.connect()
        n = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
        conn.close()
        self.assertEqual(n, 2)  # alpha + m1, geen duplicaten


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_build_kb_index.py -v`
Expected: FAIL — bouwerscript bestaat nog niet (`spec_from_file_location` → exec faalt / FileNotFound).

- [ ] **Step 3: Implement `scripts/build-kb-index.py`**

Create `scripts/build-kb-index.py`:

```python
#!/usr/bin/env python3
"""Bouw/ververs kb-index.db uit de vault-markdown.

Hybride zoekindex (sqlite-vec + FTS5) over 02-wiki en 09-memory(current).
Afgeleid + herbouwbaar: --rebuild dropt de db en bouwt opnieuw uit files.
Hergebruikt de JSON embed-cache (emb.get_cached) zodat vectoren niet opnieuw
berekend worden. Toggle-gates: wiki onder embed_index, memory onder memory_capture.

Stdlib + sqlite-vec. Usage: python3 build-kb-index.py [--rebuild]
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _kbindex  # noqa: E402
import _settings  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _memory import read_status  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

VAULT = vault_root()
WIKI = VAULT / "02-wiki"
MEMORY = VAULT / "09-memory"
WIKI_SKIP = {"index.md", "log.md"}


def _title_created(path):
    try:
        fm, _ = parse_frontmatter(Path(path).read_text(encoding="utf-8"))
        return fm.get("title", ""), fm.get("created", "")
    except Exception:
        return "", ""


def _collect():
    """(path, layer, status) voor elke te indexeren file, gated op toggles."""
    items = []
    if _settings.get("embed_index", True) and WIKI.exists():
        for f in sorted(WIKI.glob("**/*.md")):
            if f.name in WIKI_SKIP:
                continue
            items.append((f, "wiki", "current"))
    if _settings.get("memory_capture", True) and MEMORY.exists():
        for f in sorted(MEMORY.glob("**/*.md")):
            if read_status(f) == "current":
                items.append((f, "memory", "current"))
    return items


def main(rebuild: bool = False) -> None:
    eid = emb.embed_id()
    idx = _kbindex.index_path()
    if rebuild and idx.exists():
        idx.unlink()
    conn = _kbindex.connect()
    # dim van het live model; faal-zacht als het model onbereikbaar is
    probe = emb.embed("dimensie-probe")
    if not probe:
        print("kb-index: embedmodel onbereikbaar, overgeslagen", file=sys.stderr)
        conn.close()
        return
    dim = len(probe)
    # embed_id-mismatch => index ongeldig, verse start
    if idx != Path(":memory:") and conn.execute(
            "SELECT name FROM sqlite_master WHERE name='meta'").fetchone():
        if not _kbindex.is_valid_for(conn, eid):
            conn.close()
            if idx.exists():
                idx.unlink()
            conn = _kbindex.connect()
    _kbindex.ensure_schema(conn, dim=dim, embed_id=eid)

    cache = emb.load_cache()
    seen = set()
    indexed = skipped = failed = 0
    for f, layer, status in _collect():
        sp = str(f)
        seen.add(sp)
        fh = emb.file_hash(f)
        if not rebuild and _kbindex.indexed_hash(conn, sp) == fh:
            skipped += 1
            continue
        vec = emb.get_cached(f, cache)
        if not vec:
            failed += 1
            continue
        title, created = _title_created(f)
        _kbindex.upsert(conn, path=sp, layer=layer, status=status,
                        body=emb.doc_text(f), vector=vec, file_hash=fh,
                        title=title, created=created)
        indexed += 1
    removed = _kbindex.prune(conn, keep_paths=seen)
    emb.save_cache(cache)
    conn.close()
    print(f"kb-index: {len(seen)} files, {indexed} (re)indexed, {skipped} ongewijzigd, "
          f"{removed} verwijderd, {failed} failed, backend={eid}")


if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv[1:]
    try:
        main(rebuild=rebuild)
    except Exception as e:
        print(f"kb-index: overgeslagen ({e})", file=sys.stderr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_build_kb_index.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Create the `/kennisbank:rebuild-index` command**

Create `commands/kennisbank/rebuild-index.md` (match the style of `commands/kennisbank/settings.md`):

```markdown
---
description: Herbouw de lokale zoekindex kb-index.db uit de vault-markdown (snel, deterministisch)
---

# /kennisbank:rebuild-index

Herbouwt `kb-index.db` (de hybride sqlite-vec + FTS5 zoekindex) volledig opnieuw
uit de markdown-files. Snel en deterministisch; raakt **geen** markdown — de
index is een wegwerp-cache. Gebruik dit na een modelwissel, na bulk-import, of
als de index achterloopt.

Draai:

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/build-kb-index.py" --rebuild
```

Toon daarna de samenvattingsregel die het script print (aantal files, (re)indexed,
verwijderd, backend). Bij "embedmodel onbereikbaar": meld dat Ollama niet draait;
de index blijft staan zoals hij was.
```

- [ ] **Step 6: Run the full suite (no regressions)**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/build-kb-index.py commands/kennisbank/rebuild-index.md tests/test_build_kb_index.py
git commit -m "feat(memory): build-kb-index.py bouwer + /kennisbank:rebuild-index"
```

---

## Self-Review

**Spec coverage (fase 2):**
- sqlite-vec vec0 + FTS5 index → Task 1 schema, Task 3 search. ✓
- Dim van live model (4096), niet 1536; embed_id-gate → Task 1 `ensure_schema` + Task 4 mismatch-rebuild. ✓
- Incrementeel + prune + rebuild → Task 2 + Task 4. ✓
- Toggle-gates (wiki=embed_index, memory=memory_capture, alleen current) → Task 4 `_collect`. ✓
- Hybride RRF zoek met layer/status-filter → Task 3. ✓
- `/kennisbank:rebuild-index` → Task 4. ✓
- Decoupling #9: geen wijziging aan kb-retrieve/build-embed-index/JSON-cache; kb-index.db nieuw. ✓
- Testbaar zonder Ollama: `_kbindex` neemt vectoren als arg; bouwer-test monkeypatcht emb. ✓
- Buiten fase 2 (bewust): recall-hook/MCP (fase 3), capture/sweep (4), rebuild-memory/backfill/health (5).

**Placeholder scan:** geen TBD/TODO; alle code + testcode volledig.

**Type consistency:** `upsert(**kw)` keyword-namen (`path,layer,status,body,vector,file_hash,title,created`) consistent in Task 2-4; `search` retour-dict keys (`path,layer,status,title,created,score`) consistent met de bouwer-velden; `ensure_schema(conn,dim,embed_id)` signatuur identiek aangeroepen in Task 1-test en Task 4-bouwer; `index_path()`/`connect()`/`is_valid_for` consistent.

**Geverifieerd vóór uitvoering:** sqlite-vec `v0.1.9` laadt (Windows/py3.14); `vec0` KNN via `MATCH ... ORDER BY distance`, FTS5 via `MATCH ... ORDER BY rank`, `serialize_float32` — alle drie empirisch getest. Live dim = 4096 (`qwen3-embedding:8b`). De testvectoren gebruiken kleine dims (4/8) — toegestaan, want de dim is per-index parametrisch.

**Aandachtspunt uitvoerder:** Task 4-test herlaadt modules en monkeypatcht `emb.get_cached`/`embed_id`. Als import-volgorde in de testomgeving anders ligt, draai de test geïsoleerd (`pytest tests/test_build_kb_index.py`) en bevestig dat `_kbindex.connect()` de temp-vault-db opent (niet de echte). De `index_path()` leest `vault_root()` at call-time, dus de temp-`KENNISBANK_VAULT` moet vóór `connect()` gezet zijn — dat is zo in de test-`setUp`.

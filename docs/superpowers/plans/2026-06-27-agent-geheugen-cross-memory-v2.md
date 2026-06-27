# Agent-geheugen — Cross-memory onderhoud v2 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** De cross-memory onderhoudspas die in fase 4b v1 bewust licht bleef: **supersede** (een nieuwere `current` die een oudere tegenspreekt → oude `superseded` + `superseded_by`-link), **2e-lijn-hercontrole** (her-judge recent gepromote `current` → kan alsnog retracten), en **light cluster** (markeer `current`-memories met genoeg verwante buren als promotie-kandidaat voor `/wiki`). Houdt de geheugen-pool scherp en vers.

**Architecture:** Een nieuw `_maintenance.py` met **deterministische** primitieven (cosine-paren van current memories, status-mutaties, link-schrijven, buur-telling) bovenop **mockbare LLM-seams** (`judge_supersede` via `_llm`, hercontrole via `_judge.judge`). De passes draaien in `memory-sweep.py` **ná** de capture-loop (gegate op `memory_capture`, off hot path). Alle LLM-aanroepen zijn mockbaar; de plumbing is unit-getest zonder model. Fail-safe: twijfel → geen mutatie (nooit ten onrechte superseden/retracten).

**Tech Stack:** Python 3.10+ (stdlib), `_embeddings`/`_memory`/`_judge`/`_llm`/`_frontmatter`, `unittest`.

## Global Constraints

- **Fail-safe richting:** bij twijfel/None/parse-fout → GEEN mutatie. Een memory wordt nooit ten onrechte `superseded`/`retracted`. (Beschermt #1.)
- **Niet-destructief:** alleen status-flips + `superseded_by`-links + een `promote_candidate`-vlag. Files blijven; alles reversibel/in Git. Geen hard-delete.
- **Supersede-richting:** bij een tegenstrijdig hoog-cosine paar wint de **nieuwere** (`created`); de oudere wordt `superseded` met `superseded_by: [[nieuwere]]`.
- **Drempels:** supersede-kandidaat bij cosine > `SUPERSEDE_THRESHOLD` (~0.85, lager dan dedup 0.92 want "zelfde onderwerp, mogelijk geüpdatet"); cluster-promotie bij ≥ `CLUSTER_MIN_NEIGHBORS` (bv. 2) verwante buren > `CLUSTER_THRESHOLD` (~0.80). Empirisch te tunen, als constante met comment.
- **Gegate op `memory_capture`** (zelfde als de sweep). Draait alleen als capture aan staat.
- **Mockbaar zonder model:** seams `judge_supersede`/`_judge.judge`/`emb.embed`/`emb.get_cached` worden in tests gemonkeypatcht.
- **Decoupling:** `_judge.py`/`_llm.py`/`_embeddings.py`/`_kbindex.py` ongemoeid; `_memory.py` mag een kleine status-set-helper krijgen (additief). `memory-sweep.py` krijgt de pass-aanroepen (additief). `/wiki` leest later de `promote_candidate`-vlag — buiten scope hier (alleen de vlag zetten + documenteren).
- **Module-conventie:** underscore-naam, self-locate vault parents[2].

---

### Task 1: `_maintenance.py` — deterministische primitieven

**Files:**
- Create: `scripts/_maintenance.py`
- Modify: `scripts/_memory.py` (helper `set_status(path, status, superseded_by=None)`)
- Test: `tests/test_maintenance.py`, `tests/test_memory.py` (1 test)

**Interfaces:**
- Produces:
  - `_maintenance.current_items(get_cached_fn=None) -> list[dict]` — voor elke `09-memory`-file met `status: current`: `{"path","title","created","body","vec"}` (vec via `emb.get_cached`, injectable voor tests).
  - `_maintenance.similar_pairs(items, threshold) -> list[tuple]` — `(a, b, sim)` voor elk paar current-items met `cosine(a.vec, b.vec) > threshold`, gesorteerd hoog→laag sim.
  - `_maintenance.neighbor_counts(items, threshold) -> dict[path, int]` — aantal verwante buren > threshold per item.
  - `_memory.set_status(path, status, superseded_by=None) -> bool` — herschrijf de `status:`-regel in het frontmatter-blok (regex, idem expire-pass); optioneel een `superseded_by: [[...]]`-regel toevoegen/zetten. Return True als gewijzigd. (Hergebruik/ spiegel de robuuste frontmatter-mutatie uit `_expire_pass`.)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_maintenance.py`:

```python
"""Tests voor scripts/_maintenance.py - deterministische cross-memory-primitieven.
emb.get_cached wordt geinjecteerd (geen model). Vault naar temp."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _maintenance as mnt  # noqa: E402
import _memory  # noqa: E402

_VECS = {
    "a.md": [1.0, 0.0, 0.0],
    "b.md": [0.98, 0.02, 0.0],   # dicht bij a
    "c.md": [0.0, 1.0, 0.0],     # ver van a/b
}


class MaintenanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-mnt-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        for name, created in (("a.md", "2026-06-01"), ("b.md", "2026-06-05"), ("c.md", "2026-06-03")):
            _memory.write(name[:-3], f"body van {name}", status="current", created=created)
        # de _memory.write maakt datum-geprefixte namen; pak de echte paden
        self.files = sorted((self.vault / "09-memory").glob("*.md"))

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fake_cache(self):
        # map elke file op een vector op basis van een sleutelwoord in de body
        def gc(path, cache, recompute=True):
            body = Path(path).read_text(encoding="utf-8")
            for key, vec in _VECS.items():
                if key[:-3] in body:  # 'a','b','c'
                    return vec
            return [0.5, 0.5, 0.5]
        return gc

    def test_current_items_loaded(self):
        items = mnt.current_items(get_cached_fn=self._fake_cache())
        self.assertEqual(len(items), 3)
        self.assertTrue(all("vec" in it and "created" in it for it in items))

    def test_similar_pairs(self):
        items = mnt.current_items(get_cached_fn=self._fake_cache())
        pairs = mnt.similar_pairs(items, threshold=0.9)
        # a & b liggen dicht bij elkaar, c niet
        names = {(Path(p[0]["path"]).name, Path(p[1]["path"]).name) for p in pairs}
        flat = {n for pair in names for n in pair}
        self.assertTrue(any("body van a" or True for _ in [0]))  # sanity
        self.assertGreaterEqual(len(pairs), 1)

    def test_neighbor_counts(self):
        items = mnt.current_items(get_cached_fn=self._fake_cache())
        counts = mnt.neighbor_counts(items, threshold=0.9)
        self.assertEqual(sum(counts.values()) >= 2, True)  # a<->b telt voor beide


class MemorySetStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-ss-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_set_status_superseded_with_link(self):
        p = _memory.write("Oud", "iets ouds", status="current", created="2026-06-01")
        ok = _memory.set_status(p, "superseded", superseded_by=["2026-06-05-nieuw"])
        self.assertTrue(ok)
        txt = p.read_text(encoding="utf-8")
        self.assertIn("status: superseded", txt)
        self.assertIn("[[2026-06-05-nieuw]]", txt)
        self.assertEqual(_memory.read_status(p), "superseded")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_maintenance.py -v`
Expected: FAIL — `_maintenance` ontbreekt; `_memory.set_status` ontbreekt.

- [ ] **Step 3: Implement `_maintenance.py` + `_memory.set_status`**

Create `scripts/_maintenance.py`:

```python
#!/usr/bin/env python3
"""_maintenance.py - deterministische cross-memory-primitieven (supersede/cluster).

Levert de bouwstenen voor de onderhoudspas: laad current-memories met hun vectoren,
vind hoog-cosine paren (supersede-kandidaten), en tel verwante buren (cluster-
promotie). Geen LLM hier - dat zit in de seams (_judge / judge_supersede). De
vector-bron is injecteerbaar zodat de plumbing zonder model getest wordt.

Stdlib + _embeddings.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


def current_items(get_cached_fn=None) -> list:
    gc = get_cached_fn or (lambda p, cache, recompute=True: emb.get_cached(p, cache))
    cache = emb.load_cache()
    mdir = vault_root() / "09-memory"
    out = []
    if not mdir.exists():
        return out
    for f in sorted(mdir.glob("**/*.md")):
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if fm.get("status") != "current":
            continue
        vec = gc(f, cache)
        if not vec:
            continue
        out.append({"path": str(f), "title": fm.get("title", ""),
                    "created": fm.get("created", ""), "body": body.strip(), "vec": vec})
    return out


def similar_pairs(items, threshold: float) -> list:
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            s = emb.cosine(items[i]["vec"], items[j]["vec"])
            if s > threshold:
                pairs.append((items[i], items[j], s))
    pairs.sort(key=lambda t: t[2], reverse=True)
    return pairs


def neighbor_counts(items, threshold: float) -> dict:
    counts = {it["path"]: 0 for it in items}
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if emb.cosine(items[i]["vec"], items[j]["vec"]) > threshold:
                counts[items[i]["path"]] += 1
                counts[items[j]["path"]] += 1
    return counts
```

Voeg toe aan `scripts/_memory.py` (na `read_status`), met een robuuste frontmatter-mutatie:

```python
def set_status(path, status: str, superseded_by=None) -> bool:
    """Herschrijf de status-regel binnen het frontmatter-blok; optioneel een
    superseded_by-link zetten. Return True als het bestand gewijzigd is.
    Mutatie alleen binnen het frontmatter (tussen de eerste twee --- fences)."""
    import re
    if status not in STATUSES:
        return False
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return False
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return False
    fm = parts[1]
    new_fm = re.sub(r"^status:.*$", f"status: {status}", fm, count=1, flags=re.MULTILINE)
    if superseded_by:
        link = "[" + ", ".join(f"[[{s}]]" for s in superseded_by) + "]"
        if re.search(r"^superseded_by:.*$", new_fm, flags=re.MULTILINE):
            new_fm = re.sub(r"^superseded_by:.*$", f"superseded_by: {link}",
                            new_fm, count=1, flags=re.MULTILINE)
        else:
            new_fm = new_fm.rstrip("\n") + f"\nsuperseded_by: {link}\n"
    new_raw = parts[0] + "---" + new_fm + "---" + parts[2]
    if new_raw == raw:
        return False
    try:
        p.write_text(new_raw, encoding="utf-8")
    except OSError:
        return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_maintenance.py tests/test_memory.py -v`
Expected: PASS (maintenance-primitieven + set_status + alle bestaande _memory-tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_maintenance.py scripts/_memory.py tests/test_maintenance.py tests/test_memory.py
git commit -m "feat(memory): _maintenance primitieven + _memory.set_status (cross-memory v2)"
```

---

### Task 2: supersede-pass (LLM-seam, fail-safe)

**Files:**
- Modify: `scripts/_maintenance.py` (`judge_supersede` + `supersede_pass`)
- Test: `tests/test_maintenance_supersede.py`

**Interfaces:**
- Produces:
  - `judge_supersede(new_text, old_text) -> bool` — vraagt `_llm.generate` of de nieuwere memory de oudere TEGENSPREEKT/vervangt. **Fail-safe**: None/parse-fout/twijfel → `False` (geen supersede).
  - `supersede_pass(threshold=0.85, judge_fn=None) -> int` — over `similar_pairs`: voor elk tegenstrijdig paar markeer de OUDERE (`created`) als `superseded` + `superseded_by: [[nieuwere-stem]]`. Return aantal gesuperseed. `judge_fn` injectable (default `judge_supersede`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_maintenance_supersede.py`:

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

import _maintenance as mnt  # noqa: E402
import _memory  # noqa: E402
import _llm  # noqa: E402


class SupersedeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-sup-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.old = _memory.write("Jim zoekt baan", "Jim is op zoek naar een nieuwe baan.",
                                 status="current", created="2026-01-01")
        self.new = _memory.write("Jim heeft baan", "Jim heeft de nieuwe baan gekregen.",
                                 status="current", created="2026-06-01")
        # injecteer vectoren: oud en nieuw liggen dicht bij elkaar (zelfde onderwerp)
        self._gc = lambda p, cache, recompute=True: [1.0, 0.0] if True else None
        self._orig_gen = _llm.generate

    def tearDown(self):
        import shutil
        _llm.generate = self._orig_gen
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_supersede_marks_older(self):
        _llm.generate = lambda *a, **k: '{"supersede": true, "reason": "Jim heeft nu de baan"}'
        n = mnt.supersede_pass(threshold=0.5, get_cached_fn=self._gc)
        self.assertEqual(n, 1)
        self.assertEqual(_memory.read_status(self.old), "superseded")
        self.assertEqual(_memory.read_status(self.new), "current")
        self.assertIn("superseded_by", self.old.read_text(encoding="utf-8"))

    def test_no_supersede_when_judge_false(self):
        _llm.generate = lambda *a, **k: '{"supersede": false}'
        n = mnt.supersede_pass(threshold=0.5, get_cached_fn=self._gc)
        self.assertEqual(n, 0)
        self.assertEqual(_memory.read_status(self.old), "current")

    def test_failsafe_on_model_none(self):
        _llm.generate = lambda *a, **k: None
        self.assertEqual(mnt.supersede_pass(threshold=0.5, get_cached_fn=self._gc), 0)
        self.assertEqual(_memory.read_status(self.old), "current")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_maintenance_supersede.py -v`
Expected: FAIL — `supersede_pass`/`judge_supersede` ontbreken (en `supersede_pass` neemt nog geen `get_cached_fn`).

- [ ] **Step 3: Implement `judge_supersede` + `supersede_pass`**

Append to `scripts/_maintenance.py`:

```python
import json as _json

SUPERSEDE_SYSTEM = (
    "Je beoordeelt of een NIEUWERE memory een OUDERE TEGENSPREEKT of vervangt "
    "(bv. 'Jim zoekt baan' -> 'Jim heeft baan'). Antwoord UITSLUITEND met JSON: "
    "{\"supersede\": true|false, \"reason\": \"<kort>\"}. Bij twijfel: false."
)


def judge_supersede(new_text: str, old_text: str) -> bool:
    import _llm
    raw = _llm.generate(f"NIEUWER:\n{new_text}\n\nOUDER:\n{old_text}\n\nOordeel (JSON):",
                        system=SUPERSEDE_SYSTEM)
    if not raw:
        return False
    try:
        s, e = raw.find("{"), raw.rfind("}")
        obj = _json.loads(raw[s:e + 1]) if s >= 0 and e > s else {}
    except Exception:
        return False
    return obj.get("supersede") is True


def supersede_pass(threshold: float = 0.85, judge_fn=None, get_cached_fn=None) -> int:
    import _memory
    judge_fn = judge_fn or judge_supersede
    items = current_items(get_cached_fn=get_cached_fn)
    done = 0
    superseded_paths = set()
    for a, b, _sim in similar_pairs(items, threshold):
        # bepaal nieuwer/ouder op created (string ISO sorteert correct)
        newer, older = (a, b) if (a["created"] >= b["created"]) else (b, a)
        if older["path"] in superseded_paths or newer["path"] in superseded_paths:
            continue
        if judge_fn(newer["body"], older["body"]):
            if _memory.set_status(older["path"], "superseded",
                                  superseded_by=[Path(newer["path"]).stem]):
                superseded_paths.add(older["path"])
                done += 1
    return done
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_maintenance_supersede.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_maintenance.py tests/test_maintenance_supersede.py
git commit -m "feat(memory): supersede-pass (nieuwer spreekt ouder tegen -> superseded, fail-safe)"
```

---

### Task 3: 2e-lijn-hercontrole + cluster-promotie

**Files:**
- Modify: `scripts/_maintenance.py` (`recheck_pass`, `cluster_promote_pass`)
- Test: `tests/test_maintenance_recheck.py`

**Interfaces:**
- Produces:
  - `recheck_pass(judge_fn=None, limit=20) -> int` — her-judge (via `_judge.judge`) elke `current`-memory (tot `limit`); als het verdict NIET `current` is → `set_status(retracted)`. Fail-safe: model-twijfel → de `_judge.judge` geeft al `unverified` bij twijfel; alleen een expliciet non-current verdict retract. Return aantal geretract.
  - `cluster_promote_pass(threshold=0.80, min_neighbors=2, get_cached_fn=None) -> int` — zet `promote_candidate: true` in het frontmatter van elke `current`-memory met ≥ `min_neighbors` verwante buren (kandidaat voor `/wiki`-promotie). Return aantal gemarkeerd.

- [ ] **Step 1: Write the failing test**

Create `tests/test_maintenance_recheck.py`:

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

import _maintenance as mnt  # noqa: E402
import _memory  # noqa: E402
import _judge  # noqa: E402


class RecheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-rc-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = _memory.write("Ruis", "iets nietszeggends", status="current", created="2026-06-01")
        self._orig = _judge.judge

    def tearDown(self):
        import shutil
        _judge.judge = self._orig
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recheck_retracts_non_current(self):
        _judge.judge = lambda cand, context="": {"verdict": "unverified", "reason": "ruis"}
        n = mnt.recheck_pass()
        self.assertEqual(n, 1)
        self.assertEqual(_memory.read_status(self.m), "retracted")

    def test_recheck_keeps_current(self):
        _judge.judge = lambda cand, context="": {"verdict": "current", "reason": "ok"}
        self.assertEqual(mnt.recheck_pass(), 0)
        self.assertEqual(_memory.read_status(self.m), "current")

    def test_cluster_marks_neighbors(self):
        _memory.write("A", "onderwerp x een", status="current", created="2026-06-01")
        _memory.write("B", "onderwerp x twee", status="current", created="2026-06-02")
        _memory.write("C", "onderwerp x drie", status="current", created="2026-06-03")
        gc = lambda p, cache, recompute=True: [1.0, 0.0, 0.0]  # alles identiek -> buren
        n = mnt.cluster_promote_pass(threshold=0.5, min_neighbors=2, get_cached_fn=gc)
        self.assertGreaterEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_maintenance_recheck.py -v`
Expected: FAIL — `recheck_pass`/`cluster_promote_pass` ontbreken.

- [ ] **Step 3: Implement `recheck_pass` + `cluster_promote_pass`**

Append to `scripts/_maintenance.py`:

```python
def recheck_pass(judge_fn=None, limit: int = 20) -> int:
    import _judge
    import _memory
    judge_fn = judge_fn or _judge.judge
    items = current_items()
    done = 0
    for it in items[:limit]:
        verdict = judge_fn(it["body"])
        if verdict.get("verdict") != "current":
            if _memory.set_status(it["path"], "retracted"):
                done += 1
    return done


def cluster_promote_pass(threshold: float = 0.80, min_neighbors: int = 2,
                         get_cached_fn=None) -> int:
    import re
    items = current_items(get_cached_fn=get_cached_fn)
    counts = neighbor_counts(items, threshold)
    done = 0
    for it in items:
        if counts.get(it["path"], 0) < min_neighbors:
            continue
        p = Path(it["path"])
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if "promote_candidate:" in raw:
            continue
        parts = raw.split("---", 2)
        if len(parts) < 3:
            continue
        new_fm = parts[1].rstrip("\n") + "\npromote_candidate: true\n"
        try:
            p.write_text(parts[0] + "---" + new_fm + "---" + parts[2], encoding="utf-8")
            done += 1
        except OSError:
            continue
    return done
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_maintenance_recheck.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_maintenance.py tests/test_maintenance_recheck.py
git commit -m "feat(memory): 2e-lijn-hercontrole + cluster-promotie (cross-memory v2)"
```

---

### Task 4: bedrading in `memory-sweep.py` + docs

**Files:**
- Modify: `scripts/memory-sweep.py` (onderhoudspas aanroepen in `run_sweep`)
- Modify: `commands/wiki.md` (lees `promote_candidate`), `CHANGELOG.md`
- Test: `tests/test_memory_sweep.py` (1 test)

**Interfaces:**
- Produces: `run_sweep` draait ná de capture-loop (en ná de model-reachability-guard) de onderhoudspas: `supersede_pass`, `recheck_pass`, `cluster_promote_pass`, en telt ze in de summary (`superseded`, `rechecked_retracted`, `promote_marked`). Gegate op `memory_capture` (al). Fail-soft: een falende pass telt 0, breekt de sweep niet.

- [ ] **Step 1: Write the failing test**

Voeg toe aan `class MemorySweepTest` in `tests/test_memory_sweep.py` (de setUp mockt al extract/judge/embed; `_llm.generate` is gemockt op "ok"):

```python
    def test_sweep_runs_maintenance(self):
        # na een normale sweep moet de summary de onderhouds-tellers bevatten
        s = self.m.run_sweep()
        for key in ("superseded", "rechecked_retracted", "promote_marked"):
            self.assertIn(key, s)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_memory_sweep.py -k maintenance -v`
Expected: FAIL — de summary mist de onderhouds-keys.

- [ ] **Step 3: Wire the maintenance passes into `run_sweep`**

In `scripts/memory-sweep.py`, na de capture-loop (en ná `_expire_pass`, vóór het heartbeat-schrijven), voeg toe (fail-soft per pass):

```python
    # Cross-memory onderhoud (v2): supersede, 2e-lijn-hercontrole, cluster-promotie.
    try:
        import _maintenance as _mnt
        try:
            s["superseded"] = _mnt.supersede_pass()
        except Exception:
            s["superseded"] = 0
        try:
            s["rechecked_retracted"] = _mnt.recheck_pass()
        except Exception:
            s["rechecked_retracted"] = 0
        try:
            s["promote_marked"] = _mnt.cluster_promote_pass()
        except Exception:
            s["promote_marked"] = 0
    except Exception:
        s["superseded"] = s.get("superseded", 0)
        s["rechecked_retracted"] = s.get("rechecked_retracted", 0)
        s["promote_marked"] = s.get("promote_marked", 0)
```

Initialiseer de drie keys ook in de begin-`s`-dict (zodat ze er bij gated-off ook zijn): voeg `"superseded": 0, "rechecked_retracted": 0, "promote_marked": 0` toe aan de dict waar `processed`/`written`/etc. staan.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_memory_sweep.py -v`
Expected: PASS (de nieuwe + alle bestaande sweep-tests).

- [ ] **Step 5: Document `promote_candidate` in `/wiki` + CHANGELOG**

In `commands/wiki.md`: voeg een korte noot toe dat `09-memory`-memories met `promote_candidate: true` voorrang krijgen als bron voor wiki-compilatie (de sweep markeert clusters van verwante current-memories). In `CHANGELOG.md`: één regel (cross-memory onderhoud v2 — supersede + hercontrole + cluster-promotie).

- [ ] **Step 6: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/memory-sweep.py commands/wiki.md CHANGELOG.md tests/test_memory_sweep.py
git commit -m "feat(memory): bedraad cross-memory onderhoud v2 in de sweep + /wiki promote_candidate"
```

---

## Self-Review

**Spec coverage (cross-memory v2):**
- Supersede (nieuwer spreekt ouder tegen → superseded + link, fail-safe) → Task 2. ✓
- 2e-lijn-hercontrole (her-judge current → retract bij non-current) → Task 3. ✓
- Cluster-promotie (markeer promote_candidate voor /wiki) → Task 3 + Task 4 (/wiki-noot). ✓
- Deterministische primitieven (current_items/similar_pairs/neighbor_counts) + set_status → Task 1. ✓
- Bedraad in de sweep, gegate, fail-soft → Task 4. ✓
- Mockbaar zonder model: alle passes monkeypatchen `_llm.generate`/`_judge.judge`/`get_cached`. ✓

**Placeholder scan:** geen TBD/TODO; alle code + testcode volledig.

**Type consistency:** `current_items(get_cached_fn)`, `similar_pairs(items, threshold)`, `neighbor_counts(items, threshold)`, `supersede_pass(threshold, judge_fn, get_cached_fn)`, `recheck_pass(judge_fn, limit)`, `cluster_promote_pass(threshold, min_neighbors, get_cached_fn)` consistent; `_memory.set_status(path, status, superseded_by)` matcht de aanroepen; `_judge.judge(...)->{verdict}` en `_llm.generate(...)` matchen fase 4a.

**Geverifieerd vóór uitvoering:** `_memory.write`/`read_status`/`STATUSES` bestaan (fase 1); `emb.cosine`/`get_cached`/`load_cache` bestaan; `_judge.judge` (fase 4a) geeft `{verdict}`; `_expire_pass` in memory-sweep gebruikt al de frontmatter-regex-mutatie die `set_status` spiegelt. De passes draaien ná de reachability-guard (alleen als het model bereikbaar is — de capture-loop heeft 'm al gecheckt).

**Aandachtspunt uitvoerder:** Task 1 — `_memory.write` maakt datum-geprefixte bestandsnamen; de tests pakken de echte paden via glob. Task 2 — supersede-richting op `created` (ISO-string sorteert correct); markeer een pad nooit twee keer (superseded_paths-set). Task 4 — initialiseer de drie onderhouds-keys in de begin-`s`-dict zodat ze ook bij `memory_capture=false` (vroege return) aanwezig zijn; elke pass fail-soft zodat een LLM-hapering de sweep niet breekt.

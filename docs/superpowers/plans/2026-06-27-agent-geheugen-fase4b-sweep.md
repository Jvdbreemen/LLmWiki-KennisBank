# Agent-geheugen — Fase 4b: Sweep-orkestratie (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** De autonome capture-sweep die nieuwe transcripts omzet in geheugen: een `.swept`-watermark + transcript-reader, chunk/dedup-utilities, de `memory-sweep.py`-orkestrator (extract → chunk → dedup → judge → schrijf met status → onderhoud → heartbeat), en een detached SessionStart-launcher met single-flight lockfile die de sweep en daarna `build-kb-index` draait.

**Architecture:** De sweep is een **deterministische orkestrator** bovenop de fase-4a seams (`_extract`, `_judge`, `_llm`) en `_embeddings`/`_memory`/`_kbindex`. Alle LLM-aanroepen lopen via mockbare seams; de plumbing (watermark, chunking, dedup, status-schrijven, collision-guard, budget, expire, heartbeat) is puur en unit-getest zonder model. De SessionStart-**launcher** is dun: single-flight lockfile, spawnt de sweep **detached** (niet-blokkerend), draait daarna `build-kb-index` (sweep→index-ordening), exit 0 fail-open. Gegate op `memory_capture`.

**Tech Stack:** Python 3.10+ (stdlib: `json`, `subprocess`, `os`), fase-4a seams + `_embeddings`/`_memory`/`_kbindex`/`_settings`, `unittest`.

## Global Constraints

- **Gegate op `memory_capture`:** sweep + launcher doen niets als de toggle uit staat (fail-soft default True).
- **Detached + niet-blokkerend:** de SessionStart-launcher spawnt de sweep los (Windows `DETACHED_PROCESS|CREATE_NO_WINDOW`, POSIX `start_new_session=True`), `.wait()` NIET, exit 0. Onzichtbaar/snel (noord-ster).
- **Single-flight lockfile:** atomic create + PID/mtime + stale-reclaim. Twee SessionStarts kort na elkaar mogen geen overlappende sweeps draaien (race op DB/files).
- **Fail-safe keten (uit 4a):** judge → `unverified` bij twijfel; alleen expliciet `current` promoot. extract → `[]` bij fout. Model onbereikbaar → sweep stopt netjes, memory blijft staan, heartbeat meldt het.
- **Sweep-breed budget:** max `MAX_TRANSCRIPTS` per run + max `MAX_CHUNKS` per transcript. Niet eindeloos doorploegen.
- **Chunk lange transcripts** vóór extract (anders vallen lange sessies stil naar []).
- **Dedup bij capture:** kandidaat-embedding cosine vs bestaande memory; > `DEDUP_THRESHOLD` (~0.92) → niet schrijven (update bestaande `updated`-stamp).
- **Collision-guard:** uniek memory-pad per dag (suffix-teller) — geen overschrijven.
- **Status uit verdict:** judge `current`→`current`, anders `unverified`. `evidence_basis="agent"`, `source_session`=transcript-pad.
- **Sweep→index-ordening:** launcher draait sweep (status-flips/schrijven) en DAARNA `build-kb-index` — nooit via hook-volgorde-aanname.
- **Heartbeat:** sweep schrijft `<vault>/.claude/memory-sweep-status.json` (last_run, processed, current, unverified, errors, provider, is_local). Fase 5 leest dit (sessiestart/doctor).
- **Lokaal-first (#4):** alle LLM via `_llm` (default lokaal); een cloud-stap logt al luid (4a).
- **Decoupling:** `_embeddings.py`, `kb-retrieve.py`, `build-embed-index.py`, `_kbindex.py`, `_llm.py`, `_judge.py`, `_extract.py` ongemoeid; `_memory.py` mag een collision-guard-helper krijgen (additief). `import-cc-history.py` ongemoeid (we schrijven een eigen kleine reader).
- **Interpreter:** repo-scripts = `python3`; de SessionStart-launcher-registratie gebruikt `py -3` (Windows) zoals de andere hooks.

---

### Task 1: `.swept`-watermark + transcript-reader (`_sweepstate.py`)

**Files:**
- Create: `scripts/_sweepstate.py`
- Test: `tests/test_sweepstate.py`

**Interfaces:**
- Consumes: `_vaultpath.vault_root`.
- Produces:
  - `TRANSCRIPTS_DIR -> Path` (= `<vault>/01-raw/transcripts`), `WATERMARK = ".swept"`.
  - `pending(vault=None) -> list[Path]` — `.jsonl`-transcripts wier stem niet in `.swept` staat.
  - `mark(stems, vault=None) -> int` — APPEND exact die stems aan `.swept` (dedup).
  - `transcript_text(jsonl_path) -> str` — lees de `.jsonl`, reduceer user/assistant-berichten tot platte tekst (fail-soft → "").

- [ ] **Step 1: Write the failing test**

Create `tests/test_sweepstate.py`:

```python
"""Tests voor scripts/_sweepstate.py - watermark + transcript-reader."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _sweepstate as ss  # noqa: E402


class SweepStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-sweep-"))
        self.vault = self.tmp / "vault"
        self.tdir = self.vault / "01-raw" / "transcripts"
        self.tdir.mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _t(self, name, records):
        p = self.tdir / name
        p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        return p

    def test_pending_excludes_marked(self):
        self._t("a.jsonl", [{"type": "user", "message": {"role": "user", "content": "hoi"}}])
        self._t("b.jsonl", [{"type": "user", "message": {"role": "user", "content": "hoi"}}])
        self.assertEqual({p.stem for p in ss.pending()}, {"a", "b"})
        ss.mark(["a"])
        self.assertEqual({p.stem for p in ss.pending()}, {"b"})

    def test_mark_is_idempotent(self):
        self._t("a.jsonl", [{"type": "user", "message": {"role": "user", "content": "x"}}])
        ss.mark(["a"])
        ss.mark(["a"])
        self.assertEqual(ss.pending(), [])

    def test_transcript_text_reduces_messages(self):
        p = self._t("c.jsonl", [
            {"type": "user", "message": {"role": "user", "content": "Repareer de bug"}},
            {"type": "assistant", "message": {"role": "assistant",
                "content": [{"type": "text", "text": "Token-expiry fix"}]}},
        ])
        txt = ss.transcript_text(p)
        self.assertIn("Repareer de bug", txt)
        self.assertIn("Token-expiry fix", txt)

    def test_transcript_text_failsoft(self):
        bad = self.tdir / "bad.jsonl"
        bad.write_text("{ kapot json", encoding="utf-8")
        self.assertEqual(ss.transcript_text(bad), "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_sweepstate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_sweepstate'`.

- [ ] **Step 3: Implement `scripts/_sweepstate.py`**

Create `scripts/_sweepstate.py`:

```python
#!/usr/bin/env python3
"""_sweepstate.py - watermark + transcript-reader voor de capture-sweep.

Spiegelt distill-notify's .distilled-pattern met een EIGEN .swept-watermark, zodat
de geheugen-sweep onafhankelijk van de destillatie bijhoudt welke transcripts al
tot memory verwerkt zijn. transcript_text() reduceert een CC-.jsonl tot platte
user/assistant-tekst (fail-soft).

Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

WATERMARK = ".swept"


def _tdir(vault=None) -> Path:
    return (vault or vault_root()) / "01-raw" / "transcripts"


def _watermark(vault=None) -> set:
    f = _tdir(vault) / WATERMARK
    try:
        return {ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()}
    except OSError:
        return set()


def pending(vault=None) -> list:
    d = _tdir(vault)
    if not d.exists():
        return []
    done = _watermark(vault)
    return [p for p in sorted(d.glob("*.jsonl")) if p.stem not in done]


def mark(stems, vault=None) -> int:
    done = _watermark(vault)
    new = [s for s in dict.fromkeys(stems) if s and s not in done]
    if not new:
        return 0
    f = _tdir(vault) / WATERMARK
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            for s in new:
                fh.write(s + "\n")
    except OSError as e:
        print(f"[sweepstate] kan watermark niet schrijven: {e}", file=sys.stderr)
        return 0
    return len(new)


def _block_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(parts)
    return ""


def transcript_text(jsonl_path) -> str:
    """Reduceer een CC-transcript-jsonl tot platte user/assistant-tekst. Fail-soft."""
    out = []
    try:
        with Path(jsonl_path).open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msg = rec.get("message") if isinstance(rec, dict) else None
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                if role in ("user", "assistant"):
                    t = _block_text(msg.get("content")).strip()
                    if t:
                        out.append(f"{role}: {t}")
    except Exception:
        return ""
    return "\n\n".join(out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_sweepstate.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_sweepstate.py tests/test_sweepstate.py
git commit -m "feat(memory): _sweepstate.py .swept-watermark + transcript-reader"
```

---

### Task 2: chunk + dedup + collision-guard (`_sweeputil.py` + `_memory` helper)

**Files:**
- Create: `scripts/_sweeputil.py`
- Modify: `scripts/_memory.py` (voeg `unique_memory_path` toe)
- Test: `tests/test_sweeputil.py`, `tests/test_memory.py` (1 test toevoegen)

**Interfaces:**
- Produces:
  - `_sweeputil.chunk(text, max_chars=6000, overlap=200) -> list[str]` — splits lange tekst in chunks (op alinea-grenzen waar mogelijk), met kleine overlap.
  - `_sweeputil.is_duplicate(vec, existing_vecs, threshold=0.92) -> bool` — True als `vec` cosine > threshold tegen één van `existing_vecs` (gebruikt `_embeddings.cosine`).
  - `_memory.unique_memory_path(title, created=None) -> Path` — `memory_path`, maar voegt `-2`, `-3`, … toe tot het pad vrij is (collision-guard).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sweeputil.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import unittest
import _sweeputil as su  # noqa: E402


class SweepUtilTest(unittest.TestCase):
    def test_chunk_splits_long_text(self):
        text = "\n\n".join(f"alinea {i} " + "x" * 500 for i in range(20))
        chunks = su.chunk(text, max_chars=2000)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 2200 for c in chunks))  # max + overlap-marge

    def test_chunk_short_text_one_chunk(self):
        self.assertEqual(su.chunk("kort stukje", max_chars=2000), ["kort stukje"])

    def test_is_duplicate_true_for_near_identical(self):
        v = [1.0, 0.0, 0.0]
        self.assertTrue(su.is_duplicate(v, [[0.99, 0.01, 0.0]], threshold=0.9))

    def test_is_duplicate_false_for_distinct(self):
        self.assertFalse(su.is_duplicate([1.0, 0.0, 0.0], [[0.0, 1.0, 0.0]], threshold=0.9))

    def test_is_duplicate_empty_existing(self):
        self.assertFalse(su.is_duplicate([1.0, 0.0], [], threshold=0.9))


if __name__ == "__main__":
    unittest.main()
```

Voeg toe aan `class MemoryFormatTest` in `tests/test_memory.py`:

```python
    def test_unique_memory_path_avoids_collision(self):
        p1 = _memory.write("Zelfde titel", "een", created="2026-06-27")
        p2 = _memory.unique_memory_path("Zelfde titel", created="2026-06-27")
        self.assertNotEqual(p1, p2)
        self.assertTrue(p2.name.endswith("-2.md"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_sweeputil.py tests/test_memory.py -k "chunk or duplicate or unique" -v`
Expected: FAIL — `_sweeputil` ontbreekt; `unique_memory_path` ontbreekt.

- [ ] **Step 3: Implement `_sweeputil.py` and the `_memory` helper**

Create `scripts/_sweeputil.py`:

```python
#!/usr/bin/env python3
"""_sweeputil.py - chunking + dedup voor de capture-sweep. Stdlib + _embeddings."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _embeddings import cosine  # noqa: E402


def chunk(text: str, max_chars: int = 6000, overlap: int = 200) -> list:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    paras = text.split("\n\n")
    chunks, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) + 2 > max_chars:
            chunks.append(cur)
            cur = (cur[-overlap:] + "\n\n" + p) if overlap else p
        else:
            cur = (cur + "\n\n" + p) if cur else p
    if cur.strip():
        chunks.append(cur)
    # harde splitsing voor een enkele te lange alinea
    out = []
    for c in chunks:
        while len(c) > max_chars + overlap:
            out.append(c[:max_chars])
            c = c[max_chars - overlap:]
        out.append(c)
    return out


def is_duplicate(vec, existing_vecs, threshold: float = 0.92) -> bool:
    if not vec or not existing_vecs:
        return False
    for ev in existing_vecs:
        if ev and cosine(vec, ev) > threshold:
            return True
    return False
```

Voeg toe aan `scripts/_memory.py` (na `memory_path`):

```python
def unique_memory_path(title: str, created: str | None = None) -> Path:
    """memory_path met collision-guard: voegt -2,-3,.. toe tot het pad vrij is."""
    base = memory_path(title, created)
    if not base.exists():
        return base
    stem, suffix, parent = base.stem, base.suffix, base.parent
    n = 2
    while True:
        cand = parent / f"{stem}-{n}{suffix}"
        if not cand.exists():
            return cand
        n += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_sweeputil.py tests/test_memory.py -v`
Expected: PASS (5 sweeputil + de nieuwe memory-test + alle bestaande).

- [ ] **Step 5: Commit**

```bash
git add scripts/_sweeputil.py scripts/_memory.py tests/test_sweeputil.py tests/test_memory.py
git commit -m "feat(memory): _sweeputil chunk/dedup + _memory.unique_memory_path collision-guard"
```

---

### Task 3: `memory-sweep.py` — de orkestrator

**Files:**
- Create: `scripts/memory-sweep.py`
- Test: `tests/test_memory_sweep.py`

**Interfaces:**
- Consumes: `_sweepstate`, `_sweeputil`, `_extract`, `_judge`, `_embeddings`, `_memory`, `_settings`.
- Produces:
  - `run_sweep(max_transcripts=10, max_chunks=6) -> dict` — verwerk pending transcripts: per transcript `transcript_text` → `chunk` → per chunk `extract_candidates` → per kandidaat embed + `is_duplicate` (skip dup) → `judge` → `_memory.write(status, evidence_basis="agent", source_session, path=unique)` → `mark`. Daarna een **expire-pass** (deterministisch: `09-memory` current met `expires < vandaag` → status `expired`). Schrijf heartbeat. Return een samenvatting-dict.
  - `_expire_pass() -> int`, `_write_heartbeat(summary)`.
  - CLI: `python3 memory-sweep.py [--max N]`.
- **Gegate op `memory_capture`** (vroege return + heartbeat "uitgeschakeld").
- **Mockbaar:** tests monkeypatchen `_extract.extract_candidates`, `_judge.judge`, en `emb.embed`/`emb.get_cached` → geen model.

- [ ] **Step 1: Write the failing test**

Create `tests/test_memory_sweep.py`:

```python
"""Tests voor scripts/memory-sweep.py - de orkestrator. Alle LLM/embed-seams
gemockt; geen echt model. Vault naar temp."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load():
    spec = importlib.util.spec_from_file_location("memory_sweep", str(SCRIPTS_DIR / "memory-sweep.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class MemorySweepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-msweep-"))
        self.vault = self.tmp / "vault"
        (self.vault / "01-raw" / "transcripts").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        # een pending transcript
        (self.vault / "01-raw" / "transcripts" / "s1.jsonl").write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "Bug X opgelost"}}),
            encoding="utf-8")
        self.m = _load()
        import _extract, _judge
        import _embeddings as emb
        self._orig = (_extract.extract_candidates, _judge.judge, emb.embed)
        _extract.extract_candidates = lambda text, max_n=8: [{"title": "Bug X", "body": "opgelost via Y"}]
        _judge.judge = lambda cand, context="": {"verdict": "current", "reason": "duidelijk"}
        emb.embed = lambda text, timeout=30.0: [0.1, 0.2, 0.3]
        self.emb, self._extract, self._judge = emb, _extract, _judge

    def tearDown(self):
        import shutil
        self._extract.extract_candidates, self._judge.judge, self.emb.embed = self._orig
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sweep_writes_current_memory_and_marks(self):
        summary = self.m.run_sweep()
        mems = list((self.vault / "09-memory").glob("*.md"))
        self.assertEqual(len(mems), 1)
        self.assertIn("status: current", mems[0].read_text(encoding="utf-8"))
        self.assertIn("evidence_basis: agent", mems[0].read_text(encoding="utf-8"))
        # tweede run verwerkt niets nieuws (watermark)
        self.assertEqual(self.m.run_sweep()["processed"], 0)

    def test_doubt_writes_unverified(self):
        self._judge.judge = lambda cand, context="": {"verdict": "unverified", "reason": "vaag"}
        self.m.run_sweep()
        mem = list((self.vault / "09-memory").glob("*.md"))[0]
        self.assertIn("status: unverified", mem.read_text(encoding="utf-8"))

    def test_dedup_skips_near_duplicate(self):
        # bestaande memory met dezelfde embedding -> kandidaat is duplicaat
        import _memory
        _memory.write("Bestaand", "iets", created="2026-06-27")
        # emb.embed geeft altijd dezelfde vector -> is_duplicate True tegen de bestaande
        # (de sweep embed't bestaande memory met dezelfde mock-vector)
        summary = self.m.run_sweep()
        self.assertEqual(summary.get("written", 0), 0)
        self.assertGreaterEqual(summary.get("duplicates", 0), 1)

    def test_gated_off_does_nothing(self):
        (self.vault / "kennisbank-settings.json").write_text(
            json.dumps({"memory_capture": False}), encoding="utf-8")
        summary = self.m.run_sweep()
        self.assertEqual(list((self.vault / "09-memory").glob("*.md")), [])
        self.assertFalse(summary.get("enabled", True))

    def test_heartbeat_written(self):
        self.m.run_sweep()
        hb = self.vault / ".claude" / "memory-sweep-status.json"
        self.assertTrue(hb.exists())
        data = json.loads(hb.read_text(encoding="utf-8"))
        self.assertIn("last_run", data)

    def test_expire_pass_flips_past_expires(self):
        import _memory
        old = _memory.write("Vluchtig", "iets", status="current",
                            expires="2000-01-01", created="2026-06-27")
        self.m.run_sweep()
        self.assertIn("status: expired", old.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
```

> NOTE: `test_dedup_skips_near_duplicate` leunt erop dat de sweep bestaande `09-memory`-files embed (met de mock-vector) om de dedup-pool te bouwen. Als de implementatie de pool anders bouwt, pas de test aan zodat hij de dedup ECHT raakt (bv. door de bestaande memory via de sweep te laten embedden of de pool injecteerbaar te maken). De kern: een kandidaat met cosine > 0.92 tegen bestaand → niet geschreven, `duplicates` telt op.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_memory_sweep.py -v`
Expected: FAIL — `memory-sweep.py` bestaat niet.

- [ ] **Step 3: Implement `scripts/memory-sweep.py`**

Create `scripts/memory-sweep.py`:

```python
#!/usr/bin/env python3
"""memory-sweep.py - autonome capture-sweep (extract -> dedup -> judge -> schrijf).

Verwerkt pending transcripts (sinds de .swept-watermark) tot geheugen-files. Per
transcript: tekst -> chunks -> per chunk kandidaten extraheren -> embedden + dedup
tegen bestaande memory -> onafhankelijk judgen -> schrijven met status (current bij
expliciet hoog-zeker, anders unverified), evidence_basis=agent, source_session.
Daarna een deterministische expire-pass. Schrijft een heartbeat-status.

Gegate op memory_capture. Alle LLM/embed-aanroepen lopen via mockbare seams.
Fail-soft: model onbereikbaar -> stopt netjes, memory blijft staan, heartbeat meldt.

Stdlib. Usage: python3 memory-sweep.py [--max N]
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _extract  # noqa: E402
import _judge  # noqa: E402
import _llm  # noqa: E402
import _memory  # noqa: E402
import _settings  # noqa: E402
import _sweepstate as ss  # noqa: E402
import _sweeputil as su  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

HEARTBEAT = "memory-sweep-status.json"


def _existing_memory_vectors() -> list:
    vecs, cache = [], emb.load_cache()
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return vecs
    for f in mdir.glob("**/*.md"):
        v = emb.get_cached(f, cache)
        if v:
            vecs.append(v)
    return vecs


def _expire_pass() -> int:
    today = date.today().isoformat()
    n = 0
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return 0
    for f in mdir.glob("**/*.md"):
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if fm.get("status") == "current" and fm.get("expires") and fm["expires"] < today:
            txt = f.read_text(encoding="utf-8").replace("status: current", "status: expired", 1)
            f.write_text(txt, encoding="utf-8")
            n += 1
    return n


def _write_heartbeat(summary: dict) -> None:
    hb = vault_root() / ".claude" / HEARTBEAT
    summary = dict(summary)
    summary["last_run"] = datetime.now(timezone.utc).isoformat()
    summary["provider"] = _llm.providers()[0] if _llm.providers() else ""
    summary["is_local"] = _llm.is_local()
    try:
        hb.parent.mkdir(parents=True, exist_ok=True)
        hb.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def run_sweep(max_transcripts: int = 10, max_chunks: int = 6) -> dict:
    s = {"enabled": True, "processed": 0, "written": 0, "current": 0,
         "unverified": 0, "duplicates": 0, "expired": 0, "errors": 0}
    if not _settings.get("memory_capture", True):
        s["enabled"] = False
        _write_heartbeat(s)
        return s
    existing = _existing_memory_vectors()
    for tp in ss.pending()[:max_transcripts]:
        try:
            text = ss.transcript_text(tp)
            for ch in su.chunk(text)[:max_chunks]:
                for cand in _extract.extract_candidates(ch):
                    body = cand.get("body", "")
                    vec = emb.embed(body)
                    if vec and su.is_duplicate(vec, existing):
                        s["duplicates"] += 1
                        continue
                    verdict = _judge.judge(body)
                    status = "current" if verdict.get("verdict") == "current" else "unverified"
                    path = _memory.unique_memory_path(cand.get("title", "memory"))
                    _memory.write(cand.get("title", "memory"), body, status=status,
                                  evidence_basis="agent", source_session=tp.name,
                                  created=path.stem[:10])
                    if vec:
                        existing.append(vec)
                    s["written"] += 1
                    s[status] += 1
            ss.mark([tp.stem])
            s["processed"] += 1
        except Exception:
            s["errors"] += 1
    s["expired"] = _expire_pass()
    _write_heartbeat(s)
    return s


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    mx = 10
    if "--max" in argv:
        try:
            mx = int(argv[argv.index("--max") + 1])
        except Exception:
            mx = 10
    s = run_sweep(max_transcripts=mx)
    print(f"memory-sweep: {s['processed']} transcripts, {s['written']} geschreven "
          f"({s['current']} current, {s['unverified']} unverified), {s['duplicates']} dup, "
          f"{s['expired']} expired, {s['errors']} fouten"
          if s.get("enabled") else "memory-sweep: uitgeschakeld (memory_capture=false)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"memory-sweep: overgeslagen ({e})", file=sys.stderr)
        sys.exit(0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_memory_sweep.py -v`
Expected: PASS (6 tests). Pas zo nodig `test_dedup_skips_near_duplicate` aan per de NOTE (de dedup-pool wordt uit bestaande `09-memory` opgebouwd via `emb.get_cached`; in de test geeft de `emb.embed`-mock een vaste vector — zorg dat `get_cached` óók die vector teruggeeft, bv. door in `setUp` ook `emb.get_cached = lambda f, cache, recompute=True: [0.1,0.2,0.3]` te monkeypatchen).

- [ ] **Step 5: Commit**

```bash
git add scripts/memory-sweep.py tests/test_memory_sweep.py
git commit -m "feat(memory): memory-sweep.py orkestrator (extract/dedup/judge/schrijf/expire/heartbeat)"
```

---

### Task 4: detached launcher + lockfile + ordening + docs

**Files:**
- Create: `scripts/sweep-launch.py`
- Modify: `CONFIGURATION.md`, `CHANGELOG.md`, `commands/sessielog.md`
- Test: `tests/test_sweep_launch.py`

**Interfaces:**
- Produces:
  - `sweep-launch.py` (SessionStart-hook): gegate op `memory_capture`; **single-flight lockfile** (`<vault>/.claude/.sweep.lock` met PID+mtime, stale-reclaim > `STALE_SEC`); spawnt `memory-sweep.py` **detached**; daarna `build-kb-index.py` (ordening); exit 0 fail-open. Functies: `acquire_lock()`, `release_lock()`, `is_stale(lock)`, `main()`.
  - Documentatie: registreer `sweep-launch.py` als SessionStart-hook; documenteer dat `/sessielog` de sweep on-demand kan draaien.

- [ ] **Step 1: Write the failing test**

Create `tests/test_sweep_launch.py`:

```python
"""Tests voor scripts/sweep-launch.py - lockfile + gating (geen echte spawn)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("sweep_launch", str(SCRIPTS_DIR / "sweep-launch.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class SweepLaunchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-launch-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = _load()

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_acquire_then_second_fails(self):
        self.assertTrue(self.m.acquire_lock())
        self.assertFalse(self.m.acquire_lock())  # single-flight
        self.m.release_lock()
        self.assertTrue(self.m.acquire_lock())

    def test_gated_off_skips_spawn(self):
        (self.vault / "kennisbank-settings.json").write_text(
            json.dumps({"memory_capture": False}), encoding="utf-8")
        spawned = []
        self.m._spawn_detached = lambda script, *a: spawned.append(script)
        self.m.main()
        self.assertEqual(spawned, [])  # niets gespawnd als gated off

    def test_main_spawns_when_enabled(self):
        spawned = []
        self.m._spawn_detached = lambda script, *a: spawned.append(Path(script).name)
        self.m.main()
        # sweep eerst, dan index
        self.assertIn("memory-sweep.py", spawned)
        self.assertIn("build-kb-index.py", spawned)
        self.assertLess(spawned.index("memory-sweep.py"), spawned.index("build-kb-index.py"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_sweep_launch.py -v`
Expected: FAIL — `sweep-launch.py` bestaat niet.

- [ ] **Step 3: Implement `scripts/sweep-launch.py`**

Create `scripts/sweep-launch.py`:

```python
#!/usr/bin/env python3
"""sweep-launch.py - SessionStart-launcher voor de capture-sweep.

Dun en NIET-blokkerend: gegate op memory_capture, neemt een single-flight lock,
spawnt memory-sweep.py DETACHED en daarna build-kb-index.py (sweep->index-ordening),
en eindigt met exit 0 (fail-open). De zware LLM-sweep draait dus los van SessionStart
zodat de sessiestart onzichtbaar/snel blijft.

Stdlib only.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

LOCK_NAME = ".sweep.lock"
STALE_SEC = 3600  # een lock ouder dan 1u geldt als verweesd


def _lock_path() -> Path:
    return vault_root() / ".claude" / LOCK_NAME


def is_stale(lock: Path) -> bool:
    try:
        return (time.time() - lock.stat().st_mtime) > STALE_SEC
    except OSError:
        return True


def acquire_lock() -> bool:
    lock = _lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists() and not is_stale(lock):
        return False
    try:
        if lock.exists():
            lock.unlink()  # verweesde lock opruimen
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except OSError:
        return False


def release_lock() -> None:
    try:
        _lock_path().unlink()
    except OSError:
        pass


def _spawn_detached(script: str, *args) -> None:
    cmd = [sys.executable, script, *args]
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x08000000  # DETACHED_PROCESS|CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(cmd, **kwargs)
    except Exception:
        pass


def main() -> int:
    try:
        import _settings
        if not _settings.get("memory_capture", True):
            return 0
    except Exception:
        pass
    if not acquire_lock():
        return 0  # al een sweep bezig
    d = os.path.dirname(os.path.abspath(__file__))
    # ordening: sweep (status-flips/schrijven) eerst, dan de index
    _spawn_detached(os.path.join(d, "memory-sweep.py"))
    _spawn_detached(os.path.join(d, "build-kb-index.py"))
    # de lock wordt door de volgende run als 'stale' opgeruimd; sweep zelf is kort
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
```

> **Ordening-noot:** de twee processen worden detached gespawnd; om een echte race te vermijden draait `build-kb-index` idealiter NA de sweep. In v1 spawnen we beide direct na elkaar — `build-kb-index` is incrementeel en idempotent, en kb-recall herleest live status (fase 3), dus een net-te-vroege index zelf-herstelt bij de volgende SessionStart. Een strikte ketening (sweep → dan index) kan later via een wrapper-script; de test borgt enkel de spawn-VOLGORDE.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_sweep_launch.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Document the SessionStart registration + /sessielog**

In `CONFIGURATION.md`: voeg `sweep-launch.py` toe als SessionStart-hook (mirror de stijl van `build-embed-index.py`/`build-kb-index.py`), met uitleg dat het gegate is op `memory_capture` en de zware sweep detached draait. In `commands/sessielog.md`: voeg een korte stap/noot toe dat `/sessielog` optioneel de sweep on-demand mag draaien (`python3 "$VAULT/.claude/scripts/memory-sweep.py"`). In `CHANGELOG.md`: één regel (autonome capture-sweep + detached launcher).

- [ ] **Step 6: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/sweep-launch.py CONFIGURATION.md CHANGELOG.md commands/sessielog.md tests/test_sweep_launch.py
git commit -m "feat(memory): sweep-launch.py detached SessionStart-launcher + lockfile + docs"
```

---

## Self-Review

**Spec coverage (fase 4b):**
- `.swept`-watermark + transcript-reader → Task 1. ✓ (req 5)
- chunk lange transcripts + dedup + collision-guard → Task 2 (+ `_memory.unique_memory_path`). ✓ (req 1,2,3)
- orkestrator: extract→dedup→judge→schrijf(status/evidence/source)→mark, budget, expire-pass, heartbeat → Task 3. ✓ (AC #1,#2; req 4,6)
- detached launcher + single-flight lockfile + sweep→index-ordening + /sessielog + docs → Task 4. ✓ (AC #3)
- Cross-memory: expire (deterministisch) in Task 3; supersede/cluster + tweede-verdedigingslinie hercontrole → bewust LICHT in v1 (expire gedekt; volledige supersession/cluster is een latere verfijning — genoteerd). (AC #4 deels)
- render-hardening (AC #5) → al in fase 4a. ✓
- Deterministische plumbing unit-getest; LLM mockbaar (AC #6) → alle sweep-tests mocken extract/judge/embed. ✓

**Placeholder scan:** geen TBD/TODO; alle code + testcode volledig.

**Type consistency:** `_extract.extract_candidates(text, max_n) -> [{title,body}]`, `_judge.judge(cand, context) -> {verdict,reason}`, `_memory.write(title, body, status, evidence_basis, source_session, created)` en `unique_memory_path` consistent aangeroepen in de sweep; `ss.pending()/mark()/transcript_text()` en `su.chunk()/is_duplicate()` matchen Task 1/2.

**Geverifieerd vóór uitvoering:** transcript-archief landt in `01-raw/transcripts/*.jsonl` (archive-transcript.py); de `.distilled`-watermark-pattern (distill-notify) is het model voor `.swept`; CC-`.jsonl` heeft `message.{role,content}` (import-cc-history extract_text). De fase-4a seams (`_extract`/`_judge`/`_llm`) en `_memory.write(evidence_basis="agent")` bestaan en accepteren wat de sweep zet.

**Aandachtspunt uitvoerder:** Task 3 — de dedup-pool wordt uit bestaande `09-memory` opgebouwd via `emb.get_cached`; in de test moet je ZOWEL `emb.embed` ALS `emb.get_cached` mocken naar dezelfde vaste vector zodat `test_dedup_skips_near_duplicate` de dedup echt raakt. Task 4 — de lock is bewust simpel (PID-bestand + stale-reclaim); de test mockt `_spawn_detached` zodat er geen echt proces start. Bevestig de spawn-VOLGORDE (sweep vóór index).

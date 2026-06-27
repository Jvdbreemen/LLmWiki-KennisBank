# Agent-geheugen — Fase 1: Fundament (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Leg het datamodel en de configuratie voor de geheugenlaag neer: twee nieuwe toggles (default aan) en een `_memory.py` format-module die memory-`.md`-files schrijft/leest, plus de `09-memory/`-vaultmap en documentatie. Nog geen gedrag — alleen het fundament waar fase 2–5 op bouwen.

**Architecture:** Volgt de bestaande KennisBank script-conventies: stdlib-only modules in `scripts/` met een leidende underscore (importeerbaar zonder hyphen), zelf-lokaliserende vault via `KENNISBANK_VAULT`, toggles via `_settings.py`. `_memory.py` is een pure bibliotheek (geen I/O-side-effects bij import) die memory-frontmatter rendert en pareert, hergebruikt `_common.slugify` en `_frontmatter.parse_frontmatter`.

**Tech Stack:** Python 3.10+ (stdlib only), `unittest` (bestaand testpatroon), markdown + YAML-frontmatter, bash (`setup.sh`).

## Global Constraints

- **Stdlib only** in alle `scripts/`-modules — geen externe pip-deps in fase 1.
- **Toggles default aan:** `memory_capture` en `memory_recall` default `True` (bewuste afwijking van de opt-in-conventie; geheugen is kern-functionaliteit). Spec randvoorwaarde #9.
- **Vaultmap:** geheugen woont in `09-memory/` (volgende vrije nummer; `05-` is `05-bronnen/`). Maand-archief in `09-memory/archive/`.
- **Onafhankelijk ontkoppeld** (spec #9): niets in fase 1 mag bestaand gedrag (`auto_archive`, `embed_index`, `daily_graphify`, `distill_notify`) wijzigen.
- **Status-set:** `unverified | current | superseded | retracted | expired`. Default bij capture: `unverified`.
- **Evidence-basis-set:** `getypt | cc-sessie | audio | import | autoresearch | agent`.
- **Interpreter-conventie:** repo-scripts en `setup.sh` gebruiken `python3` (portability); alleen Windows-hooks gebruiken `py -3`. Fase 1 raakt geen hooks.
- **Test-conventie:** `unittest`, temp-vault via `KENNISBANK_VAULT`, `SCRIPTS_DIR` op `sys.path`, env hersteld in `tearDown`.

---

### Task 1: Twee geheugen-toggles in `_settings.py`

**Files:**
- Modify: `scripts/_settings.py:36-41` (de `DEFAULTS`-dict)
- Test: `tests/test_settings.py` (nieuwe testmethodes in bestaande `SettingsTest`)

**Interfaces:**
- Consumes: bestaande `_settings.get(key, default)`, `_settings.DEFAULTS`.
- Produces: `DEFAULTS["memory_capture"] == True`, `DEFAULTS["memory_recall"] == True`. Latere fases lezen ze via `_settings.get("memory_capture", True)` / `_settings.get("memory_recall", True)`.

- [ ] **Step 1: Write the failing test**

In `tests/test_settings.py`, voeg binnen `class SettingsTest` toe:

```python
    def test_memory_toggles_default_true(self):
        # Geen settings-bestand → defaults. Geheugen is kern-functionaliteit: default aan.
        self.assertTrue(_settings.get("memory_capture", _settings.DEFAULTS["memory_capture"]))
        self.assertTrue(_settings.get("memory_recall", _settings.DEFAULTS["memory_recall"]))

    def test_memory_toggles_in_defaults(self):
        self.assertIs(_settings.DEFAULTS.get("memory_capture"), True)
        self.assertIs(_settings.DEFAULTS.get("memory_recall"), True)

    def test_memory_toggle_independently_settable(self):
        # recall uit, capture aan: onafhankelijk schakelbaar.
        _settings.set("memory_recall", False)
        self.assertFalse(_settings.get("memory_recall", True))
        self.assertTrue(_settings.get("memory_capture", True))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_settings.py -k memory -v`
Expected: FAIL — `test_memory_toggles_in_defaults` faalt met `AssertionError: None is not True` (keys ontbreken nog in `DEFAULTS`).

- [ ] **Step 3: Add the toggles to DEFAULTS**

In `scripts/_settings.py`, vervang de `DEFAULTS`-dict (regels 36-41) door:

```python
DEFAULTS = {
    "auto_archive": False,
    "distill_notify": True,
    "embed_index": True,
    "daily_graphify": True,
    # Geheugen-subsysteem (spec fase 1). Kern-functionaliteit → default aan,
    # bewust afwijkend van de opt-in-conventie van auto_archive.
    "memory_capture": True,
    "memory_recall": True,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_settings.py -k memory -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full settings suite (no regressions)**

Run: `python3 -m pytest tests/test_settings.py -v`
Expected: alle bestaande tests + de 3 nieuwe PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/_settings.py tests/test_settings.py
git commit -m "feat(memory): memory_capture + memory_recall toggles (default aan)"
```

---

### Task 2: `_memory.py` — memory-format module

**Files:**
- Create: `scripts/_memory.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Consumes: `_common.slugify(text, max_len)`, `_common._today_iso()`, `_frontmatter.parse_frontmatter(text) -> (dict, str)`, `_vaultpath.vault_root() -> Path`.
- Produces:
  - `STATUSES: tuple[str, ...]` = `("unverified","current","superseded","retracted","expired")`
  - `EVIDENCE_BASES: tuple[str, ...]` = `("getypt","cc-sessie","audio","import","autoresearch","agent")`
  - `memory_dir() -> Path` (= `<vault>/09-memory`)
  - `memory_path(title, created=None) -> Path` (= `<vault>/09-memory/<YYYY-MM-DD>-<slug>.md`)
  - `render(title, body, *, status="unverified", evidence_basis="cc-sessie", source_session="", created=None, updated=None, expires=None, superseded_by=None, tags=None) -> str` (volledige markdown met frontmatter)
  - `write(title, body, **kw) -> Path` (rendert + schrijft, maakt `09-memory/` aan, return pad)
  - `read_status(path) -> str` (status uit frontmatter, `"unverified"` als afwezig/onleesbaar)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_memory.py`:

```python
"""Tests voor scripts/_memory.py - het memory-format (frontmatter + paden).

Pure lib: geen netwerk, geen embeddings. Vault naar temp via KENNISBANK_VAULT.
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

import _memory  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402


class MemoryFormatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-mem-"))
        self.vault = self.tmp / "vault"
        self.vault.mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_status_and_evidence_sets(self):
        self.assertEqual(
            _memory.STATUSES,
            ("unverified", "current", "superseded", "retracted", "expired"),
        )
        self.assertIn("cc-sessie", _memory.EVIDENCE_BASES)

    def test_memory_path_layout(self):
        p = _memory.memory_path("Hook-gedreven retrieval", created="2026-06-27")
        self.assertEqual(p.parent, self.vault / "09-memory")
        self.assertEqual(p.name, "2026-06-27-hook-gedreven-retrieval.md")

    def test_render_defaults_to_unverified(self):
        md = _memory.render("Titel", "De body.", created="2026-06-27", updated="2026-06-27")
        fm, body = parse_frontmatter(md)
        self.assertEqual(fm["type"], "memory")
        self.assertEqual(fm["status"], "unverified")
        self.assertEqual(fm["evidence_basis"], "cc-sessie")
        self.assertIn("De body.", body)

    def test_render_rejects_bad_status(self):
        with self.assertRaises(ValueError):
            _memory.render("T", "b", status="bogus")

    def test_write_creates_file_and_dir(self):
        p = _memory.write("Een les", "Wat ik leerde.", created="2026-06-27")
        self.assertTrue(p.exists())
        self.assertTrue((self.vault / "09-memory").is_dir())
        self.assertEqual(_memory.read_status(p), "unverified")

    def test_read_status_missing_returns_unverified(self):
        f = self.vault / "09-memory" / "x.md"
        f.parent.mkdir(parents=True)
        f.write_text("geen frontmatter", encoding="utf-8")
        self.assertEqual(_memory.read_status(f), "unverified")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_memory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_memory'`.

- [ ] **Step 3: Implement `_memory.py`**

Create `scripts/_memory.py`:

```python
#!/usr/bin/env python3
"""_memory.py - format van de ruwe geheugenlaag (09-memory/).

Pure stdlib-bibliotheek: rendert en pareert memory-markdown met frontmatter,
en bouwt paden. Geen netwerk, geen embeddings, geen side-effects bij import.
Underscore-naam zodat scripts het importeren na sys.path.insert (idem _settings).

Frontmatter-contract (spec fase 1):
    type: memory
    status: unverified | current | superseded | retracted | expired
    evidence_basis: getypt | cc-sessie | audio | import | autoresearch | agent
    source_session, created, updated, expires?, superseded_by?, tags
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import slugify, _today_iso  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

STATUSES = ("unverified", "current", "superseded", "retracted", "expired")
EVIDENCE_BASES = ("getypt", "cc-sessie", "audio", "import", "autoresearch", "agent")
DEFAULT_STATUS = "unverified"
DEFAULT_EVIDENCE = "cc-sessie"


def memory_dir() -> Path:
    return vault_root() / "09-memory"


def memory_path(title: str, created: str | None = None) -> Path:
    date = created or _today_iso()
    return memory_dir() / f"{date}-{slugify(title)}.md"


def _yaml_list(items) -> str:
    return "[" + ", ".join(items) + "]"


def render(title: str, body: str, *, status: str = DEFAULT_STATUS,
           evidence_basis: str = DEFAULT_EVIDENCE, source_session: str = "",
           created: str | None = None, updated: str | None = None,
           expires: str | None = None, superseded_by=None, tags=None) -> str:
    if status not in STATUSES:
        raise ValueError(f"ongeldige status: {status!r} (verwacht een van {STATUSES})")
    if evidence_basis not in EVIDENCE_BASES:
        raise ValueError(f"ongeldige evidence_basis: {evidence_basis!r}")
    created = created or _today_iso()
    updated = updated or created
    lines = ["---",
             f'title: "{title}"',
             "type: memory",
             f"status: {status}",
             f"evidence_basis: {evidence_basis}",
             f'source_session: "{source_session}"',
             f"created: {created}",
             f"updated: {updated}"]
    if expires:
        lines.append(f"expires: {expires}")
    if superseded_by:
        lines.append(f"superseded_by: {_yaml_list(superseded_by)}")
    lines.append(f"tags: {_yaml_list(tags or [])}")
    lines.append("---")
    lines.append("")
    lines.append(body.rstrip() + "\n")
    return "\n".join(lines)


def write(title: str, body: str, **kw) -> Path:
    created = kw.get("created")
    p = memory_path(title, created)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(title, body, **kw), encoding="utf-8")
    return p


def read_status(path) -> str:
    try:
        fm, _ = parse_frontmatter(Path(path).read_text(encoding="utf-8"))
        status = fm.get("status")
        return status if status in STATUSES else DEFAULT_STATUS
    except Exception:
        return DEFAULT_STATUS
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_memory.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Bevestig de frontmatter-roundtrip**

`_frontmatter.parse_frontmatter` strikt enclosing quotes weg (geverifieerd: regels 64-70 van `scripts/_frontmatter.py`), dus zowel `title: "Titel"` als `status: unverified` pareren naar schone strings (`"Titel"`, `"unverified"`). De roundtrip render→parse is dus stabiel ongeacht quoting.

Run: `python3 -m pytest tests/test_memory.py::MemoryFormatTest::test_render_defaults_to_unverified -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/_memory.py tests/test_memory.py
git commit -m "feat(memory): _memory.py format-module (frontmatter, paden, status)"
```

---

### Task 3: `09-memory/` vaultmap + documentatie + settings-voorbeeld

**Files:**
- Modify: `setup.sh:103` (mkdir-regel met de vaultmappen)
- Modify: `vault-structure/README.md` (mappenoverzicht + sectie)
- Modify: `kennisbank-settings.example.json` (twee nieuwe toggles, default true)
- Modify: `commands/kennisbank/settings.md` (documenteer de twee toggles)
- Test: `tests/test_setup_deploy.py` (assert dat `09-memory` in de mkdir-regel staat)

**Interfaces:**
- Consumes: niets nieuws.
- Produces: `09-memory/` + `09-memory/archive/` worden door `setup.sh` aangemaakt; `kennisbank-settings.example.json` toont de defaults.

- [ ] **Step 1: Write the failing test**

In `tests/test_setup_deploy.py`, voeg een test toe die `setup.sh` als tekst leest en de map controleert (volg het bestaande leespatroon in dat bestand; als er al een helper is die `setup.sh` inleest, hergebruik die):

```python
    def test_setup_creates_09_memory_dir(self):
        text = (Path(__file__).resolve().parent.parent / "setup.sh").read_text(encoding="utf-8")
        self.assertIn("09-memory", text)
        self.assertIn("09-memory/archive", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_setup_deploy.py -k 09_memory -v`
Expected: FAIL — `09-memory` staat nog niet in `setup.sh`.

- [ ] **Step 3: Add the dirs to `setup.sh`**

In `setup.sh` regel 103, voeg `09-memory` en `09-memory/archive` toe aan de brace-expansie:

```bash
mkdir -p "$VAULT"/{00-inbox,01-raw/sessies,01-raw/transcripts,02-wiki,03-projecten,04-templates,05-bronnen,06-claude,07-media,08-archive,09-memory,09-memory/archive}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_setup_deploy.py -k 09_memory -v`
Expected: PASS.

- [ ] **Step 5: Update `kennisbank-settings.example.json`**

Vervang de inhoud door (twee nieuwe toggles, default true):

```json
{
  "auto_archive": false,
  "distill_notify": true,
  "embed_index": true,
  "daily_graphify": true,
  "memory_capture": true,
  "memory_recall": true
}
```

- [ ] **Step 6: Document `09-memory/` in `vault-structure/README.md`**

Voeg `09-memory/` toe aan het ASCII-mappenoverzicht (na `08-archive/`) en voeg een sectie toe:

```markdown
### `09-memory/`
Ruwe agent-geheugenlaag. Atomaire memories (`YYYY-MM-DD-slug.md`) met
truth-maintenance-frontmatter (`status`, `evidence_basis`, `superseded_by`).
Gevuld door het geheugen-subsysteem (toggle `memory_capture`); niet handmatig
gecureerd. Maand-archief van oude, niet-gepromote memories in `09-memory/archive/`.
Gepromote kennis verhuist via `/wiki` naar `02-wiki/`.
```

- [ ] **Step 7: Document the toggles in `commands/kennisbank/settings.md`**

Voeg `memory_capture` en `memory_recall` toe aan de toggle-tabel/-lijst in dat bestand (volg de bestaande opmaak), met één regel elk:
- `memory_capture` (default aan) — extractie+judge van memories naar `09-memory/` + onderhoud.
- `memory_recall` (default aan) — injecteer memories in de context via hook + lokale MCP.

- [ ] **Step 8: Run the full suite (no regressions)**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 9: Commit**

```bash
git add setup.sh vault-structure/README.md kennisbank-settings.example.json commands/kennisbank/settings.md tests/test_setup_deploy.py
git commit -m "feat(memory): 09-memory/ vaultmap + settings-voorbeeld + docs"
```

---

## Self-Review

**Spec coverage (fase 1-scope):**
- Toggles `memory_capture`/`memory_recall` default aan → Task 1. ✓
- Memory-frontmatter-contract (status/evidence_basis/superseded_by/expires) → Task 2 `render`. ✓
- `09-memory/` + `09-memory/archive/` → Task 3. ✓
- Status-set + evidence-set als single source → Task 2 constants. ✓
- Ontkoppeling (#9): fase 1 raakt geen bestaand gedrag — alleen nieuwe keys/dir/module. ✓
- Buiten fase 1 (bewust): index-store (fase 2), recall (3), capture/sweep (4), rebuild/backfill (5).

**Placeholder scan:** geen TBD/TODO; alle code volledig; testcode compleet.

**Type consistency:** `render(...)` keyword-args matchen `write(**kw)` doorgifte; `read_status` leest dezelfde `status`-key die `render` schrijft; `STATUSES`/`EVIDENCE_BASES` als tuples consistent gebruikt in tests en module.

**Geverifieerd vóór uitvoering:** `parse_frontmatter` strikt enclosing quotes (`_frontmatter.py:64-70`), `slugify` produceert `hook-gedreven-retrieval` uit `"Hook-gedreven retrieval"` (`_common.py:23-30`), `_today_iso()` geeft `YYYY-MM-DD` (`_common.py:37-38`). De testcode in dit plan klopt tegen de echte signatures.

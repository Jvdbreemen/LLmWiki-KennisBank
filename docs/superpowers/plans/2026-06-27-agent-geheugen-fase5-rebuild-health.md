# Agent-geheugen — Fase 5: rebuild-memory + backfill + health/doctor (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** De ops-laag rond het geheugen: een `--all` her-extractiemodus + `/kennisbank:rebuild-memory`-commando, de upgrade-backfill, doctor-checks (no-cloud + quarantaine-rot) en een SessionStart-health-surface die de heartbeat luid maakt. Hiermee is het geheugen-subsysteem compleet, herbouwbaar en zichtbaar-bij-falen.

**Architecture:** `memory-sweep.py` krijgt een `ignore_watermark` (`--all`) modus die ALLE transcripts her-extraheert; dedup maakt het idempotent. `/kennisbank:rebuild-memory` is een bevestigend commando erbovenop. Een nieuwe `memory-doctor.py` levert deterministische checks (no-cloud op de actieve `_llm`-keten + Ollama-endpoint, en quarantaine-rot = aantal `unverified` ouder dan 48u) die `doctor.sh` aanroept. `memory-notify.py` is een SessionStart-hook (spiegel van `distill-notify.py`) die de heartbeat + rot-achterstand surfacet — zo verzoenen we "onzichtbaar" met "luid bij falen". Geen wiki→memory seeding (keuze C).

**Tech Stack:** Python 3.10+ (stdlib), bash (`doctor.sh`), `_memory`/`_llm`/`_sweepstate`/`_frontmatter`, `unittest`.

## Global Constraints

- **`rebuild-memory` is zwaar + bevestigend:** her-extractie over ALLE transcripts (LLM-werk). Het commando vraagt expliciete bevestiging vóór het draait. Idempotent via dedup (geen dubbele memories bij herhaald draaien).
- **No wiki→memory seeding (keuze C):** wiki blijft promotie-doel; nooit memory-bron.
- **No-cloud-doctor (#4):** waarschuw als de actieve `_llm`-keten een cloud-provider bevat, EN als de actieve Ollama-endpoint niet `localhost`/`127.0.0.1` is (remote-ollama lekt stil — `is_local()` is naam-gebaseerd, dus endpoint apart checken).
- **Quarantaine-rot:** tel `09-memory`-files met `status: unverified` en `created` ouder dan 48u; waarschuw als > 0 (de sweep promoot/retract ze niet — duidt op een hangende judge/sweep).
- **Health luid:** `memory-notify.py` surfacet bij SessionStart: `model_unreachable`, sweep-`errors`, rot-achterstand, of een verouderde heartbeat. Niets te melden → geen output (onzichtbaar).
- **Fail-soft/fail-open:** doctor-helper en de SessionStart-hook crashen nooit; ontbrekende heartbeat/lege vault → stil/0.
- **Decoupling:** bestaande modules ongemoeid behalve `memory-sweep.py` (additieve `--all`-modus). `doctor.sh` wordt uitgebreid (additief). De upgrade-skill krijgt een backfill-stap.
- **Interpreter:** repo-scripts/`setup.sh`/commands = `python3`; SessionStart-hook-registratie = `py -3` (Windows).

---

### Task 1: `--all` her-extractiemodus + `/kennisbank:rebuild-memory`

**Files:**
- Modify: `scripts/memory-sweep.py` (`run_sweep(..., ignore_watermark=False)` + `--all` CLI)
- Create: `commands/kennisbank/rebuild-memory.md`
- Test: `tests/test_memory_sweep.py` (1 test toevoegen)

**Interfaces:**
- Produces: `run_sweep(max_transcripts=10, max_chunks=6, ignore_watermark=False)` — bij `ignore_watermark=True` worden ALLE `*.jsonl` in `01-raw/transcripts/` verwerkt (niet alleen `pending()`); dedup voorkomt duplicaten. CLI `--all` zet `ignore_watermark=True`.

- [ ] **Step 1: Write the failing test**

Voeg toe aan `class MemorySweepTest` in `tests/test_memory_sweep.py`:

```python
    def test_rebuild_all_reprocesses_marked(self):
        # eerste sweep markeert s1 als swept
        self.m.run_sweep()
        # normale 2e sweep doet niets
        self.assertEqual(self.m.run_sweep()["processed"], 0)
        # --all negeert de watermark en verwerkt s1 opnieuw...
        s = self.m.run_sweep(ignore_watermark=True)
        self.assertEqual(s["processed"], 1)
        # ...maar dedup voorkomt een tweede memory-file (idempotent)
        mems = list((self.vault / "09-memory").glob("*.md"))
        self.assertEqual(len(mems), 1)
```

> NOTE: dit leunt op de dedup-mock uit `setUp` (zowel `emb.embed` als `emb.get_cached` geven dezelfde vector → de her-geëxtraheerde kandidaat is een duplicaat van de bestaande memory). Bevestig dat `setUp` `emb.get_cached` mockt; zo niet, voeg het toe.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_memory_sweep.py -k rebuild_all -v`
Expected: FAIL — `run_sweep` kent nog geen `ignore_watermark`.

- [ ] **Step 3: Add the `--all` mode**

In `scripts/memory-sweep.py`, pas `run_sweep` aan: vervang de transcript-selectie zodat `ignore_watermark` ALLE transcripts pakt. Verander de signatuur en de selectie-regel:

```python
def run_sweep(max_transcripts: int = 10, max_chunks: int = 6,
              ignore_watermark: bool = False) -> dict:
    # ... bestaande gate + s-dict + reachability-probe ...
    if ignore_watermark:
        tdir = vault_root() / "01-raw" / "transcripts"
        todo = sorted(tdir.glob("*.jsonl"))[:max_transcripts] if tdir.exists() else []
    else:
        todo = ss.pending()[:max_transcripts]
    for tp in todo:
        # ... bestaande verwerking ...
```

(Gebruik `todo` waar nu `ss.pending()[:max_transcripts]` staat. De `reachability-probe`-guard moet ook op `todo` checken i.p.v. `ss.pending()` — gebruik `if todo and not _model_reachable():` met dezelfde lijst, of bepaal `todo` vóór de probe.)

En in `main`, voeg de `--all`-vlag toe:

```python
    ignore = "--all" in argv
    s = run_sweep(max_transcripts=mx, ignore_watermark=ignore)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_memory_sweep.py -v`
Expected: PASS (de nieuwe + alle bestaande).

- [ ] **Step 5: Create `/kennisbank:rebuild-memory`**

Create `commands/kennisbank/rebuild-memory.md`:

```markdown
---
description: Her-extraheer ALLE geheugen uit gearchiveerde transcripts (zwaar, vraagt bevestiging)
---

# /kennisbank:rebuild-memory

Her-extraheert het ruwe agent-geheugen (`09-memory/`) uit ALLE gearchiveerde
transcripts in `01-raw/transcripts/`, los van de `.swept`-watermark. Dit is een
**zware** operatie: het draait de LLM-extractie + judge over je hele
transcript-backlog. Idempotent — dedup voorkomt dubbele memories, dus herhaald
draaien is veilig.

**Vraag eerst expliciete bevestiging** (dit kan veel LLM-werk zijn). Pas na "ja":

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/memory-sweep.py" --all
```

Toon daarna de samenvattingsregel (verwerkte transcripts, geschreven memories,
duplicaten, fouten). Bij "model onbereikbaar": meld dat Ollama/het LLM niet
draait; er wordt niets gemarkeerd of geschreven.

Voor alleen de zoekindex herbouwen (niet her-extraheren): gebruik
`/kennisbank:rebuild-index`.
```

- [ ] **Step 6: Commit**

```bash
git add scripts/memory-sweep.py commands/kennisbank/rebuild-memory.md tests/test_memory_sweep.py
git commit -m "feat(memory): --all her-extractiemodus + /kennisbank:rebuild-memory"
```

---

### Task 2: `memory-doctor.py` checks + `doctor.sh`-wiring

**Files:**
- Create: `scripts/memory-doctor.py`
- Modify: `scripts/doctor.sh`
- Test: `tests/test_memory_doctor.py`

**Interfaces:**
- Produces:
  - `memory-doctor.py nocloud` → print één regel per waarschuwing (cloud-provider in keten; niet-lokale Ollama-endpoint); exit 0 altijd. `cloud_warnings() -> list[str]`.
  - `memory-doctor.py rot [--hours 48]` → print het aantal `unverified` ouder dan N uur; `rot_count(hours=48) -> int`.
  - `doctor.sh` roept beide aan en mapt op `report_pass`/`report_warn`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_memory_doctor.py`:

```python
"""Tests voor scripts/memory-doctor.py - no-cloud + quarantaine-rot checks."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import importlib.util


def _load():
    spec = importlib.util.spec_from_file_location("memory_doctor", str(SCRIPTS_DIR / "memory-doctor.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class MemoryDoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-doc-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = {k: os.environ.get(k) for k in
                       ("KENNISBANK_VAULT", "KB_LLM_PROVIDERS", "KB_LLM_ENDPOINT")}
        for k in ("KB_LLM_PROVIDERS", "KB_LLM_ENDPOINT"):
            os.environ.pop(k, None)
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = _load()

    def tearDown(self):
        import shutil
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, name, status, created):
        (self.vault / "09-memory" / name).write_text(
            f"---\ntitle: T\ntype: memory\nstatus: {status}\ncreated: {created}\n---\n\nbody",
            encoding="utf-8")

    def test_nocloud_clean_default(self):
        self.assertEqual(self.m.cloud_warnings(), [])  # default ollama localhost

    def test_nocloud_flags_cloud_provider(self):
        os.environ["KB_LLM_PROVIDERS"] = "ollama, openrouter"
        w = self.m.cloud_warnings()
        self.assertTrue(any("openrouter" in x for x in w))

    def test_nocloud_flags_remote_ollama(self):
        os.environ["KB_LLM_ENDPOINT"] = "http://192.168.1.50:11434"
        w = self.m.cloud_warnings()
        self.assertTrue(any("endpoint" in x.lower() for x in w))

    def test_rot_counts_old_unverified(self):
        old = (date.today() - timedelta(days=3)).isoformat()
        new = date.today().isoformat()
        self._mem("a.md", "unverified", old)   # rot
        self._mem("b.md", "unverified", new)   # vers, geen rot
        self._mem("c.md", "current", old)      # current, geen rot
        self.assertEqual(self.m.rot_count(hours=48), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_memory_doctor.py -v`
Expected: FAIL — `memory-doctor.py` bestaat niet.

- [ ] **Step 3: Implement `scripts/memory-doctor.py`**

Create `scripts/memory-doctor.py`:

```python
#!/usr/bin/env python3
"""memory-doctor.py - deterministische gezondheidschecks voor het geheugen.

Twee checks, aangeroepen door doctor.sh:
  nocloud  - waarschuw als de actieve _llm-keten cloud bevat OF de Ollama-endpoint
             niet lokaal is (is_local() is naam-gebaseerd; endpoint apart checken).
  rot      - tel unverified memories ouder dan N uur (hangende judge/sweep).

Fail-soft: ontbrekende vault/config -> geen waarschuwing / 0. Stdlib only.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _llm  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def cloud_warnings() -> list:
    out = []
    try:
        chain = _llm.providers()
    except Exception:
        return out
    cloud = [p for p in chain if p in _llm.CLOUD_PROVIDERS]
    if cloud:
        out.append(f"LLM-keten bevat cloud-provider(s): {', '.join(cloud)} "
                   f"- content kan je machine verlaten (#4)")
    # endpoint-check voor de actieve ollama-provider
    if chain and chain[0] == "ollama":
        try:
            ep = _llm._endpoint("ollama")
        except Exception:
            ep = ""
        if ep and not any(h in ep for h in _LOCAL_HOSTS):
            out.append(f"Ollama-endpoint is niet lokaal ({ep}) - embeddings/generatie "
                       f"verlaten je machine (#4)")
    return out


def rot_count(hours: int = 48) -> int:
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return 0
    cutoff = date.today() - timedelta(hours=hours)
    n = 0
    for f in mdir.glob("**/*.md"):
        try:
            fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if fm.get("status") != "unverified":
            continue
        created = fm.get("created", "")
        try:
            d = datetime.fromisoformat(created).date() if created else date.today()
        except Exception:
            continue
        if d < cutoff:
            n += 1
    return n


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "nocloud":
        for w in cloud_warnings():
            print(w)
        return 0
    if argv and argv[0] == "rot":
        hours = 48
        if "--hours" in argv:
            try:
                hours = int(argv[argv.index("--hours") + 1])
            except Exception:
                hours = 48
        print(rot_count(hours))
        return 0
    print("usage: memory-doctor.py nocloud|rot [--hours N]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_memory_doctor.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Wire into `doctor.sh`**

Voeg vóór de samenvatting in `scripts/doctor.sh` een geheugen-sectie toe die de helper aanroept (volg de bestaande `report_pass`/`report_warn`-stijl; gebruik `python3`):

```bash
# --- Geheugen-subsysteem (fase 5) ---
if [ -f "$VAULT/.claude/scripts/memory-doctor.py" ]; then
  nocloud_out="$(python3 "$VAULT/.claude/scripts/memory-doctor.py" nocloud 2>/dev/null)"
  if [ -n "$nocloud_out" ]; then
    while IFS= read -r line; do report_warn "geheugen no-cloud" "$line"; done <<EOF2
$nocloud_out
EOF2
  else
    report_pass "geheugen no-cloud" "LLM-keten lokaal"
  fi
  rot="$(python3 "$VAULT/.claude/scripts/memory-doctor.py" rot 2>/dev/null)"
  if [ "${rot:-0}" -gt 0 ] 2>/dev/null; then
    report_warn "geheugen quarantaine" "$rot unverified memories ouder dan 48u (sweep/judge hangt?)"
  else
    report_pass "geheugen quarantaine" "geen rot"
  fi
fi
```

(Pas het exacte pad/quoting aan op de bestaande `doctor.sh`-stijl. Houd het additief — verander geen bestaande checks.)

- [ ] **Step 6: Commit**

```bash
git add scripts/memory-doctor.py scripts/doctor.sh tests/test_memory_doctor.py
git commit -m "feat(memory): memory-doctor no-cloud + quarantaine-rot checks + doctor.sh-wiring"
```

---

### Task 3: `memory-notify.py` SessionStart-health-surface

**Files:**
- Create: `scripts/memory-notify.py`
- Test: `tests/test_memory_notify.py`

**Interfaces:**
- Produces: `memory-notify.py` (SessionStart-hook): leest de heartbeat (`<vault>/.claude/memory-sweep-status.json`) + `rot_count`; emit een `additionalContext`-JSON als er iets te melden is (`model_unreachable`, sweep-`errors`>0, rot>0, of een verouderde/ontbrekende heartbeat terwijl er pending transcripts zijn). Niets te melden → geen output (onzichtbaar). `notice() -> str` (de melding of "").

- [ ] **Step 1: Write the failing test**

Create `tests/test_memory_notify.py`:

```python
"""Tests voor scripts/memory-notify.py - SessionStart-health-surface."""
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
    spec = importlib.util.spec_from_file_location("memory_notify", str(SCRIPTS_DIR / "memory-notify.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class MemoryNotifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-notify-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
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

    def _hb(self, obj):
        (self.vault / ".claude" / "memory-sweep-status.json").write_text(
            json.dumps(obj), encoding="utf-8")

    def test_clean_no_notice(self):
        self._hb({"last_run": "2026-06-27T10:00:00+00:00", "errors": 0,
                  "model_unreachable": False})
        self.assertEqual(self.m.notice(), "")

    def test_model_unreachable_notice(self):
        self._hb({"model_unreachable": True, "errors": 0})
        self.assertIn("onbereikbaar", self.m.notice().lower())

    def test_errors_notice(self):
        self._hb({"errors": 3, "model_unreachable": False})
        self.assertIn("3", self.m.notice())

    def test_rot_notice(self):
        from datetime import date, timedelta
        old = (date.today() - timedelta(days=3)).isoformat()
        (self.vault / "09-memory" / "a.md").write_text(
            f"---\ntype: memory\nstatus: unverified\ncreated: {old}\n---\n\nx", encoding="utf-8")
        self._hb({"errors": 0, "model_unreachable": False})
        self.assertIn("unverified", self.m.notice().lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_memory_notify.py -v`
Expected: FAIL — `memory-notify.py` bestaat niet.

- [ ] **Step 3: Implement `scripts/memory-notify.py`**

Create `scripts/memory-notify.py`:

```python
#!/usr/bin/env python3
"""memory-notify.py - SessionStart-health-surface voor het geheugen.

Verzoent 'onzichtbaar' met 'luid bij falen': leest de sweep-heartbeat + de
quarantaine-rot en meldt ALLEEN als er iets mis is (model onbereikbaar, sweep-
fouten, of unverified-rot). Niets mis -> geen output (stil).

SessionStart-output-contract: {"hookSpecificOutput": {"hookEventName":
"SessionStart", "additionalContext": "..."}}. Fail-open: altijd exit 0.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

HEARTBEAT = "memory-sweep-status.json"


def _rot() -> int:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "memory_doctor", os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory-doctor.py"))
        md = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(md)
        return md.rot_count(48)
    except Exception:
        return 0


def notice() -> str:
    msgs = []
    hb_path = vault_root() / ".claude" / HEARTBEAT
    hb = {}
    if hb_path.exists():
        try:
            hb = json.loads(hb_path.read_text(encoding="utf-8")) or {}
        except Exception:
            hb = {}
    if hb.get("model_unreachable"):
        msgs.append("geheugen-sweep: LLM/embed was onbereikbaar - capture gepauzeerd "
                    "(transcripts blijven wachten).")
    if isinstance(hb.get("errors"), int) and hb["errors"] > 0:
        msgs.append(f"geheugen-sweep: {hb['errors']} fout(en) in de laatste run.")
    rot = _rot()
    if rot > 0:
        msgs.append(f"geheugen: {rot} unverified memories ouder dan 48u "
                    f"(sweep/judge promoot ze niet - draai /kennisbank:settings of check Ollama).")
    return " ".join(msgs)


def main() -> int:
    msg = notice()
    if msg:
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "KennisBank-geheugen: " + msg,
            }
        }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_memory_notify.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Document the SessionStart registration**

In `CONFIGURATION.md`: voeg `memory-notify.py` toe als SessionStart-hook (mirror de stijl van `distill-notify.py`), met uitleg dat het alleen meldt bij problemen (stil als gezond).

- [ ] **Step 6: Commit**

```bash
git add scripts/memory-notify.py tests/test_memory_notify.py CONFIGURATION.md
git commit -m "feat(memory): memory-notify SessionStart-health-surface (luid bij falen, stil gezond)"
```

---

### Task 4: upgrade-backfill + docs

**Files:**
- Modify: `skills/kennisbank-upgrade/SKILL.md`
- Modify: `CHANGELOG.md`, `vault-structure/README.md` (heartbeat/lock-bestanden noemen)
- Test: `tests/test_skill_frontmatter.py` (als die de upgrade-skill valideert; anders een doc-presence-test in `tests/test_setup_deploy.py`)

**Interfaces:**
- Produces: de `kennisbank-upgrade`-skill draait bij upgrade naar deze versie eenmalig de backfill (`memory-sweep.py --all`) over de bestaande transcript-backlog, en documenteert dat. Idempotent via dedup.

- [ ] **Step 1: Write the failing test**

Voeg een presence-test toe (volg het patroon in `tests/test_setup_deploy.py` of `test_skill_frontmatter.py`):

```python
    def test_upgrade_skill_mentions_memory_backfill(self):
        text = (Path(__file__).resolve().parent.parent /
                "skills" / "kennisbank-upgrade" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("rebuild-memory", text)
        self.assertIn("backfill", text.lower())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/ -k upgrade_skill_mentions_memory_backfill -v`
Expected: FAIL — de upgrade-skill noemt de backfill nog niet.

- [ ] **Step 3: Add the backfill step to the upgrade skill**

In `skills/kennisbank-upgrade/SKILL.md`: voeg een stap toe (in de stijl van de bestaande stappen) die — NA het deployen van de nieuwe scripts en ALS `memory_capture` aan staat — eenmalig de geheugen-backfill aanbiedt/draait:

```markdown
### Geheugen-backfill (eenmalig, bij upgrade naar de geheugen-versie)

Als `memory_capture` aan staat en er al transcripts in `01-raw/transcripts/`
staan, bied aan de bestaande backlog te her-extraheren tot geheugen:

> "Er staan N gearchiveerde transcripts. Wil je die nu eenmalig tot geheugen
> verwerken (`/kennisbank:rebuild-memory`)? Dit is zwaar LLM-werk maar idempotent."

Pas na bevestiging:

```bash
python3 "$VAULT/.claude/scripts/memory-sweep.py" --all
```

Idempotent via dedup; herhaald draaien maakt geen dubbele memories. Sla over als
de gebruiker nee zegt of als Ollama/het LLM niet draait.
```

- [ ] **Step 4: Update `CHANGELOG.md` + `vault-structure/README.md`**

`CHANGELOG.md`: één regel (rebuild-memory + backfill + health/doctor — geheugen-subsysteem compleet). `vault-structure/README.md`: noem de afgeleide bestanden `kb-index.db`, `memory-sweep-status.json` (heartbeat) en `.sweep.lock` onder `.claude/` zodat het layout-overzicht klopt.

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/kennisbank-upgrade/SKILL.md CHANGELOG.md vault-structure/README.md tests/
git commit -m "feat(memory): upgrade-backfill + docs (geheugen-subsysteem compleet)"
```

---

## Self-Review

**Spec coverage (fase 5):**
- `/kennisbank:rebuild-memory` (zwaar, bevestigend, idempotent via dedup) → Task 1. ✓
- `--all` her-extractie negeert watermark → Task 1. ✓
- No-cloud-doctor (cloud-keten + niet-lokale Ollama-endpoint) → Task 2 (sluit de fase-4a doctor-noot). ✓
- Quarantaine-rot (unverified > 48u) → Task 2. ✓
- SessionStart-health-surface (luid bij falen, stil gezond) → Task 3. ✓
- Upgrade-backfill (eenmalig over backlog) → Task 4. ✓
- Geen wiki→memory seeding (keuze C) → nergens gebouwd. ✓

**Placeholder scan:** geen TBD/TODO; alle code + testcode volledig.

**Type consistency:** `run_sweep(..., ignore_watermark=False)` consistent; `cloud_warnings() -> list`, `rot_count(hours) -> int`, `notice() -> str` consistent tussen helper, doctor en notify; `_llm.providers()/CLOUD_PROVIDERS/_endpoint` matchen fase 4a.

**Geverifieerd vóór uitvoering:** `doctor.sh` heeft `report_pass`/`report_warn`/`report_fail`-helpers (gelezen); `distill-notify.py` is het SessionStart-hook-model; de heartbeat `memory-sweep-status.json` wordt door de sweep geschreven (fase 4b) met `model_unreachable`/`errors`; `_llm._endpoint("ollama")` + `CLOUD_PROVIDERS` bestaan (fase 4a).

**Aandachtspunt uitvoerder:** Task 1 — zorg dat de reachability-probe-guard `todo` gebruikt (niet `ss.pending()`), anders draait `--all` niet bij een lege watermark-achterstand. Task 2 — `rot_count` gebruikt `created` (datum) als proxy voor leeftijd; een dag-granulariteit is genoeg voor de 48u-drempel. Task 3 — `memory-notify` importeert `memory-doctor` via importlib (hyphen); bevestig het pad. Houd alle SessionStart-output fail-open.

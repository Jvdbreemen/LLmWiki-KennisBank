# KennisBank settings-systeem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maak vier achtergrond-automatieken (auto-archive, distill-notify, embed-index, daily-graphify) individueel aan/uit te zetten via een persistente settings-store, met een `/kennisbank:settings`-commando en interactieve uitvraag bij setup/upgrade.

**Architecture:** Eén platte JSON-store `$VAULT/kennisbank-settings.json` als bron van waarheid; gedeelde helper `scripts/_settings.py` (get/set/DEFAULTS + CLI) als enige lezer/schrijver; hook-scripts gaten zichzelf (lezen toggle, `exit 0` als uit) zonder de globale `~/.claude/settings.json` te herschrijven; de daily-graphify-gate zit in de command-markdown.

**Tech Stack:** Python 3 (stdlib only), bash (`setup.sh`), Claude Code command/skill-markdown, `unittest` (pytest-runner).

## Global Constraints

- Vault-root ALTIJD via `KENNISBANK_VAULT` (env) met fallback `~/KennisBank`, geresolved door `scripts/_vaultpath.vault_root()`. NOOIT een letterlijk `~/KennisBank`- of `C:\...`-pad. Regression-guard: `tests/test_vaultpath.py::test_no_script_hardcodes_the_vault`.
- Hook-scripts zijn FAIL-OPEN: elke fout eindigt met `exit 0`, een hook blokkeert nooit een sessie.
- Helper-modules hebben GEEN hyphen in de naam (`_settings.py`, `_vaultpath.py`), zodat ze importeerbaar zijn na `sys.path.insert`. Hyphenscripts worden in tests geladen via `tests/_loader.py::load_script`.
- Stdlib only in alle scripts. Geen externe dependencies.
- Taal: match de taal van het bestand dat je bewerkt. Code-commentaar, docs (`CONFIGURATION.md`, `CHANGELOG.md`, `README.md`, `POST-INSTALL.md`) en command-markdown (`commands/*.md`) zijn Nederlands. De skills (`skills/kennisbank-upgrade/SKILL.md`) zijn ENGELS: schrijf de toegevoegde stap daar in het Engels. GEEN em dashes (gebruik een streepje-met-spaties of een dubbele punt).
- Defaults (ongeconfigureerd of read/parse-fout): `auto_archive=False`, `distill_notify=True`, `embed_index=True`, `daily_graphify=True`.
- Command-markdown gebruikt `python3` in bash-blokken (zusterconventie, zie `destilleer.md`); `setup.sh` en de hooks gebruiken `py -3` op Windows.
- Tests gebruiken `unittest` met een temp-vault via `KENNISBANK_VAULT`; herstel env in `tearDown`/`finally` (anders lekt de var naar latere tests, zie `test_distill_notify.py::_run_main`).

---

### Task 1: `_settings.py` helper + voorbeeldbestand

**Files:**
- Create: `scripts/_settings.py`
- Create: `kennisbank-settings.example.json`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces:
  - `_settings.DEFAULTS: dict[str, bool]` — canonieke toggles + defaults.
  - `_settings.settings_path() -> Path` — `vault_root() / "kennisbank-settings.json"`.
  - `_settings.get(key: str, default: bool) -> bool` — fail-open lezer.
  - `_settings.set(key: str, value: bool) -> None` — atomische schrijver.
  - `_settings.init() -> bool` — schrijf defaults als afwezig; True als geschreven.
  - CLI: `python _settings.py get <key> [default]` (print `1`/`0`), `set <key> <1|0|true|false>`, `init` (print `written`/`exists`).

- [ ] **Step 1: Schrijf de falende tests**

`tests/test_settings.py`:

```python
"""Tests voor scripts/_settings.py — de toggle-store.

_settings.py heeft geen hyphen, dus het importeert direct zodra scripts/ op
sys.path staat (idem _vaultpath.py). De vault wordt per test naar een temp-map
gewezen via KENNISBANK_VAULT; de env wordt in tearDown hersteld zodat hij niet
naar latere tests lekt.
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
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _settings  # noqa: E402


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-set-"))
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

    def _write(self, text: str):
        (self.vault / "kennisbank-settings.json").write_text(text, encoding="utf-8")

    def test_get_missing_file_returns_default(self):
        self.assertTrue(_settings.get("embed_index", True))
        self.assertFalse(_settings.get("auto_archive", False))

    def test_get_corrupt_file_returns_default(self):
        self._write("{ this is not json")
        self.assertTrue(_settings.get("embed_index", True))

    def test_get_missing_key_returns_default(self):
        self._write(json.dumps({"embed_index": True}))
        self.assertFalse(_settings.get("auto_archive", False))

    def test_get_reads_stored_value(self):
        self._write(json.dumps({"auto_archive": True}))
        self.assertTrue(_settings.get("auto_archive", False))

    def test_set_then_get_roundtrip(self):
        _settings.set("auto_archive", True)
        self.assertTrue(_settings.get("auto_archive", False))
        _settings.set("auto_archive", False)
        self.assertFalse(_settings.get("auto_archive", True))

    def test_set_preserves_unknown_keys(self):
        self._write(json.dumps({"some_future_key": 42}))
        _settings.set("auto_archive", True)
        data = json.loads((self.vault / "kennisbank-settings.json").read_text(encoding="utf-8"))
        self.assertEqual(data["some_future_key"], 42)
        self.assertTrue(data["auto_archive"])

    def test_init_writes_defaults_when_absent(self):
        self.assertTrue(_settings.init())
        data = json.loads((self.vault / "kennisbank-settings.json").read_text(encoding="utf-8"))
        self.assertEqual(data, _settings.DEFAULTS)

    def test_init_is_noop_when_present(self):
        self._write(json.dumps({"auto_archive": True}))
        self.assertFalse(_settings.init())
        data = json.loads((self.vault / "kennisbank-settings.json").read_text(encoding="utf-8"))
        self.assertEqual(data, {"auto_archive": True})

    def test_settings_path_honors_env(self):
        self.assertEqual(_settings.settings_path(), self.vault / "kennisbank-settings.json")

    # --- CLI ---
    def _cli(self, *args):
        env = dict(os.environ)
        env["KENNISBANK_VAULT"] = str(self.vault)
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "_settings.py"), *args],
            env=env, capture_output=True, text=True,
        )

    def test_cli_get_default(self):
        r = self._cli("get", "embed_index")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "1")
        r = self._cli("get", "auto_archive")
        self.assertEqual(r.stdout.strip(), "0")

    def test_cli_set_then_get(self):
        self._cli("set", "auto_archive", "true")
        r = self._cli("get", "auto_archive")
        self.assertEqual(r.stdout.strip(), "1")

    def test_cli_init(self):
        r = self._cli("init")
        self.assertEqual(r.stdout.strip(), "written")
        r = self._cli("init")
        self.assertEqual(r.stdout.strip(), "exists")

    def test_example_matches_defaults(self):
        example = Path(__file__).resolve().parent.parent / "kennisbank-settings.example.json"
        data = json.loads(example.read_text(encoding="utf-8"))
        self.assertEqual(set(data.keys()), set(_settings.DEFAULTS.keys()))
        self.assertEqual(data, _settings.DEFAULTS)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run de tests, verifieer dat ze falen**

Run: `python -m pytest tests/test_settings.py -v`
Expected: FAIL met `ModuleNotFoundError: No module named '_settings'` (en de example-test faalt op een ontbrekend bestand).

- [ ] **Step 3: Schrijf `scripts/_settings.py`**

```python
#!/usr/bin/env python3
"""_settings.py — KennisBank achtergrond-automatiek toggles.

Eén plat JSON-bestand op $VAULT/kennisbank-settings.json is de bron van waarheid
voor welke achtergrond-automatiek draait. get()/set() zijn de enige lezer en
schrijver, zodat key-namen en formaat nergens driften.

Fail-open op lezen: ontbrekend bestand, ongeldige JSON of een ontbrekende key
geeft de meegegeven default terug, nooit een exceptie. Stdlib only, geen hyphen
in de naam zodat scripts het kunnen importeren na sys.path.insert (idem
_vaultpath.py).

CLI:
    python _settings.py get <key> [default]   -> print 1/0, exit 0
    python _settings.py set <key> <1|0|true|false>
    python _settings.py init                   -> schrijf defaults als afwezig
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Self-locate de vault als KENNISBANK_VAULT ontbreekt (idem aan de hookscripts).
# Dit script woont in <vault>/.claude/scripts/, dus parents[2] == <vault>.
os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

FILENAME = "kennisbank-settings.json"

# Canonieke toggles en hun default als de key (of het bestand) ontbreekt.
# Eén bron voor het command, setup.sh en de upgrade-skill.
DEFAULTS = {
    "auto_archive": False,
    "distill_notify": True,
    "embed_index": True,
    "daily_graphify": True,
}

_TRUTHY = ("1", "true", "yes", "y", "on")


def settings_path() -> Path:
    return vault_root() / FILENAME


def _load() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(key: str, default: bool) -> bool:
    """Lees een toggle. Ontbrekend bestand/key of parse-fout -> default."""
    return bool(_load().get(key, default))


def set(key: str, value: bool) -> None:
    """Schrijf een toggle atomisch (tempfile + os.replace). Behoudt onbekende
    keys zodat een nieuwere store-versie niet kapot gaat op een oudere schrijver."""
    data = _load()
    data[key] = bool(value)
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".kbset-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, p)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def init() -> bool:
    """Schrijf het defaults-bestand als het nog niet bestaat. Return True als
    geschreven, False als het al bestond."""
    p = settings_path()
    if p.exists():
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(DEFAULTS), indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return True


def _cli(argv: list[str]) -> int:
    if not argv:
        print("usage: _settings.py get|set|init ...", file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "get":
        if len(argv) < 2:
            print("usage: _settings.py get <key> [default]", file=sys.stderr)
            return 2
        key = argv[1]
        default = DEFAULTS.get(key, False)
        if len(argv) >= 3:
            default = argv[2].lower() in _TRUTHY
        print("1" if get(key, default) else "0")
        return 0
    if cmd == "set":
        if len(argv) < 3:
            print("usage: _settings.py set <key> <1|0|true|false>", file=sys.stderr)
            return 2
        set(argv[1], argv[2].lower() in _TRUTHY)
        return 0
    if cmd == "init":
        print("written" if init() else "exists")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Schrijf `kennisbank-settings.example.json`**

```json
{
  "auto_archive": false,
  "distill_notify": true,
  "embed_index": true,
  "daily_graphify": true
}
```

- [ ] **Step 5: Run de tests, verifieer dat ze slagen**

Run: `python -m pytest tests/test_settings.py -v`
Expected: PASS (alle tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/_settings.py kennisbank-settings.example.json tests/test_settings.py
git commit -m "feat(settings): _settings.py toggle-store met get/set/init + CLI"
```

---

### Task 2: Self-gate `archive-transcript.py` op `auto_archive`

**Files:**
- Modify: `scripts/archive-transcript.py` (in `main()`, na het lezen van stdin)
- Test: `tests/test_archive_transcript.py` (twee tests toevoegen)

**Interfaces:**
- Consumes: `_settings.get("auto_archive", False)` uit Task 1.
- Produces: geen nieuwe symbolen; `main()` gate-gedrag.

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_archive_transcript.py` binnen `class ArchiveTest`:

```python
    def _hook_stdin(self, src):
        return json.dumps({"transcript_path": str(src),
                           "session_id": "ABCDEF1234567890",
                           "cwd": "/home/u/myproject"})

    def _run_main(self, stdin_text):
        import io, os
        old_in, old_env = sys.stdin, os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        sys.stdin = io.StringIO(stdin_text)
        try:
            return mod.main()
        finally:
            sys.stdin = old_in
            if old_env is None:
                os.environ.pop("KENNISBANK_VAULT", None)
            else:
                os.environ["KENNISBANK_VAULT"] = old_env

    def test_main_skips_when_auto_archive_off(self):
        # Geen settings-bestand -> auto_archive default False -> niets archiveren.
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        rc = self._run_main(self._hook_stdin(src))
        self.assertEqual(rc, 0)
        tdir = self.vault / "01-raw" / "transcripts"
        self.assertEqual(list(tdir.glob("*.jsonl")) if tdir.exists() else [], [])

    def test_main_archives_when_auto_archive_on(self):
        (self.vault).mkdir(parents=True, exist_ok=True)
        (self.vault / "kennisbank-settings.json").write_text(
            '{"auto_archive": true}', encoding="utf-8")
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        rc = self._run_main(self._hook_stdin(src))
        self.assertEqual(rc, 0)
        files = list((self.vault / "01-raw" / "transcripts").glob("*.jsonl"))
        self.assertEqual(len(files), 1)
```

- [ ] **Step 2: Run de tests, verifieer dat ze falen**

Run: `python -m pytest tests/test_archive_transcript.py -k auto_archive -v`
Expected: `test_main_skips_when_auto_archive_off` FAILt (er wordt nog wel gearchiveerd want er is nog geen gate).

- [ ] **Step 3: Voeg de gate toe in `main()`**

In `scripts/archive-transcript.py`, na het stdin-parse-blok en VOOR `result = archive(...)`, voeg toe:

```python
    # Toggle-gate: archiveer alleen als auto_archive aanstaat. Fail-open: kan de
    # toggle niet gelezen worden, val terug op de default (False = uit).
    try:
        import _settings
        enabled = _settings.get("auto_archive", False)
    except Exception:
        enabled = False
    if not enabled:
        return 0
```

De volledige `main()` wordt daarmee:

```python
def main() -> int:
    try:
        raw = sys.stdin.read()
        hook = json.loads(raw) if raw.strip() else {}
        if not isinstance(hook, dict):
            hook = {}
    except (json.JSONDecodeError, OSError, ValueError):
        hook = {}
    # Toggle-gate: archiveer alleen als auto_archive aanstaat. Fail-open: kan de
    # toggle niet gelezen worden, val terug op de default (False = uit).
    try:
        import _settings
        enabled = _settings.get("auto_archive", False)
    except Exception:
        enabled = False
    if not enabled:
        return 0
    try:
        result = archive(hook, vault_root())
    except Exception as e:  # fail-open
        print(f"[archive-transcript] unexpected: {e}", file=sys.stderr)
        return 0
    if result.get("status") == "error":
        print(f"[archive-transcript] {result.get('reason')}", file=sys.stderr)
    return 0
```

- [ ] **Step 4: Run de tests, verifieer dat ze slagen**

Run: `python -m pytest tests/test_archive_transcript.py -v`
Expected: PASS (alle, inclusief de bestaande `archive()`-tests die ongewijzigd blijven).

- [ ] **Step 5: Commit**

```bash
git add scripts/archive-transcript.py tests/test_archive_transcript.py
git commit -m "feat(settings): gate archive-transcript op auto_archive toggle"
```

---

### Task 3: Self-gate `distill-notify.py` SessionStart-meldpad op `distill_notify`

**Files:**
- Modify: `scripts/distill-notify.py` (in `main()`, alleen het argument-loze meldpad)
- Test: `tests/test_distill_notify.py` (twee tests toevoegen)

**Interfaces:**
- Consumes: `_settings.get("distill_notify", True)` uit Task 1.
- Produces: geen nieuwe symbolen. `--mark`/`--list-pending` blijven ongegate.

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_distill_notify.py` binnen `class DistillNotifyTest`:

```python
    def _write_settings(self, text):
        self.vault.mkdir(parents=True, exist_ok=True)
        (self.vault / "kennisbank-settings.json").write_text(text, encoding="utf-8")

    def test_notify_silent_when_toggle_off(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self._write_settings('{"distill_notify": false}')
        rc, out = self._run_main(["distill-notify.py"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")

    def test_list_pending_works_even_when_toggle_off(self):
        # De handmatige /destilleer-paden mogen NIET gate-en op de melding.
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self._write_settings('{"distill_notify": false}')
        rc, out = self._run_main(["distill-notify.py", "--list-pending"])
        self.assertEqual(out.strip(), "2026-06-24-a-aaaa1111")
```

- [ ] **Step 2: Run de tests, verifieer dat ze falen**

Run: `python -m pytest tests/test_distill_notify.py -k toggle -v`
Expected: `test_notify_silent_when_toggle_off` FAILt (de melding wordt nog steeds geëmit).

- [ ] **Step 3: Voeg de gate toe in `main()`**

In `scripts/distill-notify.py`, vervang de regel `_emit_notify(len(pending(vault)))` door een gegate variant. De `--mark`/`--list-pending`-takken blijven ervoor en zijn dus NIET gegate:

```python
        if argv and argv[0] == "--list-pending":
            for s in pending(vault):
                print(s)
            return 0
        # Alleen het SessionStart-meldpad gate-t op distill_notify. De
        # --mark/--list-pending subcommando's hierboven draaien altijd, zodat
        # /destilleer blijft werken als de melding uit staat. Fail-open: kan de
        # toggle niet gelezen worden, val terug op de default (True = aan).
        try:
            import _settings
            notify = _settings.get("distill_notify", True)
        except Exception:
            notify = True
        if notify:
            _emit_notify(len(pending(vault)))
```

- [ ] **Step 4: Run de tests, verifieer dat ze slagen**

Run: `python -m pytest tests/test_distill_notify.py -v`
Expected: PASS (alle, inclusief de bestaande melding/mark/list-tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/distill-notify.py tests/test_distill_notify.py
git commit -m "feat(settings): gate distill-notify meldpad op distill_notify toggle"
```

---

### Task 4: Self-gate `build-embed-index.py` op `embed_index`

**Files:**
- Modify: `scripts/build-embed-index.py` (vooraan in `main()`)
- Test: `tests/test_build_embed_index_gate.py` (nieuw)

**Interfaces:**
- Consumes: `_settings.get("embed_index", True)` uit Task 1.
- Produces: geen nieuwe symbolen. Gate zit VOOR de `.needs-rebuild`-clear.

- [ ] **Step 1: Schrijf de falende test**

`tests/test_build_embed_index_gate.py`:

```python
"""Gate-test voor build-embed-index.py op de embed_index toggle.

Met de toggle uit moet main() vroeg terugkeren ZONDER neveneffect. We bewijzen
dat via de graphify .needs-rebuild-flag: main() leegt die normaal, dus als de
flag na een run nog bestaat is main() ervoor afgehaakt. Geen embedding-backend
nodig: de gate zit vóór elke embed-call.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script


class EmbedIndexGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-embgate-"))
        self.vault = self.tmp / "vault"
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / "02-wiki" / "a.md").write_text("# a\ntekst", encoding="utf-8")
        self.rebuild = self.vault / "graphify-out" / ".needs-rebuild"
        self.rebuild.parent.mkdir(parents=True)
        self.rebuild.write_text("02-wiki/a.md\n", encoding="utf-8")
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_gate_off_leaves_rebuild_flag(self):
        (self.vault / "kennisbank-settings.json").write_text(
            '{"embed_index": false}', encoding="utf-8")
        mod = load_script("build-embed-index.py")
        mod.main()
        self.assertTrue(self.rebuild.exists(),
                        "main() mag de flag niet legen als embed_index uit staat")


if __name__ == "__main__":
    unittest.main()
```

> NB: `build-embed-index.py` resolvet `VAULT`/`REBUILD_FLAG` als module-globals bij import. Daarom wordt `KENNISBANK_VAULT` in `setUp` gezet VOORDAT `load_script` het script exect. `load_script` exect elke aanroep vers, dus de globals pakken de temp-vault.

- [ ] **Step 2: Run de test, verifieer dat hij faalt**

Run: `python -m pytest tests/test_build_embed_index_gate.py -v`
Expected: FAIL (zonder gate leegt main() de flag, of probeert te embedden; de assert op een nog-bestaande flag faalt).

- [ ] **Step 3: Voeg de gate toe vooraan in `main()`**

In `scripts/build-embed-index.py`, als ALLEReerste regels van `def main() -> None:`:

```python
def main() -> None:
    # Toggle-gate: ververs de embed-index alleen als embed_index aanstaat.
    # Fail-open: kan de toggle niet gelezen worden, val terug op de default
    # (True = aan). De gate zit vóór de .needs-rebuild-clear en elke embed-call.
    try:
        import _settings
        if not _settings.get("embed_index", True):
            print("embed-index: uitgeschakeld via settings (embed_index=false)")
            return
    except Exception:
        pass
    if not WIKI.exists():
        print("embed-index: geen 02-wiki/, overgeslagen")
        return
    ...
```

(De bestaande body vanaf `if not WIKI.exists()` blijft ongewijzigd.)

- [ ] **Step 4: Run de test, verifieer dat hij slaagt**

Run: `python -m pytest tests/test_build_embed_index_gate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/build-embed-index.py tests/test_build_embed_index_gate.py
git commit -m "feat(settings): gate build-embed-index op embed_index toggle"
```

---

### Task 5: `/kennisbank:settings`-commando + subdir-deploy in `setup.sh`

**Files:**
- Create: `commands/kennisbank/settings.md`
- Modify: `setup.sh` (command-deploy: extra subdir-loop in beide takken)
- Test: `tests/test_setup_deploy.py` (één test toevoegen)

**Interfaces:**
- Consumes: `_settings.get/set` (Task 1) vanuit de command-markdown via `python3`.
- Produces: deployt naar `$HOME/.claude/commands/kennisbank/settings.md` -> slash `/kennisbank:settings`.

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `tests/test_setup_deploy.py` binnen `class SetupDeployTest`:

```python
    def test_settings_command_deploys_to_subdir(self):
        tmp, vault = self.run_setup()
        try:
            cmd = tmp / ".claude" / "commands" / "kennisbank" / "settings.md"
            self.assertTrue(cmd.is_file(),
                            f"/kennisbank:settings niet gedeployed op {cmd}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 2: Run de test, verifieer dat hij faalt**

Run: `python -m pytest tests/test_setup_deploy.py -k settings_command -v`
Expected: FAIL (flat glob `commands/*.md` neemt de subdir niet mee; bestand ontbreekt). Mogelijk SKIP als er geen Git Bash is — draai dan op een machine mét Git Bash.

- [ ] **Step 3: Schrijf `commands/kennisbank/settings.md`**

```markdown
Beheer de KennisBank achtergrond-automatiek: zet toggles aan of uit en leg de keuze vast.

## Vault-root bepalen (VERPLICHT: lees dit eerst)

Bepaal de vault-root EEN keer en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik NOOIT een letterlijk pad. De helper staat in `$VAULT/.claude/scripts/_settings.py`.

## Doel
De vier achtergrond-automatieken zijn opt-in/opt-out. Dit commando toont de
huidige staat, laat je toggles wijzigen en schrijft de keuze naar
`$VAULT/kennisbank-settings.json` (bron van waarheid, gelezen door de hooks en de
dagelijkse graphify-gate).

## Stap 1: Lees de huidige staat
Lees per toggle de waarde via de helper. Gebruik de canonieke keys en hun default:

```bash
for key in auto_archive distill_notify embed_index daily_graphify; do
  val=$(python3 "$VAULT/.claude/scripts/_settings.py" get "$key")
  echo "$key=$val"
done
```

`1` = aan, `0` = uit. Bestaat het bestand nog niet, dan geeft de helper de
defaults (auto_archive uit, de rest aan).

## Stap 2: Toon de toggles en vraag de gewenste staat
Toon een nette tabel met per toggle de naam, huidige staat (aan/uit) en wat hij
doet:

- **auto_archive** — archiveer elk transcript bij sessie-einde naar `01-raw/transcripts/` (voer hierna `/destilleer` uit). Uit = geen archief; gebruik `/sessielog` handmatig.
- **distill_notify** — meld bij sessiestart hoeveel transcripts op `/destilleer` wachten.
- **embed_index** — ververs de wiki-embeddingcache bij sessiestart (voor prompt-time retrieval). Uit = retrieval draait op een oudere cache.
- **daily_graphify** — draai 1x/dag automatisch `/graphify --update` (kost-gated op 20u). Uit = alleen `.needs-rebuild` bijhouden; draai de graph handmatig.

Vraag de gebruiker via `AskUserQuestion` (multiSelect) welke toggles AAN moeten
staan. Vink vooraf exact de toggles aan die nu `1` zijn (uit stap 1), zodat de
gebruiker alleen het verschil hoeft te kiezen.

## Stap 3: Schrijf de keuze terug
Voor ELKE canonieke toggle: aangevinkt -> `true`, niet-aangevinkt -> `false`.
Schrijf via de helper (maakt het bestand aan als het nog niet bestaat):

```bash
python3 "$VAULT/.claude/scripts/_settings.py" set auto_archive   <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set distill_notify <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set embed_index    <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set daily_graphify <true|false>
```

## Bevestiging
Toon de nieuwe staat (herhaal stap 1) en benoem expliciet welke automatiek nu
aan en welke uit staat. Vermeld dat hook-toggles pas effect hebben vanaf de
volgende sessie (de hooks lezen de store bij hun volgende run).

## Regels
- Schrijf NOOIT direct JSON; gebruik altijd `_settings.py set`, zodat key-namen en formaat consistent blijven.
- Taal: volgt de prompt. Geen em dashes.
```

- [ ] **Step 4: Pas `setup.sh` aan voor subdir-deploy**

In `setup.sh`, in de `--yes`-tak, NA de bestaande `for f in commands/*.md`-loop, voeg de subdir-loop toe:

```bash
    for f in commands/*.md; do
      copy_file "$f" "$CLAUDE_COMMANDS/$(basename "$f")"
    done
    # Genamespacede commands (bv. commands/kennisbank/settings.md -> /kennisbank:settings)
    for f in commands/*/*.md; do
      rel="${f#commands/}"
      mkdir -p "$CLAUDE_COMMANDS/$(dirname "$rel")"
      copy_file "$f" "$CLAUDE_COMMANDS/$rel"
    done
```

En IDENTIEK in de interactieve tak (binnen het `if [ "$REPLY" = "y" ] ...`-blok), na de bestaande flat-loop:

```bash
    mkdir -p "$CLAUDE_COMMANDS"
    for f in commands/*.md; do
      copy_file "$f" "$CLAUDE_COMMANDS/$(basename "$f")"
    done
    for f in commands/*/*.md; do
      rel="${f#commands/}"
      mkdir -p "$CLAUDE_COMMANDS/$(dirname "$rel")"
      copy_file "$f" "$CLAUDE_COMMANDS/$rel"
    done
```

`nullglob` is al gezet (regel `shopt -s nullglob`), dus een lege match is veilig.

- [ ] **Step 5: Run de test, verifieer dat hij slaagt**

Run: `python -m pytest tests/test_setup_deploy.py -v`
Expected: PASS (nieuwe + bestaande deploy-tests). SKIP alleen als er geen Git Bash is.

- [ ] **Step 6: Commit**

```bash
git add commands/kennisbank/settings.md setup.sh tests/test_setup_deploy.py
git commit -m "feat(settings): /kennisbank:settings commando + subdir-deploy in setup.sh"
```

---

### Task 6: Settings-bootstrap in `setup.sh`

**Files:**
- Modify: `setup.sh` (na de scripts-deploy: settings-bestand bootstrappen)
- Test: `tests/test_setup_deploy.py` (één test toevoegen)

**Interfaces:**
- Consumes: `_settings.py init` (Task 1), gedeployed naar `$VAULT/.claude/scripts/_settings.py`.
- Produces: `$VAULT/kennisbank-settings.json` met defaults bij niet-interactieve setup.

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `tests/test_setup_deploy.py` binnen `class SetupDeployTest`:

```python
    def test_settings_file_bootstrapped_with_defaults(self):
        import json
        tmp, vault = self.run_setup()  # run_setup gebruikt --yes (niet-interactief)
        try:
            sf = vault / "kennisbank-settings.json"
            self.assertTrue(sf.is_file(), "settings-bestand niet aangemaakt door setup")
            data = json.loads(sf.read_text(encoding="utf-8"))
            self.assertEqual(data["auto_archive"], False)
            self.assertEqual(data["distill_notify"], True)
            self.assertEqual(data["embed_index"], True)
            self.assertEqual(data["daily_graphify"], True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 2: Run de test, verifieer dat hij faalt**

Run: `python -m pytest tests/test_setup_deploy.py -k bootstrapped -v`
Expected: FAIL (settings-bestand wordt nog niet aangemaakt).

- [ ] **Step 3: Voeg de bootstrap toe in `setup.sh`**

In `setup.sh`, NA het scripts-deploy-blok (na `copy_file kennisbank-embed.example.json ...`, zodat `_settings.py` al in de vault staat), voeg toe:

```bash
# Settings-bootstrap: zorg dat kennisbank-settings.json bestaat. De toggles
# bepalen welke achtergrond-automatiek draait (auto-archive, distill-notify,
# embed-index, daily-graphify). Interactief vragen we per toggle; niet-
# interactief (--yes of geen TTY) schrijven we de defaults.
SETTINGS_FILE="$VAULT/kennisbank-settings.json"
if [ -f "$SETTINGS_FILE" ]; then
  echo "  behouden: $SETTINGS_FILE (bestaat al)"
elif [ "$ASSUME_YES" = "1" ] || [ ! -t 0 ]; then
  py -3 "$VAULT/.claude/scripts/_settings.py" init >/dev/null \
    && echo "  settings: defaults geschreven naar $SETTINGS_FILE (draai /kennisbank:settings om aan te passen)"
else
  echo "Achtergrond-automatiek instellen (Enter = default):"
  # auto_archive default uit, de rest aan. read met default-hint.
  ask_toggle() {
    local key="$1" prompt="$2" def="$3" reply
    printf "  %s [%s] (y/n) " "$prompt" "$([ "$def" = "1" ] && echo "Y/n" || echo "y/N")"
    read reply
    if [ -z "$reply" ]; then reply="$def"; fi
    case "$reply" in
      y|Y|1) py -3 "$VAULT/.claude/scripts/_settings.py" set "$key" true >/dev/null ;;
      *)     py -3 "$VAULT/.claude/scripts/_settings.py" set "$key" false >/dev/null ;;
    esac
  }
  ask_toggle auto_archive   "transcripts archiveren bij sessie-einde (auto_archive)" 0
  ask_toggle distill_notify "melden bij start dat transcripts wachten (distill_notify)" 1
  ask_toggle embed_index    "wiki-embeddings verversen bij start (embed_index)" 1
  ask_toggle daily_graphify "1x/dag graph automatisch bijwerken (daily_graphify)" 1
  echo "  settings: keuze opgeslagen in $SETTINGS_FILE"
fi
```

> NB: gebruikt `py -3` (Windows-launcher) consistent met de hook-aanroepen in `~/.claude/settings.json`. Op macOS/Linux is `py -3` niet aanwezig; daar gebruikt setup.sh elders ook al Python via de scripts. Als deze repo ooit op een POSIX-host wordt gesetupt, vervang `py -3` door `python3`. (Plan-aanname: primaire host is Windows, zoals de bestaande hooks tonen.)

- [ ] **Step 4: Run de test, verifieer dat hij slaagt**

Run: `python -m pytest tests/test_setup_deploy.py -v`
Expected: PASS (alle deploy-tests). De `--yes`-run schrijft de defaults via de niet-interactieve tak.

- [ ] **Step 5: Commit**

```bash
git add setup.sh tests/test_setup_deploy.py
git commit -m "feat(settings): bootstrap kennisbank-settings.json in setup.sh"
```

---

### Task 7: Daily-graphify-gate in command-markdown

**Files:**
- Modify: `commands/sessielog.md` (Stap 2 item 5)
- Modify: `commands/wiki.md` (graphify-batch-verwijzing in Stappen)
- Modify: `commands/destilleer.md` (Stap 3)
- Test: `tests/test_command_settings_gates.py` (nieuw, grep-guard)

**Interfaces:**
- Consumes: `_settings.get("daily_graphify", True)` via `python3` in de command-bash.
- Produces: geen code-symbolen; instructie-gedrag.

- [ ] **Step 1: Schrijf de falende grep-guard test**

`tests/test_command_settings_gates.py`:

```python
"""Guard: de daily-graphify-gate moet in de command-markdown verankerd staan.

Dit is geen gedragstest (markdown is instructie, geen code) maar een regression-
guard dat de toggle-naam niet stilletjes uit de commands verdwijnt bij een
herschrijving.
"""
from __future__ import annotations

import unittest
from pathlib import Path

COMMANDS = Path(__file__).resolve().parent.parent / "commands"


class CommandGateTest(unittest.TestCase):
    def _assert_mentions(self, name):
        text = (COMMANDS / name).read_text(encoding="utf-8")
        self.assertIn("daily_graphify", text,
                      f"{name} noemt de daily_graphify-gate niet")

    def test_sessielog_has_gate(self):
        self._assert_mentions("sessielog.md")

    def test_wiki_has_gate(self):
        self._assert_mentions("wiki.md")

    def test_destilleer_has_gate(self):
        self._assert_mentions("destilleer.md")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run de test, verifieer dat hij faalt**

Run: `python -m pytest tests/test_command_settings_gates.py -v`
Expected: FAIL (de commands noemen `daily_graphify` nog niet).

- [ ] **Step 3: Voeg de gate toe in `commands/sessielog.md`**

In Stap 2, item 5, NA de zin "ALTIJD eerst: voeg de gewijzigde/nieuwe wiki-paden toe aan `$VAULT/graphify-out/.needs-rebuild` (goedkoop, geen LLM)." en VOOR "DAN de dag-gate op de mtime ...", voeg een toggle-check in:

```markdown
   Lees daarna de `daily_graphify`-toggle:
   ```bash
   DG=$(python3 -c "import sys; sys.path.insert(0,'$VAULT/.claude/scripts'); import _settings; print('1' if _settings.get('daily_graphify', True) else '0')")
   ```
   - `daily_graphify` UIT (`DG=0`): sla de automatische `--update` deze sessie over. `.needs-rebuild` is al bijgewerkt (gratis). Meld "auto-graph uit via settings; draai handmatig `/graphify $VAULT --update`". Sla ook item 6 (auto-crosslinks) over en ga naar item 7.
   - `daily_graphify` AAN (`DG=1`): volg de bestaande dag-gate hieronder.
```

(De bestaande dag-gate-bullets blijven daaronder ongewijzigd.)

- [ ] **Step 4: Voeg de gate toe in `commands/destilleer.md`**

In Stap 3 "Compileer tot wiki", waar staat "draai de dagelijkse graphify-batch en semantische tiling zoals `/wiki` voorschrijft", voeg een zin toe:

```markdown
De dagelijkse graphify-batch respecteert de `daily_graphify`-toggle: staat die
uit (`python3 -c "import sys; sys.path.insert(0,'$VAULT/.claude/scripts'); import _settings; print(_settings.get('daily_graphify', True))"` geeft `False`), werk dan alleen `.needs-rebuild` bij en sla de automatische `/graphify --update` over.
```

- [ ] **Step 5: Voeg de gate toe in `commands/wiki.md`**

In `commands/wiki.md`, Stap 4/5-gebied (waar graphify/crosslinks impliciet meelopen), voeg een expliciete regel toe onder "## Regels":

```markdown
- Dagelijkse graphify-batch respecteert de `daily_graphify`-toggle in `kennisbank-settings.json`: staat die uit, werk alleen `$VAULT/graphify-out/.needs-rebuild` bij en draai geen automatische `/graphify --update`. Lezen: `python3 -c "import sys; sys.path.insert(0,'$VAULT/.claude/scripts'); import _settings; print(_settings.get('daily_graphify', True))"`.
```

- [ ] **Step 6: Run de test, verifieer dat hij slaagt**

Run: `python -m pytest tests/test_command_settings_gates.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add commands/sessielog.md commands/wiki.md commands/destilleer.md tests/test_command_settings_gates.py
git commit -m "feat(settings): daily-graphify-gate in sessielog/wiki/destilleer"
```

---

### Task 8: `kennisbank-upgrade`-skill vraagt ontbrekende settings uit

**Files:**
- Modify: `skills/kennisbank-upgrade/SKILL.md`
- Test: `tests/test_skill_frontmatter.py` (bestaande test moet blijven slagen; geen nieuwe code-test, wel een grep-guard toevoegen)

**Interfaces:**
- Consumes: `_settings.py get/set/init` (Task 1).
- Produces: instructie-stap; geen code-symbolen.

- [ ] **Step 1: Lees de huidige skill en het frontmatter-testcontract**

Run: `python -m pytest tests/test_skill_frontmatter.py -v` (moet PASS zijn vóór de wijziging)
Lees `skills/kennisbank-upgrade/SKILL.md` om de bestaande stappenstructuur en de frontmatter (name/description) te respecteren.

- [ ] **Step 2: Schrijf de falende grep-guard**

Voeg een test toe (`tests/test_command_settings_gates.py`, hergebruik het bestand uit Task 7):

```python
    def test_upgrade_skill_ensures_settings(self):
        skill = Path(__file__).resolve().parent.parent / "skills" / "kennisbank-upgrade" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertIn("kennisbank-settings.json", text,
                      "upgrade-skill garandeert het settings-bestand niet")
```

- [ ] **Step 3: Run de guard, verifieer dat hij faalt**

Run: `python -m pytest tests/test_command_settings_gates.py -k upgrade -v`
Expected: FAIL.

- [ ] **Step 4: Voeg een settings-stap toe aan `SKILL.md` (in het ENGELS, matcht de bestaande skill-taal)**

Voeg, na de bestaande deploy/sync-stappen en VOOR de afsluiting, een stap toe (pas de stapnummering aan de bestaande nummering/koppenstijl aan):

```markdown
## Ensure settings and ask for missing toggles

Resolve `VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`.

Existing installs may not have a `kennisbank-settings.json` yet. Read each
canonical toggle's current value:

```bash
for key in auto_archive distill_notify embed_index daily_graphify; do
  echo "$key=$(python3 "$VAULT/.claude/scripts/_settings.py" get "$key")"
done
```

If the file does not exist yet (every value falls back to its default and
`$VAULT/kennisbank-settings.json` is absent), ask the user PER toggle whether to
enable it, suggesting the default:

- auto_archive (default OFF) - archive the transcript at session end
- distill_notify (default ON) - notify at start that transcripts are pending
- embed_index (default ON) - refresh the wiki embedding cache at start
- daily_graphify (default ON) - update the graph automatically once a day

Write each choice with `python3 "$VAULT/.claude/scripts/_settings.py" set <key> <true|false>`.
Do NOT re-ask keys that are already set. Mention afterwards that the user can
change this later with `/kennisbank:settings`.

BEHAVIOUR CHANGE: after this upgrade the hook only archives when `auto_archive`
is ON. Ask for it explicitly, otherwise the transcript archive stops silently.
```

- [ ] **Step 5: Run de guard + frontmatter-test, verifieer dat ze slagen**

Run: `python -m pytest tests/test_command_settings_gates.py tests/test_skill_frontmatter.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/kennisbank-upgrade/SKILL.md tests/test_command_settings_gates.py
git commit -m "feat(settings): upgrade-skill vraagt ontbrekende toggles uit"
```

---

### Task 9: Documentatie

**Files:**
- Modify: `CONFIGURATION.md` (nieuwe sectie over de settings-store en toggles)
- Modify: `CHANGELOG.md` (Unreleased: Added/Changed, incl. gedragswijziging)
- Modify: `README.md` (kort: `/kennisbank:settings` en de toggles)
- Modify: `POST-INSTALL.md` (kort: bootstrap-stap)

**Interfaces:**
- Consumes: alle voorgaande taken (documenteert hun gedrag).
- Produces: geen code.

- [ ] **Step 1: Voeg een sectie toe aan `CONFIGURATION.md`**

Plaats een nieuwe genummerde sectie (in de bestaande nummering) met deze inhoud:

```markdown
## N. Achtergrond-automatiek (settings-toggles)

Vier achtergrond-automatieken zijn individueel aan/uit te zetten via
`$VAULT/kennisbank-settings.json` (bron van waarheid, gelezen door
`scripts/_settings.py`).

| toggle | default | effect aan | effect uit |
|--------|---------|-----------|-----------|
| `auto_archive` | uit | SessionEnd archiveert het transcript naar `01-raw/transcripts/` | geen archief; gebruik `/sessielog` handmatig |
| `distill_notify` | aan | SessionStart meldt openstaande transcripts | geen melding; `/destilleer` blijft handmatig werken |
| `embed_index` | aan | SessionStart ververst de wiki-embeddingcache | retrieval draait op de bestaande (oudere) cache |
| `daily_graphify` | aan | 1x/dag automatisch `/graphify --update` (kost-gated op 20u) | alleen `.needs-rebuild` bijhouden; graph handmatig |

- **Wijzigen**: draai `/kennisbank:settings` (toont een tabel en zet toggles aan/uit), of bewerk het JSON-bestand (waarden zijn JSON-booleans).
- **Self-gating**: de hooks blijven statisch geregistreerd in `~/.claude/settings.json`; elk hookscript leest zijn toggle en eindigt fail-open (`exit 0`) als hij uit staat. Een toggle-wijziging werkt vanaf de volgende sessie.
- **Defaults bij ontbreken**: ontbreekt het bestand of een key, dan geldt de default-kolom hierboven. `setup` en `upgrade` schrijven expliciete waarden.
- **Interactie**: met `embed_index` uit wordt `graphify-out/.needs-rebuild` niet bij SessionStart geleegd; dat is benign, de flag wordt door de graphify-rebuild zelf geleegd.
```

- [ ] **Step 2: Voeg CHANGELOG-regels toe onder `## [Unreleased]`**

```markdown
### Added
- **Settings-store (`scripts/_settings.py`, `kennisbank-settings.json`).** Vier achtergrond-automatieken (auto-archive, distill-notify, embed-index, daily-graphify) zijn individueel aan/uit via een platte JSON-store. Gedeelde `get/set/init`-helper plus CLI; enige lezer/schrijver, geen key-drift.
- **`/kennisbank:settings`-commando.** Toont de toggles met huidige staat en zet ze aan/uit (genamespacet, deployt naar `~/.claude/commands/kennisbank/settings.md`).
- **Settings-bootstrap in `setup.sh` en de `kennisbank-upgrade`-skill.** Verse setup schrijft defaults (of vraagt interactief); upgrade vraagt ontbrekende toggles uit.

### Changed
- **Hooks gaten zichzelf op hun toggle.** `archive-transcript.py` (auto_archive), `distill-notify.py`-meldpad (distill_notify) en `build-embed-index.py` (embed_index) eindigen fail-open als hun toggle uit staat. De daily-graphify-batch in `sessielog`/`wiki`/`destilleer` respecteert `daily_graphify`.
- **`setup.sh` deployt nu ook genamespacede commands** (`commands/*/*.md`) met behoud van de subdir-structuur.

### Behaviour change
- **`auto_archive` is default UIT.** Bestaande installaties stoppen na deze update met automatisch archiveren tot `auto_archive` expliciet aan wordt gezet. De `kennisbank-upgrade`-skill vraagt dit actief uit. Reden: opt-in, conform de wens "kan inschakelen".
```

- [ ] **Step 3: Voeg een korte alinea toe aan `README.md`**

Onder de relevante sectie (automatiek/hooks), voeg toe:

```markdown
### Achtergrond-automatiek aan/uit

Vier achtergrond-taken (transcript-archief, destillatie-melding, embed-index,
dagelijkse graph-update) zijn toggles in `kennisbank-settings.json`. Beheer ze
met `/kennisbank:settings`. `auto_archive` staat default uit; de rest aan. Zie
CONFIGURATION.md voor de tabel.
```

- [ ] **Step 4: Voeg een korte regel toe aan `POST-INSTALL.md`**

Bij de setup-uitkomst-beschrijving, voeg toe:

```markdown
`setup.sh` schreef ook `kennisbank-settings.json` met de default-toggles
(`auto_archive` uit, de rest aan). Pas ze aan met `/kennisbank:settings`.
```

- [ ] **Step 5: Verifieer de hele suite**

Run: `python -m pytest tests/ -v`
Expected: PASS (alle tests; deploy-tests SKIPpen alleen zonder Git Bash).

- [ ] **Step 6: Commit**

```bash
git add CONFIGURATION.md CHANGELOG.md README.md POST-INSTALL.md
git commit -m "docs(settings): documenteer toggles, /kennisbank:settings en gedragswijziging"
```

---

## Self-Review

**Spec coverage:**
- Doel 1 (4 toggles individueel) -> Tasks 2,3,4 (hooks) + 7 (daily-graphify). ✓
- Doel 2 (persistent, vaste plek) -> Task 1 (`kennisbank-settings.json` + `_settings.py`). ✓
- Doel 3 (`/kennisbank:settings`-commando) -> Task 5. ✓
- Doel 4 (setup/upgrade vragen uit) -> Task 6 (setup bootstrap) + Task 8 (upgrade). ✓
- Doel 5 (handmatige paden blijven werken) -> Task 3 (mark/list ongegate) + spec niet-doelen (geen destilleer-wijziging). ✓
- Edge case `.needs-rebuild` bij embed uit -> Task 4 test + CONFIGURATION-sectie. ✓
- Edge case `--mark/--list-pending` ongegate -> Task 3 test. ✓
- Subdir-deploy gap -> Task 5. ✓
- Migratie/gedragswijziging -> Task 8 waarschuwing + Task 9 CHANGELOG. ✓

**Placeholder scan:** De `<true|false>`, `<key>`, `N.` (sectienummer in CONFIGURATION) zijn bewuste invul-tokens binnen instructie-markdown, geen code-placeholders; elke code-stap bevat volledige code. Geen TBD/TODO.

**Type consistency:** `get(key, default)`, `set(key, value)`, `init()`, `settings_path()`, `DEFAULTS` zijn consistent gebruikt in Tasks 1-8. CLI-subcommando's `get`/`set`/`init` consistent. Toggle-keys `auto_archive`/`distill_notify`/`embed_index`/`daily_graphify` overal identiek gespeld.

**Open aandachtspunt voor de uitvoerder:** `py -3` vs `python3`. Hooks/`setup.sh` gebruiken `py -3` (Windows); command-markdown gebruikt `python3` (zusterconventie). De `_settings.py`-CLI-tests draaien met `sys.executable` (host-onafhankelijk). Op een POSIX-host moet `py -3` in `setup.sh` `python3` worden; dit is gemarkeerd in Task 6 Step 3.

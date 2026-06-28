# Setup + migratie v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maak `setup.sh` idempotent-veilig voor nieuwe én bestaande gebruikers: het registreert de volledige KennisBank-hookset (juiste interpreter + matcher), ververst tooling zonder user-data te clobberen, en draait een version-gated migratie-runner met een vault-versie-stamp.

**Architecture:** Eén declaratief hook-manifest (`_hooks_manifest.py`) is de bron voor `register-hooks.py` (nu interpreter-aware + matcher-capable + self-heal-behoud-interpreter) en `doctor.sh`. Een migratie-runner (`_migrations.py`) brengt een vault deterministisch naar `VERSION` via geordende, idempotente migraties (dirs, hooks, toggles) en stempelt `<vault>/.claude/.kennisbank-version`. `setup.sh` ververst tooling onvoorwaardelijk en delegeert config/structuur aan de runner.

**Tech Stack:** Python 3.10+ (stdlib), bash, `unittest`. Geen nieuwe dependencies.

## Global Constraints

- **Versie-target:** `VERSION = "0.9.0"` (agent-geheugen minor-bump boven released 0.8.2).
- **Interpreter:** Windows (`os.name == "nt"`) → `py -3`; anders → `python3`. Bij self-heal van een bestaande hook: **behoud** de bestaande interpreter-prefix; herschrijf alleen het pad. Nooit `py -3`→`python3`.
- **User-data nooit clobberen:** vault-`CLAUDE.md`, `kennisbank-embed.json` en bestaande `kennisbank-settings.json`-wáárden blijven behouden (tenzij expliciet `--force`). Tooling (scripts/commands/skills) wordt wél onvoorwaardelijk ververst.
- **Idempotent + fail-soft:** elke stap is veilig her-uit te voeren. Een migratie-fout stopt vóór de stamp zodat een re-run hervat. Corrupte settings.json → weiger te schrijven, clobber niet.
- **PreToolUse-matcher:** `kb-presearch.py` krijgt matcher `WebSearch|WebFetch`.
- **Module-conventie:** underscore-naam (importeerbaar), self-locate vault via `parents[2]`, stdlib-only.
- **KISS:** geen rollback/downgrade/netwerk. Migraties zijn kleine lokale functies.

---

### Task 1: `_hooks_manifest.py` — single source of truth

**Files:**
- Create: `scripts/_hooks_manifest.py`
- Test: `tests/test_hooks_manifest.py`

**Interfaces:**
- Produces: `HOOKS` — `list[tuple[str, str, str|None]]` van `(event, script_basename, matcher_of_None)`. `hooks() -> list` (kopie).

- [ ] **Step 1: Write the failing test**

Create `tests/test_hooks_manifest.py`:

```python
import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("_hooks_manifest", SCRIPTS / "_hooks_manifest.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class HooksManifestTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_contains_memory_hooks(self):
        scripts = {s for _, s, _ in self.m.hooks()}
        for need in ("build-kb-index.py", "sweep-launch.py", "memory-notify.py",
                     "kb-presearch.py", "build-embed-index.py", "kb-retrieve.py",
                     "archive-transcript.py", "distill-notify.py"):
            self.assertIn(need, scripts)

    def test_presearch_has_matcher(self):
        for event, script, matcher in self.m.hooks():
            if script == "kb-presearch.py":
                self.assertEqual(event, "PreToolUse")
                self.assertEqual(matcher, "WebSearch|WebFetch")
                break
        else:
            self.fail("kb-presearch.py niet in manifest")

    def test_hooks_returns_copy(self):
        self.m.hooks().append(("X", "y.py", None))
        self.assertNotIn(("X", "y.py", None), self.m.hooks())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_hooks_manifest.py -v`
Expected: FAIL — module bestaat niet.

- [ ] **Step 3: Implement `scripts/_hooks_manifest.py`**

```python
#!/usr/bin/env python3
"""_hooks_manifest.py - de canonieke lijst van KennisBank-hooks.

Eén bron van waarheid voor register-hooks.py, doctor.sh en de migraties. Een
hook toevoegen is hier één regel; alle consumenten dekken 'm dan automatisch.
Stdlib-only, geen zware imports (doctor.sh importeert dit vanuit een python3 -c).
"""
from __future__ import annotations

# (event, script_basename, matcher_of_None). Alleen KennisBank-hooks; de hooks
# van de gebruiker (bv. caveman) staan hier NIET in en blijven ongemoeid.
HOOKS = [
    ("SessionStart",     "build-embed-index.py",  None),
    ("SessionStart",     "build-kb-index.py",     None),
    ("SessionStart",     "sweep-launch.py",       None),
    ("SessionStart",     "memory-notify.py",      None),
    ("SessionStart",     "distill-notify.py",     None),
    ("UserPromptSubmit", "kb-retrieve.py",        None),
    ("SessionEnd",       "archive-transcript.py", None),
    ("PreToolUse",       "kb-presearch.py",       "WebSearch|WebFetch"),
]


def hooks():
    """Een kopie van het manifest (consumenten mogen muteren zonder de bron te raken)."""
    return list(HOOKS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_hooks_manifest.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_hooks_manifest.py tests/test_hooks_manifest.py
git commit -m "feat(setup): _hooks_manifest single source of truth voor KennisBank-hooks"
```

---

### Task 2: `register-hooks.py` — interpreter-aware + matcher + self-heal-behoud + manifest

**Files:**
- Modify: `scripts/register-hooks.py`
- Test: `tests/test_register_hooks.py`

**Interfaces:**
- Consumes: `_hooks_manifest.hooks()`.
- Produces:
  - `interpreter() -> str` — `"py -3"` op Windows (`os.name == "nt"`), anders `"python3"`.
  - `build_command(script_path, interp=None) -> str` — `f'{interp or interpreter()} "{script_path}"'`.
  - `ensure_hook(settings, event, script_path, matcher=None) -> bool` — idempotent; self-heal behoudt de bestaande interpreter-prefix; matcher alleen bij append.
  - `register_manifest(settings, vault_root) -> bool` — registreert de volledige `_hooks_manifest` tegen `<vault>/.claude/scripts/<basename>`.
  - CLI: `register-hooks.py <settings> --manifest <vault_root>` naast de bestaande positionele vorm.

- [ ] **Step 1: Write the failing test**

Create `tests/test_register_hooks.py`:

```python
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("register_hooks", SCRIPTS / "register-hooks.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class RegisterHooksTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-rh-"))
        self.settings = self.tmp / "settings.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_interpreter_per_platform(self):
        orig = os.name
        try:
            os.name = "nt"
            self.assertEqual(self.m.interpreter(), "py -3")
            os.name = "posix"
            self.assertEqual(self.m.interpreter(), "python3")
        finally:
            os.name = orig

    def test_append_with_matcher(self):
        s = {}
        self.assertTrue(self.m.ensure_hook(s, "PreToolUse", "/v/.claude/scripts/kb-presearch.py",
                                           matcher="WebSearch|WebFetch"))
        group = s["hooks"]["PreToolUse"][0]
        self.assertEqual(group["matcher"], "WebSearch|WebFetch")
        self.assertIn("kb-presearch.py", group["hooks"][0]["command"])

    def test_selfheal_preserves_py3_interpreter(self):
        # bestaande hook met py -3 en een STALE pad -> pad ververst, prefix blijft py -3
        s = {"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": 'py -3 "/oud/.claude/scripts/kb-retrieve.py"'}]}]}}
        changed = self.m.ensure_hook(s, "SessionStart", "/nieuw/.claude/scripts/kb-retrieve.py")
        self.assertTrue(changed)
        cmd = s["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        self.assertEqual(cmd, 'py -3 "/nieuw/.claude/scripts/kb-retrieve.py"')

    def test_idempotent_no_change_second_time(self):
        s = {}
        self.m.ensure_hook(s, "SessionStart", "/v/.claude/scripts/build-kb-index.py")
        self.assertFalse(self.m.ensure_hook(s, "SessionStart", "/v/.claude/scripts/build-kb-index.py"))

    def test_register_manifest_full_set(self):
        s = {}
        self.m.register_manifest(s, "/v")
        cmds = [h["command"] for ev in s["hooks"].values() for g in ev for h in g["hooks"]]
        joined = " ".join(cmds)
        for need in ("build-kb-index.py", "sweep-launch.py", "memory-notify.py", "kb-presearch.py"):
            self.assertIn(need, joined)
        pre = s["hooks"]["PreToolUse"][0]
        self.assertEqual(pre.get("matcher"), "WebSearch|WebFetch")

    def test_corrupt_json_refused(self):
        self.settings.write_text("{not json", encoding="utf-8")
        rc = self.m.main([str(self.settings), "--manifest", "/v"])
        self.assertEqual(rc, 1)
        self.assertEqual(self.settings.read_text(encoding="utf-8"), "{not json")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_register_hooks.py -v`
Expected: FAIL — `interpreter`/`register_manifest`/matcher-arg ontbreken.

- [ ] **Step 3: Modify `scripts/register-hooks.py`**

Vervang `build_command` en `ensure_hook`, voeg `interpreter`/`register_manifest` toe, en breid `main` uit met `--manifest`. Behoud `load_settings`/`save_settings` ongewijzigd.

```python
import os


def interpreter() -> str:
    """De interpreter voor hook-commando's: 'py -3' op Windows, anders 'python3'.

    Windows' py-launcher is de robuuste manier om Python te vinden in de
    hook-uitvoercontext; op POSIX is python3 de conventie."""
    return "py -3" if os.name == "nt" else "python3"


def build_command(script_path: str, interp: str | None = None) -> str:
    """Hook-commando: '<interpreter> "<pad>"'. Pad gequote i.v.m. spaties."""
    return f'{interp or interpreter()} "{script_path}"'


def _existing_prefix(command: str) -> str | None:
    """De interpreter-prefix (alles t/m de spatie vóór de eerste quote) van een
    bestaand commando, of None als er geen quote in staat."""
    i = command.find('"')
    return command[:i] if i > 0 else None


def ensure_hook(settings: dict, event: str, script_path: str, matcher=None) -> bool:
    """Zorg dat `event` `script_path` als command-hook draait. Idempotent.

    Match op basename: bestaat een entry, dan wordt alleen het PAD ververst en
    de bestaande interpreter-prefix BEHOUDEN (geen py -3 -> python3). Matcher
    wordt alleen bij een nieuwe (append) entry gezet. Andere entries blijven."""
    basename = os.path.basename(script_path)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("settings['hooks'] is not an object")
    event_groups = hooks.setdefault(event, [])
    if not isinstance(event_groups, list):
        raise ValueError(f"settings['hooks']['{event}'] is not a list")

    for group in event_groups:
        if not isinstance(group, dict):
            continue
        for h in group.get("hooks", []):
            if not isinstance(h, dict):
                continue
            existing = h.get("command")
            if isinstance(existing, str) and basename in existing:
                prefix = _existing_prefix(existing)
                desired = f'{prefix}"{script_path}"' if prefix else build_command(script_path)
                if desired == existing:
                    return False
                h["command"] = desired  # self-heal pad, behoud interpreter
                return True

    group = {"hooks": [{"type": "command", "command": build_command(script_path)}]}
    if matcher:
        group = {"matcher": matcher,
                 "hooks": [{"type": "command", "command": build_command(script_path)}]}
    event_groups.append(group)
    return True


def register_manifest(settings: dict, vault_root: str) -> bool:
    """Registreer de volledige _hooks_manifest tegen <vault>/.claude/scripts/."""
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "_hooks_manifest", os.path.join(here, "_hooks_manifest.py"))
    man = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(man)
    changed = False
    for event, script, matcher in man.hooks():
        path = f"{vault_root}/.claude/scripts/{script}"
        if ensure_hook(settings, event, path, matcher=matcher):
            changed = True
    return changed
```

Pas `main` aan zodat `--manifest <vault>` werkt naast de positionele vorm:

```python
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) >= 3 and argv[1] == "--manifest":
        settings_path, vault_root = argv[0], argv[2]
        try:
            settings = load_settings(settings_path)
        except ValueError as e:
            print(f"register-hooks: {e}", file=sys.stderr)
            print("register-hooks: laat settings.json ongemoeid; registreer handmatig "
                  "(zie CONFIGURATION.md).", file=sys.stderr)
            return 1
        changed = register_manifest(settings, vault_root)
        if changed:
            save_settings(settings_path, settings)
            print(f"register-hooks: manifest geregistreerd in {settings_path}")
        else:
            print(f"register-hooks: manifest al aanwezig in {settings_path} (geen wijziging)")
        return 0

    if len(argv) < 3 or (len(argv) - 1) % 2 != 0:
        print("usage: register-hooks.py <settings.json> --manifest <vault_root>\n"
              "   or: register-hooks.py <settings.json> <EVENT> <script_path> "
              "[<EVENT> <script_path> ...]", file=sys.stderr)
        return 2

    settings_path = argv[0]
    pairs = [(argv[i], argv[i + 1]) for i in range(1, len(argv), 2)]
    try:
        settings = load_settings(settings_path)
    except ValueError as e:
        print(f"register-hooks: {e}", file=sys.stderr)
        print("register-hooks: laat settings.json ongemoeid; registreer hooks handmatig "
              "(zie CONFIGURATION.md).", file=sys.stderr)
        return 1
    changed = False
    for event, script_path in pairs:
        if ensure_hook(settings, event, script_path):
            changed = True
    if changed:
        save_settings(settings_path, settings)
        print(f"register-hooks: hooks geregistreerd in {settings_path}")
    else:
        print(f"register-hooks: hooks al aanwezig in {settings_path} (geen wijziging)")
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_register_hooks.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/register-hooks.py tests/test_register_hooks.py
git commit -m "feat(setup): register-hooks interpreter-aware + matcher + self-heal-behoud + --manifest"
```

---

### Task 3: `_settings.migrate()` — additieve toggle-migratie

**Files:**
- Modify: `scripts/_settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `migrate() -> bool` — voeg ontbrekende `DEFAULTS`-keys toe aan een bestaand settings-bestand zonder bestaande waarden te wijzigen; bestaat het bestand niet, val terug op `init()`. CLI: `_settings.py migrate`.

- [ ] **Step 1: Write the failing test**

Voeg toe aan `tests/test_settings.py` (volgt de bestaande temp-vault-conventie van dat bestand; zet `KENNISBANK_VAULT` naar een temp-vault, schrijf een settings-bestand met één oude key):

```python
class SettingsMigrateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-mig-"))
        self.vault = self.tmp / "vault"
        self.vault.mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        # herlaad _settings zodat vault_root de temp-vault pakt
        import importlib
        import _settings as s
        importlib.reload(s)
        self.s = s

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migrate_adds_missing_preserves_existing(self):
        import json
        p = self.vault / "kennisbank-settings.json"
        # oude install: auto_archive bewust op een niet-default waarde
        p.write_text(json.dumps({"auto_archive": True}), encoding="utf-8")
        self.assertTrue(self.s.migrate())
        data = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(data["auto_archive"], True)          # behouden
        self.assertIn("memory_capture", data)                 # toegevoegd
        self.assertEqual(data["memory_capture"], True)

    def test_migrate_idempotent(self):
        self.s.init()
        self.assertFalse(self.s.migrate())                    # niets ontbreekt

    def test_migrate_absent_file_falls_back_to_init(self):
        self.assertTrue(self.s.migrate())
        self.assertTrue((self.vault / "kennisbank-settings.json").exists())
```

(Voeg bovenaan `tests/test_settings.py` de nodige imports toe als die ontbreken: `import os, tempfile`, `from pathlib import Path`, en zorg dat `scripts/` op `sys.path` staat zoals de bestaande tests in dat bestand.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_settings.py -k Migrate -v`
Expected: FAIL — `migrate` bestaat niet.

- [ ] **Step 3: Implement `migrate()` + CLI in `_settings.py`**

Voeg toe na `init()`:

```python
def migrate() -> bool:
    """Voeg ontbrekende DEFAULTS-keys toe aan een bestaand settings-bestand zonder
    bestaande waarden te wijzigen. Bestaat het bestand niet, val terug op init().
    Return True als er iets geschreven is. Idempotent."""
    p = settings_path()
    if not p.exists():
        return init()
    data = _load()
    missing = {k: v for k, v in DEFAULTS.items() if k not in data}
    if not missing:
        return False
    data.update(missing)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True
```

Voeg een `migrate`-tak toe aan `_cli` (vóór de `unknown command`-regel):

```python
    if cmd == "migrate":
        print("migrated" if migrate() else "current")
        return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_settings.py -v`
Expected: PASS (de nieuwe + bestaande settings-tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_settings.py tests/test_settings.py
git commit -m "feat(setup): _settings.migrate additieve toggle-migratie (behoudt bestaande waarden)"
```

---

### Task 4: `_migrations.py` — version-stamp + runner

**Files:**
- Create: `scripts/_migrations.py`
- Test: `tests/test_migrations.py`

**Interfaces:**
- Consumes: `register-hooks.register_manifest`, `_settings.migrate`.
- Produces:
  - `VERSION = "0.9.0"`; `read_stamp(vault) -> str` (ontbrekend → `"0.0.0"`); `write_stamp(vault, v)`.
  - `pending(vault) -> list` (migraties met versie > stamp, semver via int-tuple).
  - `run(vault, settings_path, skip_hooks=False) -> list[str]` — past pending toe, stempelt `VERSION`; bij een migratie-fout propageert de exceptie vóór de stamp. Return de toegepaste migratie-namen.

- [ ] **Step 1: Write the failing test**

Create `tests/test_migrations.py`:

```python
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("_migrations", SCRIPTS / "_migrations.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class MigrationsTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-migr-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self.settings = self.tmp / "settings.json"
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_read_stamp_absent_is_zero(self):
        self.assertEqual(self.m.read_stamp(self.vault), "0.0.0")

    def test_pending_gates_on_stamp(self):
        self.assertTrue(self.m.pending(self.vault))           # geen stamp -> alles pending
        self.m.write_stamp(self.vault, self.m.VERSION)
        self.assertEqual(self.m.pending(self.vault), [])       # actueel -> niets

    def test_run_applies_and_stamps(self):
        applied = self.m.run(self.vault, str(self.settings))
        self.assertTrue(applied)
        self.assertEqual(self.m.read_stamp(self.vault), self.m.VERSION)
        # geheugen-dirs migratie
        self.assertTrue((self.vault / "09-memory").is_dir())
        # toggles migratie
        data = json.loads((self.vault / "kennisbank-settings.json").read_text(encoding="utf-8"))
        self.assertIn("memory_capture", data)
        # hooks migratie
        s = json.loads(self.settings.read_text(encoding="utf-8"))
        joined = json.dumps(s)
        self.assertIn("build-kb-index.py", joined)

    def test_run_idempotent(self):
        self.m.run(self.vault, str(self.settings))
        self.assertEqual(self.m.run(self.vault, str(self.settings)), [])  # niets pending

    def test_failing_migration_leaves_stamp(self):
        # injecteer een falende migratie vooraan
        def boom(vault, ctx):
            raise RuntimeError("kapot")
        self.m.MIGRATIONS.insert(0, ("0.9.0", "boom", boom))
        try:
            with self.assertRaises(RuntimeError):
                self.m.run(self.vault, str(self.settings))
            self.assertEqual(self.m.read_stamp(self.vault), "0.0.0")  # geen stamp
        finally:
            self.m.MIGRATIONS.pop(0)

    def test_skip_hooks(self):
        self.m.run(self.vault, str(self.settings), skip_hooks=True)
        self.assertFalse(self.settings.exists())  # geen hooks geschreven


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_migrations.py -v`
Expected: FAIL — module bestaat niet.

- [ ] **Step 3: Implement `scripts/_migrations.py`**

```python
#!/usr/bin/env python3
"""_migrations.py - version-gated migratie-runner voor de KennisBank-vault.

Brengt een vault deterministisch naar VERSION via geordende, idempotente
migraties (dirs, hooks, toggles) en stempelt <vault>/.claude/.kennisbank-version.
Het framework is vooruitkijkend: de huidige migraties zijn idempotent-altijd-
toepasbaar, de version-gating betaalt zich uit bij toekomstige eenrichtings-
migraties. Stdlib-only.

CLI:
    _migrations.py run <vault_root> <settings_json> [--skip-hooks]
    _migrations.py version <vault_root>   -> print de gestempelde versie
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

VERSION = "0.9.0"
STAMP_REL = ".claude/.kennisbank-version"


def _vtuple(v: str):
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)


def read_stamp(vault_root) -> str:
    try:
        return (Path(vault_root) / STAMP_REL).read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def write_stamp(vault_root, version: str) -> None:
    p = Path(vault_root) / STAMP_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(version + "\n", encoding="utf-8")


def _load_sibling(name, filename):
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(name, os.path.join(here, filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _m_memory_dirs(vault_root, ctx):
    for d in ("09-memory", "09-memory/archive", "01-raw/transcripts"):
        (Path(vault_root) / d).mkdir(parents=True, exist_ok=True)


def _m_register_hooks(vault_root, ctx):
    if ctx.get("skip_hooks"):
        return
    rh = _load_sibling("register_hooks", "register-hooks.py")
    settings_path = ctx["settings_path"]
    settings = rh.load_settings(settings_path)
    if rh.register_manifest(settings, str(vault_root)):
        rh.save_settings(settings_path, settings)


def _m_memory_toggles(vault_root, ctx):
    # _settings leest de vault uit KENNISBANK_VAULT; zet 'm voor de migratie.
    os.environ["KENNISBANK_VAULT"] = str(vault_root)
    s = _load_sibling("_settings", "_settings.py")
    s.migrate()


# (versie, naam, apply_fn(vault_root, ctx)). Geordend; idempotent.
MIGRATIONS = [
    ("0.9.0", "geheugen-dirs", _m_memory_dirs),
    ("0.9.0", "geheugen-hooks", _m_register_hooks),
    ("0.9.0", "geheugen-toggles", _m_memory_toggles),
]


def pending(vault_root):
    cur = _vtuple(read_stamp(vault_root))
    return [m for m in MIGRATIONS if _vtuple(m[0]) > cur]


def run(vault_root, settings_path, skip_hooks=False):
    """Pas pending migraties toe en stempel VERSION. Een falende migratie
    propageert vóór de stamp zodat een re-run hervat. Return de namen."""
    ctx = {"settings_path": settings_path, "skip_hooks": skip_hooks}
    applied = []
    for version, name, fn in pending(vault_root):
        fn(vault_root, ctx)
        applied.append(name)
    write_stamp(vault_root, VERSION)
    return applied


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "version" and len(argv) >= 2:
        print(read_stamp(argv[1]))
        return 0
    if len(argv) >= 3 and argv[0] == "run":
        skip = "--skip-hooks" in argv[3:]
        applied = run(argv[1], argv[2], skip_hooks=skip)
        print("migrations toegepast: " + (", ".join(applied) if applied else "(geen)"))
        return 0
    print("usage: _migrations.py run <vault_root> <settings_json> [--skip-hooks]\n"
          "   or: _migrations.py version <vault_root>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_migrations.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_migrations.py tests/test_migrations.py
git commit -m "feat(setup): _migrations version-stamp + runner (dirs/hooks/toggles, fail-voor-stamp)"
```

---

### Task 5: `setup.sh` — tooling-refresh + manifest-hooks + migraties

**Files:**
- Modify: `setup.sh`
- Test: `tests/test_setup_deploy.py`

**Interfaces:**
- Consumes: `register-hooks.py --manifest`, `_migrations.py run`.
- Produces: een idempotent-veilige `setup.sh` die tooling onvoorwaardelijk ververst, user-data behoudt, de volledige hookset registreert en migraties draait + stempelt.

- [ ] **Step 1: Write the failing test**

Voeg toe aan `tests/test_setup_deploy.py` (gebruikt de bestaande `_hook_commands`, `run_setup`, `_bash_path`):

```python
    def test_full_memory_hookset_registered(self):
        tmp, vault = self.run_setup()
        try:
            settings = json.loads((tmp / ".claude" / "settings.json").read_text(encoding="utf-8"))
            session = " ".join(_hook_commands(settings, "SessionStart"))
            for need in ("build-embed-index.py", "build-kb-index.py", "sweep-launch.py",
                         "memory-notify.py"):
                self.assertIn(need, session, f"{need} niet op SessionStart")
            pre = settings.get("hooks", {}).get("PreToolUse", [])
            self.assertTrue(pre, "geen PreToolUse-hook")
            self.assertEqual(pre[0].get("matcher"), "WebSearch|WebFetch")
            self.assertIn("kb-presearch.py", _hook_commands(settings, "PreToolUse")[0])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_version_stamp_written(self):
        tmp, vault = self.run_setup()
        try:
            stamp = vault / ".claude" / ".kennisbank-version"
            self.assertTrue(stamp.is_file())
            self.assertEqual(stamp.read_text(encoding="utf-8").strip(), "0.9.0")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_rerun_preserves_user_data_and_refreshes_tooling(self):
        tmp, vault = self.run_setup()
        try:
            # user-data wijzigen + een tooling-script bewust 'verouderen'
            (vault / "CLAUDE.md").write_text("MIJN EIGEN CLAUDE\n", encoding="utf-8")
            stale = vault / ".claude" / "scripts" / "kb-recall.py"
            stale.write_text("# STALE\n", encoding="utf-8")
            self.run_setup_in(tmp)  # tweede run tegen dezelfde HOME
            self.assertEqual((vault / "CLAUDE.md").read_text(encoding="utf-8"), "MIJN EIGEN CLAUDE\n")
            self.assertNotEqual(stale.read_text(encoding="utf-8"), "# STALE\n")  # ververst
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_setup_deploy.py -k "memory_hookset or version_stamp or preserves_user_data" -v`
Expected: FAIL — setup.sh registreert de geheugen-hooks/stamp nog niet en ververst tooling niet.

- [ ] **Step 3: Modify `setup.sh`**

Drie wijzigingen. **(a)** Voeg na `copy_file()` een `copy_force()` toe (altijd overschrijven, voor tooling):

```bash
# copy_force SRC DST -- altijd (over)kopieren. Voor TOOLING (scripts/commands/
# skills): geen user-data, dus altijd de repo-versie. User-data blijft copy_file.
copy_force() {
  cp "$1" "$2"
  echo "  ververst: $2"
}
```

**(b)** Vervang in de scripts-, commands- en skills-loops `copy_file` door `copy_force` (NIET bij CLAUDE.md of kennisbank-embed.json — die blijven `copy_file`). Concreet:
- scripts-loop (`for f in scripts/*.py scripts/*.sh; do copy_file ...`) → `copy_force`.
- commands-loops (plat + genamespacet, in zowel de `--yes`- als de interactieve tak) → `copy_force`.
- skills-loop → `copy_force`.
- Laat `copy_file kennisbank-embed.example.json ...` en `copy_file CLAUDE.md.template ...` ONGEWIJZIGD (skip-if-exists).

**(c)** Vervang de `register_hooks()`-functie + voeg een migratie-stap toe. Vervang de body van `register_hooks()`:

```bash
register_hooks() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "  WAARSCHUWING: python3 niet gevonden; hooks/migraties niet uitgevoerd."
    echo "  Registreer later handmatig (zie CONFIGURATION.md, sectie 4)."
    return 0
  fi
  mkdir -p "$HOME/.claude"
  python3 "$VAULT/.claude/scripts/register-hooks.py" "$CLAUDE_SETTINGS" --manifest "$VAULT" \
    || echo "  hooks niet geregistreerd (zie melding hierboven); registreer handmatig (CONFIGURATION.md)." >&2
}
```

Voeg na het hele hooks-blok (na de `if [ "$NO_HOOKS" = "1" ] ... fi`), vóór de afsluitende `echo`-stappen, een migratie-stap toe:

```bash
# Migraties: breng de vault version-gated naar de huidige staat (dirs, hooks,
# toggles) en stempel de versie. Idempotent; fail-soft (breekt setup niet).
if command -v python3 >/dev/null 2>&1; then
  SKIP_HOOKS_ARG=""
  [ "$NO_HOOKS" = "1" ] && SKIP_HOOKS_ARG="--skip-hooks"
  python3 "$VAULT/.claude/scripts/_migrations.py" run "$VAULT" "$CLAUDE_SETTINGS" $SKIP_HOOKS_ARG \
    || echo "  migraties niet (volledig) uitgevoerd; her-run 'bash setup.sh'." >&2
fi
```

> Noot voor de uitvoerder: `register_hooks()` (via `--manifest`) en de migratie-stap (`_m_register_hooks`) registreren beide de hookset. Dat is bewust en benign: beide zijn idempotent. `register_hooks()` draait ELKE run (self-heal van de hookset, ook na een handmatige verwijdering), terwijl de migratie de version-gated/lean-upgrade-route + stamp levert.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_setup_deploy.py -v`
Expected: PASS (de nieuwe + alle bestaande deploy-tests). Let op: deze tests draaien de echte `setup.sh` en zijn traag (~2 min).

- [ ] **Step 5: Commit**

```bash
git add setup.sh tests/test_setup_deploy.py
git commit -m "feat(setup): tooling-refresh + manifest-hookset + migraties in setup.sh (idempotent-veilig)"
```

---

### Task 6: `doctor.sh` — manifest-gedreven hook-check + versie-stamp

**Files:**
- Modify: `scripts/doctor.sh`
- Test: `tests/test_setup_deploy.py`

**Interfaces:**
- Consumes: `_hooks_manifest`, `_migrations.read_stamp`.
- Produces: doctor checkt elke manifest-hook + toont de versie-stamp.

- [ ] **Step 1: Write the failing test**

Voeg toe aan `tests/test_setup_deploy.py` (er bestaat al een `run_doctor_in`-helper en doctor-tests):

```python
    def test_doctor_reports_memory_hooks_and_version(self):
        tmp, vault = self.run_setup()
        try:
            result = self.run_doctor_in(tmp, vault)
            out = result.stdout
            self.assertRegex(out, r"\[PASS\].*build-kb-index\.py.*registered")
            self.assertRegex(out, r"\[PASS\].*kb-presearch\.py.*registered")
            self.assertRegex(out, r"kennisbank-versie.*0\.9\.0")
            self.assertEqual(result.returncode, 0, f"doctor exited {result.returncode}:\n{out}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_setup_deploy.py -k doctor_reports_memory -v`
Expected: FAIL — doctor checkt alleen build-embed-index + kb-retrieve en toont geen versie.

- [ ] **Step 3: Modify `scripts/doctor.sh`**

Vervang het hook-controle-blok (de embedded `python3 -c` die alleen `build-embed-index.py` + `kb-retrieve.py` checkt, regels rond "13b. Retrieval hooks") door een manifest-gedreven check. De `python3 -c` importeert `_hooks_manifest`, leest `settings.json`, en print één regel per hook `OK|MISSING <event> <basename>`; de bash-lus rapporteert per regel. Voeg ook een versie-stamp-INFO toe.

Vervang vanaf `# 13b. Retrieval hooks registered in settings.json.` t/m de bijbehorende afsluitende `fi` door:

```bash
# 13b. KennisBank-hooks geregistreerd in settings.json (manifest-gedreven).
SETTINGS="$CLAUDE_DIR/settings.json"
HOOK_HINT="re-run 'bash setup.sh' (of bij een hardnekkig ontbrekende hook: rm \"$VAULT/.claude/.kennisbank-version\" && bash setup.sh)"
if ! command -v python3 >/dev/null 2>&1; then
  report_warn "KennisBank-hooks" "kan $SETTINGS niet lezen zonder python3; $HOOK_HINT"
else
  HOOK_LINES="$(python3 -c '
import json, os, sys, importlib.util
spec = importlib.util.spec_from_file_location("_hooks_manifest",
    os.path.join(sys.argv[2], "_hooks_manifest.py"))
man = importlib.util.module_from_spec(spec); spec.loader.exec_module(man)
p = sys.argv[1]
if not os.path.exists(p):
    print("NOFILE"); raise SystemExit
try:
    text = open(p, encoding="utf-8").read()
    data = json.loads(text) if text.strip() else {}
except (ValueError, OSError):
    print("BADJSON"); raise SystemExit
if not isinstance(data, dict):
    print("BADJSON"); raise SystemExit
hooks = data.get("hooks", {}) if isinstance(data.get("hooks"), dict) else {}
def present(event, needle):
    for g in (hooks.get(event) or []):
        if isinstance(g, dict):
            for h in (g.get("hooks") or []):
                if isinstance(h, dict) and needle in (h.get("command") or ""):
                    return True
    return False
for event, script, _m in man.hooks():
    print(("OK " if present(event, script) else "MISSING ") + event + " " + script)
' "$SETTINGS" "$SCRIPTS_DIR" 2>/dev/null)"
  if [ "$HOOK_LINES" = "NOFILE" ]; then
    report_warn "KennisBank-hooks" "nog geen $SETTINGS; $HOOK_HINT"
  elif [ "$HOOK_LINES" = "BADJSON" ]; then
    report_warn "KennisBank-hooks" "$SETTINGS is geen geldige JSON; kan hooks niet checken. $HOOK_HINT"
  elif [ -z "$HOOK_LINES" ]; then
    report_warn "KennisBank-hooks" "kon $SETTINGS niet lezen (python3-fout); $HOOK_HINT"
  else
    printf '%s\n' "$HOOK_LINES" | while IFS=' ' read -r status event script; do
      if [ "$status" = "OK" ]; then
        report_pass "hook $event $script" "registered in $SETTINGS"
      else
        report_warn "hook $event $script" "not registered. $HOOK_HINT"
      fi
    done
  fi
fi

# 13c. Vault-versie-stamp.
if command -v python3 >/dev/null 2>&1; then
  KB_VER="$(python3 "$SCRIPTS_DIR/_migrations.py" version "$VAULT" 2>/dev/null)"
  report_info "kennisbank-versie" "${KB_VER:-onbekend}"
fi
```

> Noot: de `report_*` tellers worden in doctor.sh als globale variabelen opgehoogd. De `while`-lus hierboven draait in een pipeline-subshell; om de tellers correct te houden gebruikt de uitvoerder de bestaande doctor-conventie (procesvervanging of een tijdelijke-bestand-loop). Als doctor.sh elders al een `while read` over tellers gebruikt, spiegel díe vorm. Anders: vervang de pipeline door `while ... done <<EOF \n$HOOK_LINES\nEOF` (here-doc, geen subshell) zodat `report_pass/warn` de globale tellers ophogen.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_setup_deploy.py -k "doctor" -v`
Expected: PASS (de nieuwe memory-hooks/versie-test + de bestaande doctor-tests blijven groen).

- [ ] **Step 5: Verify shell syntax**

Run: `bash -n scripts/doctor.sh`
Expected: geen output (valide).

- [ ] **Step 6: Commit**

```bash
git add scripts/doctor.sh tests/test_setup_deploy.py
git commit -m "feat(setup): doctor.sh manifest-gedreven hook-check + versie-stamp"
```

---

### Task 7: docs + versie-bump

**Files:**
- Modify: `CONFIGURATION.md`, `CHANGELOG.md`, `README.md`
- Test: geen (docs).

**Interfaces:**
- Produces: docs die de nieuwe één-commando-upgrade + version-stamp beschrijven; de handmatige hook-registratie-sectie wordt vereenvoudigd (setup.sh doet het nu volledig).

- [ ] **Step 1: Update `CONFIGURATION.md`**

In de hook-registratie-sectie (`### Hook registration`): vervang de tekst die zegt dat alleen `build-embed-index` + `kb-retrieve` geregistreerd worden door: `setup.sh` registreert nu de **volledige** hookset via `register-hooks.py --manifest` (interpreter-aware: `py -3` op Windows, `python3` elders; PreToolUse met matcher `WebSearch|WebFetch`). De handmatige `<VAULT>`-JSON-blokken blijven als referentie, maar voeg bovenaan toe: "Normaal hoeft dit niet handmatig — `bash setup.sh` doet het volledig, voor nieuwe én bestaande vaults." Documenteer kort de version-stamp (`<vault>/.claude/.kennisbank-version`) en dat een hardnekkig ontbrekende hook met `rm` van de stamp + her-run geforceerd kan worden.

- [ ] **Step 2: Update `CHANGELOG.md`**

Onder `## [Unreleased]` → `### Added`/`### Changed`: regels voor (a) idempotent-veilige `setup.sh` voor bestaande gebruikers (tooling-refresh zonder user-data te clobberen), (b) volledige hookset-registratie incl. geheugen-hooks + presearch-matcher, (c) interpreter-aware `register-hooks` (`py -3`/`python3`, self-heal behoudt interpreter), (d) `_migrations` version-stamp + runner, (e) `_settings.migrate`.

- [ ] **Step 3: Update `README.md`**

Waar de install/upgrade beschreven staat: één regel dat `bash setup.sh` veilig her-uit te voeren is en een bestaande vault upgradet zonder aanpassingen te verliezen.

- [ ] **Step 4: Run the full suite (sanity)**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 5: Commit**

```bash
git add CONFIGURATION.md CHANGELOG.md README.md
git commit -m "docs(setup): documenteer idempotent-veilige setup/upgrade + version-stamp (v0.9.0)"
```

---

## Self-Review

**Spec coverage:**
- `_hooks_manifest` single source → Task 1. ✓
- register-hooks interpreter-aware + self-heal-behoud + matcher + manifest → Task 2. ✓
- `_settings.migrate` additief → Task 3. ✓
- `_migrations` version-stamp + runner + 3 migraties + fail-voor-stamp → Task 4. ✓
- setup.sh tooling-refresh (geen user-data clobber) + volledige hookset + migraties → Task 5. ✓
- doctor.sh manifest-gedreven + versie-stamp → Task 6. ✓
- docs + versie 0.9.0 → Task 7. ✓

**Placeholder scan:** geen TBD/TODO; alle code + testcode volledig. Eén bewuste uitvoerder-noot in Task 6 (doctor teller-subshell) met een concrete fallback (here-doc i.p.v. pipeline) — geen placeholder, een implementatie-richtlijn.

**Type consistency:** `interpreter()->str`, `build_command(path, interp=None)->str`, `ensure_hook(settings,event,path,matcher=None)->bool`, `register_manifest(settings,vault_root)->bool`, `_hooks_manifest.hooks()->list[(event,script,matcher)]`, `_settings.migrate()->bool`, `_migrations.read_stamp(vault)->str`/`run(vault,settings_path,skip_hooks=False)->list[str]` — consistent over taken. `_migrations` consumeert `register-hooks.register_manifest` + `_settings.migrate` met matchende signatures.

**Aandachtspunten uitvoerder:**
- Task 2: de self-heal-test verwacht dat een bestaande `py -3`-hook z'n prefix behoudt; `_existing_prefix` splitst op de eerste quote. Bevestig dat een commando zónder quote (theoretisch) op `build_command` terugvalt.
- Task 5: deze tests draaien de echte `setup.sh` (traag, ~2 min) en vereisen `bash` (de `_find_bash`-helper bestaat al). `register_hooks()` én de migratie registreren beide de hookset — bewust idempotent (zie de noot in Task 5).
- Task 6: respecteer de doctor.sh teller-conventie (geen pipeline-subshell die `report_*`-tellers verliest; gebruik de here-doc-vorm). `bash -n` moet groen zijn.
- Task 4: `_m_memory_toggles` zet `KENNISBANK_VAULT` naar de vault vóór het `_settings`-import, omdat `_settings` de vault op import-tijd resolvet.

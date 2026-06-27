# Setup + migratie v2 — Design

**Status:** goedgekeurd (brainstorm) — klaar voor implementatieplan.
**Datum:** 2026-06-27.
**Aanleiding:** de net uitgevoerde upgrade-deploy van het agent-geheugen op de echte vault (Kluis). Die lukte alleen handmatig + met advisor-correcties; een gewone `setup.sh`-run zou stil gefaald hebben. Dit ontwerp borgt dat setup + migratie het vanzelf goed doen, voor nieuwe én bestaande gebruikers.

## Probleem (bewijs uit de deploy)

1. **setup.sh activeert de geheugen-feature niet.** `register_hooks()` wired alleen `build-embed-index` + `kb-retrieve`. De vier agent-geheugen-hooks (`build-kb-index`, `sweep-launch`, `memory-notify`, `kb-presearch`) worden nooit geregistreerd → de scripts staan er, maar capture/recall/presearch draaien niet. De hoofd-feature shipt dood.
2. **register-hooks.py is interpreter-onveilig.** Het hardcodet `python3 "..."`. Op Windows waar `py -3` ≠ `python3` (aantoonbaar: twee verschillende `python.exe`'s) doet dit twee dingen fout: (a) het registreert hooks met een interpreter die in de hook-context mogelijk niet werkt; (b) z'n self-heal-by-basename **herschrijft bestaande, werkende `py -3`-hooks naar `python3`** → breekt retrieval.
3. **register-hooks.py kan geen PreToolUse-matcher emitten.** Zonder matcher draait `kb-presearch.py` op élke tool-call (Read/Edit/Bash), niet alleen WebSearch/WebFetch — een per-call-belasting.
4. **Geen veilig tooling-refresh-pad.** Plain `setup.sh` slaat gewijzigde scripts over (stale `kb-retrieve.py` blijft stil staan); `setup.sh --force` clobbert vault-`CLAUDE.md` + `embed.json` (user-data-verlies). Geen "ververs tooling, behoud user-config"-modus.
5. **Settings migreren niet.** `memory_capture`/`memory_recall` komen niet in een bestaande `kennisbank-settings.json` bij upgrade (functioneel default True via fallback, maar onzichtbaar/niet-toggle­baar).

## Doelen

- **Eén commando, nieuw + bestaand:** `bash setup.sh --yes` werkt zowel voor een verse install als een upgrade van een bestaande vault, zonder user-data te clobberen.
- **De feature wordt geactiveerd:** alle KennisBank-hooks worden geregistreerd, met de juiste interpreter en matcher.
- **Migratie is geborgd:** een version-stamp + migratie-runner brengen een oudere vault deterministisch naar de huidige staat.
- **Cross-platform correct:** Windows `py -3`, anders `python3`; bestaande interpreter-keuze gerespecteerd.

## Niet-doelen (KISS-grens)

- Geen rollback/downgrade. Geen netwerk. Geen package-manager. Geen zware migratie-engine.
- Migraties zijn kleine, lokale, idempotente Python-functies.
- `setup.sh` blijft de installer; de `kennisbank-upgrade`-skill orkestreert (pull tag → `setup.sh --yes`) maar bevat zelf geen migratie-logica.

## Architectuur

Vijf samenhangende units. Elk één verantwoordelijkheid, los testbaar.

### 1. `scripts/_hooks_manifest.py` — single source of truth

Een declaratieve lijst van álle KennisBank-hooks:

```python
# (event, script_basename, matcher_of_None)
HOOKS = [
    ("SessionStart",     "build-embed-index.py", None),
    ("SessionStart",     "build-kb-index.py",    None),
    ("SessionStart",     "sweep-launch.py",      None),
    ("SessionStart",     "memory-notify.py",     None),
    ("SessionStart",     "distill-notify.py",    None),
    ("UserPromptSubmit", "kb-retrieve.py",       None),
    ("SessionEnd",       "archive-transcript.py", None),
    ("PreToolUse",       "kb-presearch.py",      "WebSearch|WebFetch"),
]
```

`register-hooks.py`, `doctor.sh` (via een `--list`-achtige helper of een gedeelde lezer) en de migraties lezen deze ene lijst. Een hook toevoegen is één regel, overal gedekt. Stdlib-only, geen imports van zware modules.

> Noot: `distill-notify.py` + `archive-transcript.py` zaten al in de cc-transcript-deploy maar werden níet door `register-hooks.py` gezet (apart geregistreerd). Door ze in het manifest op te nemen, dekt setup.sh nu de volledige set in één keer.

### 2. `scripts/register-hooks.py` (herzien)

- **Interpreter-detectie:** `_interpreter()` geeft `"py -3"` als `os.name == "nt"`, anders `"python3"`. `build_command(script_path, interpreter)` → `f'{interpreter} "{script_path}"'`.
- **Self-heal behoudt interpreter:** bij een bestaande hook met dezelfde basename wordt alleen het **pad** ververst; de bestaande interpreter-prefix (`py -3` of `python3`) blijft staan. Nooit `py -3`→`python3` herschrijven.
- **Matcher-support:** een hook-entry mag een matcher dragen; bij append wordt `{"matcher": m, "hooks": [...]}` geschreven (zonder matcher: `{"hooks": [...]}`).
- **Manifest-modus:** naast de bestaande positionele CLI (`<settings> EVENT script ...`, behouden voor compat) een `--manifest`-modus die de volledige `_hooks_manifest.HOOKS` registreert tegen een vault-root. setup.sh gebruikt `--manifest`.
- Non-destructief + idempotent + JSON-weiger-bij-corrupt blijven zoals nu.

### 3. `scripts/_migrations.py` — version-stamp + runner

```python
VERSION = "0.9.0"                      # huidige repo-versie (agent-geheugen)
STAMP = ".claude/.kennisbank-version"  # relatief aan vault-root

# (versie, naam, apply_fn(vault_root, ctx) -> None)
MIGRATIONS = [
    ("0.9.0", "geheugen-dirs",    _m_memory_dirs),
    ("0.9.0", "geheugen-hooks",   _m_register_hooks),
    ("0.9.0", "geheugen-toggles", _m_memory_toggles),
]
```

- `read_stamp(vault)` → de gestempelde versie, of `"0.0.0"` als de stamp ontbreekt (pre-stamp/oude vault).
- `pending(vault)` → migraties met `versie > stamp` (semver-vergelijk via tuple van ints).
- `run(vault)` → draait pending migraties in volgorde; bij succes `write_stamp(vault, VERSION)`. Een migratie die faalt stopt de run **vóór** de stamp, zodat een re-run hervat.
- Elke `apply_fn` is **idempotent** (veilig her-uit te voeren): `geheugen-dirs` = `mkdir -p`; `geheugen-hooks` = `register-hooks --manifest` (al idempotent); `geheugen-toggles` = `_settings.migrate()`.

**Het framework is bewust vooruitkijkend.** De huidige seed-migraties zijn allemaal idempotent-altijd-toepasbaar; de version-gating betaalt zich pas echt uit bij toekomstige **eenrichtings**-migraties (data-transformatie, hernoeming) die níet veilig her-uitvoerbaar zijn. De gebruiker koos hier expliciet voor; de runner blijft klein.

### 4. `scripts/_settings.py` — `migrate()`

`migrate()` voegt ontbrekende sleutels uit `DEFAULTS` toe aan een bestaande `kennisbank-settings.json` **zonder** bestaande waarden te overschrijven. Bestaat het bestand niet, dan valt het terug op `init()`. Idempotent. Voegt o.a. `memory_capture`/`memory_recall` (default True) toe op oude installs, zodat ze zichtbaar + toggle­baar worden.

### 5. `setup.sh` — altijd-veilig (nieuw + bestaand)

Herstructurering van de deploy-volgorde:

- **Tooling = altijd ververst.** Scripts (`scripts/*.py`, `scripts/*.sh`), commands (plat + genamespacet `commands/*/*.md`) en skills worden **onvoorwaardelijk** ge(her)kopieerd (het zijn geen user-data). De huidige `copy_file`-skip-logica geldt voortaan alleen voor **user-data** (vault-`CLAUDE.md`, `kennisbank-embed.json`).
- **User-data = nooit geclobberd** (tenzij expliciet `--force`): vault-`CLAUDE.md` en `embed.json` blijven behouden; settings-wáárden blijven behouden (alleen additief gemigreerd).
- **Hooks via manifest:** `register_hooks()` roept `register-hooks.py --manifest "$VAULT"` aan (volledige set, juiste interpreter, matcher).
- **Migraties:** na de tooling-refresh draait `python3 "$VAULT/.claude/scripts/_migrations.py" run "$VAULT"` (version-gated) en stempelt de versie.
- **deps** naar de juiste interpreter (op Windows `py -3 -m pip`, anders `python3 -m pip`) zodat de hook-interpreter de dep heeft.
- `--force` behoudt z'n huidige betekenis (overschrijf óók user-data) als ontsnappingsluik.

### doctor.sh

Het bestaande embedded `python3`-blok in doctor.sh importeert `_hooks_manifest` en verifieert **elke** hook uit `HOOKS` (alle 6 SessionStart/UserPromptSubmit/SessionEnd + de PreToolUse-matcher) tegen `settings.json` als `[PASS]`/`[WARN]` — i.p.v. de twee hardgecodeerde checks nu. Toont de vault-versie-stamp (`[INFO] kennisbank-versie: 0.9.0`, gelezen uit `_migrations.read_stamp`). Zo blijft doctor automatisch in sync met het manifest: een nieuwe hook in `HOOKS` wordt zonder doctor-wijziging meegecheckt.

## Data flow

```
bash setup.sh --yes
  → mkdir vault-dirs (idempotent)
  → refresh tooling (scripts/commands/skills, onvoorwaardelijk)
  → ensure user-data (CLAUDE.md/embed.json: copy-if-absent)
  → settings bootstrap (init-if-absent) + _settings.migrate() (additief)
  → register-hooks.py --manifest  (volledige set, py-3/python3, matcher)
  → _migrations.py run            (pending migraties, dan stamp 0.9.0)
  → klaar; doctor.sh verifieert
```

Verse install (geen vault): stamp ontbreekt → alle migraties draaien → identiek eindresultaat als upgrade. Eén pad.

## Error handling

- **Ontbrekende interpreter** (`py -3`/`python3` niet gevonden): waarschuw, registreer geen hooks, ga door (bestaand gedrag).
- **Corrupte settings.json:** weiger te schrijven, exit non-zero in register-hooks; setup meldt + gaat door met de rest.
- **Migratie-fout:** stop de run vóór de stamp; de mislukte + latere migraties blijven pending → een volgende `setup.sh` hervat. Geen halve stamp.
- **Alles fail-soft + idempotent:** elke stap is veilig her-uit te voeren.

## Testing

- `tests/test_register_hooks.py` (nieuw): interpreter-detectie (monkeypatch `os.name` → `py -3`/`python3`); self-heal behoudt de bestaande interpreter (een `py -3`-hook met stale pad → pad ververst, prefix blijft `py -3`); matcher wordt geschreven voor PreToolUse; `--manifest` registreert de volledige set; idempotent (tweede run = geen wijziging); corrupte JSON → exit non-zero, bestand ongemoeid.
- `tests/test_migrations.py` (nieuw): `read_stamp` ontbrekend → `"0.0.0"`; `pending` version-gating; `run` past pending toe + stempelt; tweede `run` = geen pending (idempotent); een falende migratie laat de stamp ongemoeid (re-run hervat); semver-vergelijk (0.9.0 > 0.10.0? correct via int-tuples).
- `tests/test_settings.py` (uitbreiden): `migrate()` voegt ontbrekende toggles toe, overschrijft bestaande waarden niet, is idempotent.
- `tests/test_setup_deploy.py` (uitbreiden): na `setup.sh --yes` is de **volledige** hook-set geregistreerd (incl. de 4 geheugen-hooks + PreToolUse-matcher); een tweede run clobbert vault-`CLAUDE.md`/`embed.json` niet en behoudt settings-waarden; de versie-stamp bestaat met `0.9.0`; tooling wordt wél ververst (een bewust-oud script in de vault is na de run gelijk aan de repo-versie).

## Open punten

Geen. Versie-target = `0.9.0` (agent-geheugen minor-bump boven released 0.8.2).

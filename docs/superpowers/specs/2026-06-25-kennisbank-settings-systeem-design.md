# KennisBank settings-systeem — design

Datum: 2026-06-25
Status: goedgekeurd (brainstorm)
Branch: `feat/cc-transcript-archive` (vervolg)

## Probleem

De transcript-archief/destillatie-uitbreiding (en de eerdere graph- en
embed-features) introduceerden achtergrond-automatiek die altijd-aan is zodra de
hooks geregistreerd zijn:

- `archive-transcript.py` (SessionEnd) archiveert elk transcript;
- `distill-notify.py` (SessionStart) meldt openstaande transcripts;
- `build-embed-index.py` (SessionStart) ververst de wiki-embeddingcache;
- de dagelijkse `graphify --update`-batch (gate in `sessielog`/`wiki`/`destilleer`).

De gebruiker wil per stuk kunnen kiezen of die automatiek draait. De keuze moet
worden vastgelegd (persistent), en bij een verse `setup` of een `upgrade` moet de
gebruiker interactief worden gevraagd welke automatiek aan moet als de keuze nog
niet is vastgelegd.

## Doelen

1. Vier achtergrond-automatieken zijn individueel aan/uit te zetten.
2. De keuze is persistent en leeft op een vaste plek in de vault.
3. Een `/kennisbank:settings`-commando toont een nette lijst toggles met huidige
   staat en zet ze aan/uit, en legt de keuze vast.
4. `setup` en `upgrade` vragen ontbrekende instellingen interactief uit en
   schrijven ze weg.
5. De handmatige paden blijven werken: `/sessielog` vangt de huidige sessie
   transcript-onafhankelijk, `/destilleer` batcht alle openstaande transcripts.

## Niet-doelen (YAGNI)

- Geen live-history-fallback in `/destilleer`. Met `auto_archive` uit is het
  handmatige pad `/sessielog` + `/wiki`. (Bevestigd met gebruiker.)
- Geen wijziging aan de batch-logica van `/destilleer` of `/wiki`. Die batchen al
  meerdere raw-logs (`/wiki` scant de laatste 7 dagen; `/destilleer` neemt alle
  pending stems in een snapshot). (Bevestigd met gebruiker.)
- Geen herschrijven van de globale `~/.claude/settings.json` hooks-array. Hooks
  blijven statisch geregistreerd en gaten zichzelf.
- Geen namespace-migratie van de bestaande commands. Alleen het nieuwe
  `settings`-commando is namespaced; `/sessielog`, `/wiki`, etc. blijven flat.

## Architectuur

### Settings-store

Een plat JSON-bestand op `$VAULT/kennisbank-settings.json`, naast
`kennisbank-embed.json` (zelfde plek, zelfde patroon). Bron van waarheid.

```json
{
  "auto_archive": false,
  "distill_notify": true,
  "embed_index": true,
  "daily_graphify": true
}
```

Vault-root wordt overal geresolved via `KENNISBANK_VAULT` (env) met fallback
`~/KennisBank`, conform `_vaultpath.vault_root()`. Geen letterlijke paden.

### Helper `scripts/_settings.py`

Stdlib-only, geen hyphen in de naam (importeerbaar na `sys.path.insert`, idem aan
`_vaultpath.py` / `_frontmatter.py`). Twee functies plus de padresolutie:

- `settings_path() -> Path` — `vault_root() / "kennisbank-settings.json"`.
- `get(key: str, default: bool) -> bool` — leest het JSON-bestand en geeft de
  waarde van `key`. **Eén regel voor alle foutpaden:** ontbrekend bestand,
  ongeldige JSON, of ontbrekende key geeft `default` terug. Nooit een exceptie
  naar de caller. Zo is een corrupt of nog-niet-bestaand bestand identiek aan
  "ongeconfigureerd": de caller bepaalt het gedrag via zijn eigen per-toggle
  default.
- `set(key: str, value: bool) -> None` — leest het bestaande bestand (of begint
  leeg bij fout/afwezigheid), zet `key`, schrijft het hele object atomisch terug
  (schrijf naar tempfile in dezelfde map, dan `os.replace`). Maakt het bestand
  aan als het niet bestaat. Behoudt onbekende keys (forward-compatible).

`get`/`set` zijn de enige lezer/schrijver van het bestand. Command, `setup.sh`
(via `py -3`) en de upgrade-skill gebruiken ze allemaal, zodat key-namen en
formaat nergens kunnen driften.

De canonieke keys en hun per-toggle defaults staan op één plek in `_settings.py`
als een dict `DEFAULTS`, zodat het settings-commando, `setup.sh` en de
upgrade-skill dezelfde lijst en defaults delen.

### Defaults (ongeconfigureerd)

| toggle | default | reden |
|--------|---------|-------|
| `auto_archive` | `false` | opt-in; "kan inschakelen" |
| `distill_notify` | `true` | goedkoop, alleen een melding |
| `embed_index` | `true` | kern voor prompt-time retrieval |
| `daily_graphify` | `true` | al kost-gated op 20u; uit = graph veroudert |

De default-keuze geldt alleen als de key (of het bestand) ontbreekt. Een
read/parse-fout valt op dezelfde default terug. `setup`/`upgrade` schrijven
expliciete waarden, dus in de praktijk treedt de default alleen op bij een verse
installatie vóór de bootstrap-vraag.

### Self-gating hooks

Elk hook-script checkt zijn eigen toggle bovenaan `main()` en eindigt met
`exit 0` (fail-open, hook nooit blokkeren) als de toggle uit staat. Geen
wijziging aan de registratie in `~/.claude/settings.json`.

| script | toggle | default die het script aan `get()` geeft |
|--------|--------|------------------------------------------|
| `archive-transcript.py` | `auto_archive` | `False` |
| `distill-notify.py` (SessionStart-pad) | `distill_notify` | `True` |
| `build-embed-index.py` | `embed_index` | `True` |

Belangrijke deelpaden:

- `distill-notify.py` gate **alleen het SessionStart-meldpad** (geen argumenten).
  `--list-pending` en `--mark` worden door `/destilleer` aangeroepen en moeten
  ALTIJD werken, ook met de melding uit. Anders zou het handmatige destilleer-pad
  breken als de melding uit staat.
- `build-embed-index.py` cleart vandaag ook de graphify `.needs-rebuild`-flag.
  Met `embed_index` uit draait dat script niet, dus de flag wordt niet bij
  SessionStart geleegd. Dat is benign: `.needs-rebuild` is een "werk staat klaar"
  -signaal dat door de graphify-rebuild zelf wordt geleegd, niet door de embed-
  index. De plan-fase verifieert dat de daily-graphify-gate hier niet op vastloopt
  (zie Edge cases).

### Daily-graphify-gate

Dit is geen hook maar staat in de command-markdown (`sessielog.md` stap 2 item 5,
`wiki.md`, `destilleer.md` stap 3). De gate wordt uitgebreid met een
`daily_graphify`-check, gelezen in de bash van het command:

```bash
# interpreter volgt de zusterconventie: command-markdown gebruikt python3
# (zoals destilleer.md); setup.sh en de hooks gebruiken py -3 op Windows.
DG=$(python3 -c "import sys; sys.path.insert(0,'$VAULT/.claude/scripts'); \
import _settings; print('1' if _settings.get('daily_graphify', True) else '0')")
```

- `daily_graphify` aan: huidige logica ongewijzigd (schrijf `.needs-rebuild`; als
  `graph.json` > 20u en `.needs-rebuild` niet leeg, draai `/graphify --update`).
- `daily_graphify` uit: schrijf nog steeds `.needs-rebuild` (gratis), maar sla de
  automatische `/graphify --update` over. De gebruiker kan altijd handmatig
  `/graphify $VAULT --update` draaien.

`.needs-rebuild` blijft dus altijd het werk-staat-klaar-signaal, ongeacht de
toggle. Alleen de automatische rebuild is optioneel.

### `/kennisbank:settings`-commando

Nieuw bestand `commands/kennisbank/settings.md`. Door de subdirectory wordt het
`/kennisbank:settings`. Gedrag (markdown-instructies aan Claude):

1. Bepaal `VAULT` op de standaard manier.
2. Lees de huidige staat: per canonieke key `_settings.get(key, default)`.
3. Toon een nette tabel: toggle, huidige staat (aan/uit), korte omschrijving.
4. Vraag via `AskUserQuestion` (multiselect) welke toggles AAN moeten staan. De
   vooraf-aangevinkte set is de huidige staat.
5. Schrijf elke toggle terug via `_settings.set(key, value)` (aangevinkt =
   `true`, niet-aangevinkt = `false`). Maakt het bestand aan als het niet bestaat.
6. Rapporteer de nieuwe staat en welke automatiek nu aan/uit is.

Het commando is de canonieke handmatige weg om de keuze te wijzigen na de
installatie.

### `setup.sh` — twee wijzigingen

**1. Subdir-aware command-deploy.** Vandaag deployt setup met
`for f in commands/*.md` — een flat glob die de subdir niet meeneemt. Voeg een
tweede deploy toe die ook `commands/*/*.md` afhandelt en de subdir-structuur
behoudt:

```bash
# bestaande flat commands
for f in commands/*.md; do
  copy_file "$f" "$CLAUDE_COMMANDS/$(basename "$f")"
done
# genamespacede commands (bv. commands/kennisbank/settings.md)
for f in commands/*/*.md; do
  rel="${f#commands/}"                 # kennisbank/settings.md
  mkdir -p "$CLAUDE_COMMANDS/$(dirname "$rel")"
  copy_file "$f" "$CLAUDE_COMMANDS/$rel"
done
```

Dit gebeurt in beide takken (`--yes` en interactief), conform de bestaande
structuur. `nullglob` (al gezet) maakt de lege-match veilig.

**2. Settings-bootstrap.** Na de scripts-deploy (zodat `_settings.py` in de vault
staat), als `$VAULT/kennisbank-settings.json` ontbreekt:

- Interactief (geen `--yes`, TTY aanwezig): vraag per toggle `y/n` met de default
  voorgeselecteerd, en schrijf het resultaat via
  `py -3 "$VAULT/.claude/scripts/_settings.py" set <key> <true|false>` (zie
  CLI-hook hieronder), of via een klein inline `py -3`-blok dat de hele dict
  schrijft.
- Niet-interactief (`--yes` of geen TTY): schrijf het defaults-bestand en meld
  "instellingen op default gezet; draai /kennisbank:settings om aan te passen".

Om `setup.sh` (bash) en de upgrade-skill een schrijver te geven zonder JSON in
bash te bouwen, krijgt `_settings.py` een kleine CLI-hook onderaan:

```python
# python _settings.py get <key> [default]   -> print '1'/'0', exit 0
# python _settings.py set <key> <1|0|true|false>
# python _settings.py init                   -> schrijf defaults als afwezig
```

Stdlib-only, geen externe deps. Zo is er één implementatie van lezen/schrijven.

### `kennisbank-upgrade`-skill

Voeg een stap toe: garandeer dat `kennisbank-settings.json` bestaat en alle
canonieke keys bevat. Voor elke ontbrekende key: vraag de gebruiker interactief
(in de conversatie) of die automatiek aan moet, met de default als suggestie, en
schrijf via `_settings.set`. Zo krijgen bestaande installaties (de echte Kluis,
die nu geen settings-bestand heeft) de vraag bij de eerstvolgende upgrade. Reeds
gezette keys worden niet opnieuw gevraagd.

### `kennisbank-settings.example.json`

Een sanitized voorbeeldbestand in de repo-root (zoals
`kennisbank-embed.example.json`), met de defaults. `setup.sh` gebruikt het niet
direct als deploy-bron (de bootstrap schrijft het bestand), maar het dient als
gedocumenteerde referentie en wordt door tests gebruikt om de canonieke keys te
asserten.

## Edge cases en interacties

1. **Corrupt settings-bestand.** `get` valt terug op de meegegeven default; het
   pad-systeem breekt niet. `set` herstelt het bestand bij de volgende schrijf.
2. **`.needs-rebuild` met `embed_index` uit.** De flag wordt niet bij
   SessionStart geleegd. De daily-graphify-gate behandelt een niet-lege flag als
   "werk staat klaar" en draait (als `daily_graphify` aan) `/graphify --update`,
   dat na afloop de flag leegt (sessielog stap). Geen vastloper. De plan-fase
   bevestigt dit met een test.
3. **`distill-notify --mark/--list-pending` met `distill_notify` uit.** Die
   subcommando's blijven werken; alleen het argument-loze SessionStart-meldpad
   gate. Geverifieerd in het design; test in de plan-fase.
4. **`auto_archive` uit, daarna `/destilleer`.** Archiefmap is leeg, `/destilleer`
   meldt "niets te destilleren" en stopt. Handmatig pad is `/sessielog`. Geen
   nieuwe code.
5. **Non-TTY setup (CI, `--yes`).** Bootstrap schrijft defaults en blokkeert niet
   op `read`.

## Bestanden

Nieuw:
- `scripts/_settings.py`
- `commands/kennisbank/settings.md`
- `kennisbank-settings.example.json`
- `tests/test_settings.py`

Gewijzigd:
- `scripts/archive-transcript.py` (self-gate `auto_archive`)
- `scripts/distill-notify.py` (self-gate SessionStart-meldpad op `distill_notify`)
- `scripts/build-embed-index.py` (self-gate `embed_index`)
- `commands/sessielog.md` (daily-graphify-gate respecteert `daily_graphify`)
- `commands/wiki.md` (idem, graphify-batch-verwijzing)
- `commands/destilleer.md` (idem, stap 3)
- `setup.sh` (subdir-deploy + settings-bootstrap)
- `skills/kennisbank-upgrade/SKILL.md` (settings garanderen + ontbrekende keys vragen)
- `tests/test_setup_deploy.py` (assert subdir-deploy van het settings-commando)
- `CONFIGURATION.md` (nieuwe sectie: settings-systeem en toggles)
- `CHANGELOG.md` (Unreleased: Added/Changed)
- `README.md` / `POST-INSTALL.md` (kort: settings-commando en bootstrap)

## Tests

- `test_settings.py`:
  - `get` op ontbrekend bestand geeft default;
  - `get` op corrupt bestand geeft default;
  - `get` op ontbrekende key geeft default;
  - `set` dan `get` roundtrip;
  - `set` behoudt onbekende keys;
  - `set` is atomisch (geen half bestand bij fout — best effort via tempfile);
  - CLI-hook `get`/`set`/`init` gedragen zich identiek aan de functies.
- `test_setup_deploy.py`:
  - `commands/kennisbank/settings.md` deployt naar
    `$CLAUDE_COMMANDS/kennisbank/settings.md`;
  - de canonieke keys in `kennisbank-settings.example.json` matchen
    `_settings.DEFAULTS`.
- Hook-gating (klein, per script of gebundeld):
  - met de toggle uit eindigt het script met exit 0 en zonder neveneffect
    (geen archiefkopie / geen melding / geen embed-call);
  - `distill-notify --mark`/`--list-pending` werken ongeacht `distill_notify`.

## Migratie

Bestaande installaties hebben nog geen `kennisbank-settings.json`. Tot de
eerstvolgende `setup`/`upgrade`/`/kennisbank:settings` gelden de per-toggle
defaults: `auto_archive` valt dan terug op `false` (uit), de rest op `true`. Dat
betekent dat de huidige Kluis na deze wijziging géén transcripts meer archiveert
totdat `auto_archive` expliciet aan wordt gezet. De upgrade-skill vraagt dit
actief uit, dus de gebruiker maakt de keuze bewust. Dit is conform de
opt-in-bedoeling ("kan inschakelen"), maar het is een gedragswijziging die in de
CHANGELOG expliciet wordt genoemd.

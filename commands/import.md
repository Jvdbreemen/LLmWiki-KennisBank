Importeer oude sessies (Claude Code, claude.ai, of generieke map) naar de KennisBank vault. Argumenten: $ARGUMENTS

## Doel
Backfill van bestaande Claude-historie in `~/KennisBank/01-raw/sessies/` zodat `/wiki` er kennis uit kan compileren. Drie importers, één commando.

## Argumenten parsen

- `cc`: Claude Code session history (`$HOME/.claude/projects/*.jsonl`)
- `claudeai <pad>`: claude.ai export bundle (`conversations.json` of `.zip`)
- `folder <pad> [prefix]`: generieke recursieve markdown/txt-import
- `cowork`: alias voor `folder` met auto-detect van Mac desktop Claude (Cowork) data
- `all`: draait `cc` plus `cowork` plus, als er een claude.ai export aanwezig is, `claudeai`
- geen argument: vraag interactief welke source de gebruiker wil importeren

Als `$ARGUMENTS` niet matcht met bovenstaande: toon de lijst en vraag opnieuw.

## Algemene regels

- Altijd eerst `--dry-run --verbose`, dan bevestiging vragen, dan echte run
- Nooit `--force` zonder expliciete bevestiging van de gebruiker
- Imports zijn idempotent: bestaande raw-sessie-bestanden worden overgeslagen tenzij `--force` gezet is
- Bij errors in de JSON-output: lijst de error-bestanden in het rapport, abort niet
- Tel het aantal bestanden in `~/KennisBank/01-raw/sessies/` voor en na, zodat het verschil terug te rapporteren is

```bash
ls -1 ~/KennisBank/01-raw/sessies/ 2>/dev/null | wc -l
```

## Stappen per source

### cc: Claude Code history

1. Dry-run met verbose:
   ```bash
   python3 ~/KennisBank/.claude/scripts/import-cc-history.py --dry-run --verbose | head -50
   ```
2. Toon hoeveel sessies gevonden zijn en hoeveel nieuw zouden worden geschreven.
3. Vraag bevestiging: "Doorgaan met import?"
4. Bij ja: draai zonder `--dry-run`, met `--json`:
   ```bash
   python3 ~/KennisBank/.claude/scripts/import-cc-history.py --json
   ```
5. Vat de JSON-output samen in het rapport (imported, skipped, errors).

### claudeai: claude.ai export

1. Als pad ontbreekt: vraag de gebruiker om het pad naar `conversations.json` of de `.zip` van de claude.ai export.
2. Verifieer dat het bestand bestaat:
   ```bash
   test -f "<pad>" && echo OK || echo MISSING
   ```
   Als MISSING: stop, rapporteer terug en vraag een correct pad.
3. Dry-run:
   ```bash
   python3 ~/KennisBank/.claude/scripts/import-claudeai-export.py "<pad>" --dry-run --verbose | head -50
   ```
4. Bevestig en draai zonder `--dry-run`, met `--json`. Vat de output samen.

### folder: generieke markdown/txt map

1. Als pad ontbreekt: vraag de gebruiker om een absoluut pad. Suggereer dat de auto-detect van Mac desktop Claude data via:
   ```bash
   python3 ~/KennisBank/.claude/scripts/import-folder.py --list-cowork-candidates
   ```
   gevonden kan worden.
2. Optioneel tweede argument: prefix voor de gegenereerde slugs (bijv. `cowork`, `notes`).
3. Dry-run:
   ```bash
   python3 ~/KennisBank/.claude/scripts/import-folder.py "<pad>" [--prefix <prefix>] --dry-run --verbose | head -50
   ```
4. Bevestig en draai zonder `--dry-run`, met `--json`. Vat de output samen.

### cowork: auto-detected desktop Claude

1. Toon de gevonden kandidaten:
   ```bash
   python3 ~/KennisBank/.claude/scripts/import-folder.py --list-cowork-candidates
   ```
2. Laat de gebruiker een pad kiezen uit de lijst. Als er maar één kandidaat is: stel die voor en bevestig.
3. Dry-run met dat pad en `--prefix cowork`:
   ```bash
   python3 ~/KennisBank/.claude/scripts/import-folder.py "<gekozen-pad>" --prefix cowork --dry-run --verbose | head -50
   ```
4. Bevestig en draai zonder `--dry-run`, met `--json`. Vat de output samen.

### all: alle bronnen achter elkaar

1. Draai `cc` (één confirm).
2. Draai `cowork` (één confirm, inclusief kandidaat-keuze als er meerdere zijn).
3. Als er een claude.ai export is: vraag het pad en draai `claudeai`. Als de gebruiker geen pad heeft: sla over en meld dat.
4. Rapporteer per source en per totaal.

## Post-import

- Toon het aantal bestanden in `~/KennisBank/01-raw/sessies/` voor en na, plus het verschil.
- Suggereer als afsluiting:
  - "Run `/wiki` om kennis uit deze imports te compileren naar `~/KennisBank/02-wiki/`."
  - Alleen als er duplicaten of overlap te verwachten zijn: "Een latere `/sessielog`-run overschrijft het bestaande log voor die operation."

## Bevestiging

Per source rapporteren:
- Aantal imported
- Aantal skipped (al aanwezig)
- Aantal errors, met bestandsnamen
- Pad naar `~/KennisBank/01-raw/sessies/`

Bij `all`: bovenstaand per source plus een totaal eronder.

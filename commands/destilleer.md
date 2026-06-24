Destilleer gearchiveerde Claude Code-transcripts uit de vault tot wiki-kennis.

## Vault-root bepalen (VERPLICHT: lees dit eerst)

Bepaal de vault-root EEN keer en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik NOOIT een letterlijk pad. Alle scripts staan in `$VAULT/.claude/scripts/`.

## Doel
Tegenhanger van de archiefhook. De `SessionEnd`-hook (`archive-transcript.py`) heeft
transcripts naar `$VAULT/01-raw/transcripts/` gekopieerd. Dit commando trekt de dure
LLM-destillatie: importeer de nog niet verwerkte transcripts tot raw-sessielogs en
compileer ze tot wiki-artikelen. Idempotent via de `.distilled`-watermark.

## Stap 1: Leg de te verwerken set vast (snapshot)
```bash
BATCH=$(python3 "$VAULT/.claude/scripts/distill-notify.py" --list-pending < /dev/null)
echo "$BATCH"
```
`$BATCH` is de lijst pending transcript-stems (één per regel) op DIT moment. Is hij
leeg: meld "niets te destilleren" en stop. Bewaar deze set: stap 4 markeert exact
deze stems, niet wat er later in de map verschijnt.

## Stap 2: Importeer de archiefmap naar raw-sessielogs
```bash
python3 "$VAULT/.claude/scripts/import-cc-history.py" --source "$VAULT/01-raw/transcripts" --verbose
```
De importer slaat al bestaande raw-sessielogs over (target-bestand bestaat al),
dus dubbel draaien is veilig. Noteer welke nieuwe `raw-sessie-*.md` zijn geschreven.

## Stap 3: Compileer tot wiki
Voer de inhoud van `/wiki` uit over de zojuist geimporteerde raw-sessielogs
(zie `commands/wiki.md`): identificeer wiki-kandidaten, schrijf of werk artikelen
in `$VAULT/02-wiki/` bij, en draai de dagelijkse graphify-batch en semantische
tiling zoals `/wiki` voorschrijft. Verwerk alleen de raw-logs van vandaag of de
nieuw geimporteerde set; her-compileer geen oude artikelen.

## Stap 4: Markeer exact de snapshot als gedestilleerd
Alleen als stap 2 en 3 zonder fout zijn afgerond. Markeer ALLEEN de stems uit
`$BATCH` (stap 1), zodat een transcript dat tijdens stap 2-3 binnenkwam pending
blijft en bij de volgende run alsnog wordt aangeboden:
```bash
# shellcheck disable=SC2086  -- woordsplitsing op de stems is hier gewenst
[ -n "$BATCH" ] && python3 "$VAULT/.claude/scripts/distill-notify.py" --mark $BATCH < /dev/null
```
Dit APPENDt de verwerkte stems aan `$VAULT/01-raw/transcripts/.distilled`.

## Bevestiging
- Aantal transcripts in de snapshot (stap 1)
- Welke raw-sessielogs geimporteerd zijn (stap 2)
- Welke wiki-artikelen nieuw of bijgewerkt zijn (stap 3)
- Bevestiging dat de watermark is bijgewerkt met exact de snapshot (stap 4)

## Regels
- Idempotent: opnieuw draaien verwerkt alleen niet-gewatermerkte transcripts.
- Crasht stap 3 halverwege: laat de watermark ONGEMOEID (sla stap 4 over), zodat de
  rest bij de volgende run alsnog wordt opgepakt.
- Een transcript dat TIJDENS de run binnenkomt zit niet in `$BATCH` en blijft dus
  pending: het wordt bij de volgende `/destilleer` aangeboden. Geen stil verlies.
- Taal: volgt de prompt. Geen em dashes.

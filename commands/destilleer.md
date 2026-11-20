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
De geimporteerde `raw-sessie-*.md` zijn STUBS: frontmatter met `source_path` naar
het `.jsonl` plus een placeholder in plaats van de gespreksinhoud (zie het
wiki-artikel `import-cc-history-stubs`). Compileer daarom uit het TRANSCRIPT
(`$VAULT/01-raw/transcripts/<stem>.jsonl`), niet uit de stub. Uitzondering: een
raw-log die `/sessielog` zelf schreef bevat wel echte inhoud en `wiki-kandidaat:`-
markers, en is dus direct bruikbaar.

Voer de inhoud van `/wiki` uit over deze set (zie `commands/wiki.md`): identificeer
wiki-kandidaten, schrijf of werk artikelen in `$VAULT/02-wiki/` bij, en draai de
dagelijkse graphify-batch en semantische tiling zoals `/wiki` voorschrijft.
Verwerk alleen de nieuw geimporteerde set; her-compileer geen oude artikelen.

### Grote of vele transcripts: strip + subagent-fan-out
Transcripts kunnen enorm zijn (waargenomen tot ~12 MB / miljoenen tokens) en
passen dan niet in de context. Trek ze niet heel de hoofdcontext in. Strip elk
transcript eerst tot platte conversatietekst:
```bash
python3 "$VAULT/.claude/scripts/strip-transcript.py" <stem-of-pad> > "$SCRATCH/<stem>.txt"
```
De stripper laat thinking, tool_use, tool_result en subagent-turns vallen (~10x
kleiner) en schrijft naar stdout; leid het naar een scratch-bestand, NIET naar de
vault (de stubs blijven de index). Is de gestripte tekst klein, lees hem dan
inline. Bij grote of veel transcripts: dispatch één subagent per gestript
transcript (parallel), laat elk de net-nieuwe kennis kruisen tegen de bestaande
artikelen en compact terugrapporteren, en laat de HOOFDthread de wiki schrijven —
zo houd je provenance (`## Sessie-herkomst`) en de lint onder controle.

### Grote achterstand: optionele cloud-map (tijdelijk, opt-in)
Bij honderden pending transcripts kan de lees-stap uitbesteed worden aan
`distill-map.py`. Dat script stript en redigeert elk transcript, stuurt het in
chunks naar EEN expliciet gekozen OpenRouter-model (default
`deepseek/deepseek-v4-flash-0731`, `data_collection=deny`) en schrijft per stem
compacte kandidaat-kennis naar `$VAULT/.claude/distill-map/<stem>.json`, plus een
`_digest.md` gegroepeerd per project. Inhoud verlaat je machine, dus het draait
ALLEEN als de toggle `distill_cloud_map` aan staat (default uit). Zet hem na het
inlopen weer uit. De vault-config `kennisbank-llm.json` wordt niet gebruikt:
achtergrondjobs blijven lokaal.

**Toestemming is verplicht en geldt per run.** `/destilleer` zelf is lokaal; een
aanroep ervan is GEEN toestemming om transcripts naar de cloud te sturen. Zet de
toggle NOOIT zelf aan. Draai eerst de dry-run, toon de gebruiker het aantal
transcripts, het volume en het gekozen model, en vraag expliciet of die inhoud
naar OpenRouter mag. Zonder een ja: blijf bij de lokale werkwijze hierboven.
Staat de toggle al aan (bijvoorbeeld na een afgebroken run), vraag dan alsnog,
want een vergeten toggle is geen toestemming. Zet hem na de run altijd terug op
uit en controleer dat met `_settings.py get distill_cloud_map`.
De toestemming geldt voor precies de set uit de dry-run. Leg die set daarom vast
met `--write-stems` en geef hem met `--stems-file` aan elke cloud-call; nooit
`--pending` na de dry-run, want een transcript dat intussen binnenkwam zou dan
zonder toestemming meegaan. Wil je de set uitbreiden, vraag dan opnieuw.
```bash
SNAP="$VAULT/.claude/distill-map/_approved-stems.txt"
python3 "$VAULT/.claude/scripts/distill-map.py" --pending --dry-run --write-stems "$SNAP"
# pas na expliciete toestemming van de gebruiker voor deze set:
python3 "$VAULT/.claude/scripts/_settings.py" set distill_cloud_map true
python3 "$VAULT/.claude/scripts/distill-map.py" --stems-file "$SNAP" --limit 10  # proefbatch
python3 "$VAULT/.claude/scripts/distill-map.py" --stems-file "$SNAP"             # rest; hervat zelf
python3 "$VAULT/.claude/scripts/_settings.py" set distill_cloud_map false
```
Exitcode 1 = minstens een stem faalde (staat in `_errors.jsonl`, krijgt geen
output en wordt bij de volgende run opnieuw geprobeerd). Reduce daarna in
batches per project vanuit `_digest.md`: kruis elke kandidaat tegen de bestaande
wiki, schrijf of werk artikelen bij, en markeer per afgeronde batch exact die
stems met `distill-notify.py --mark` (stap 4 per batch in plaats van een keer aan
het eind). Stap 2 (stubs importeren) blijft nodig.

De dagelijkse graphify-batch respecteert de `daily_graphify`-toggle: staat die
uit (`python3 -c "import sys; sys.path.insert(0,'$VAULT/.claude/scripts'); import _settings; print(_settings.get('daily_graphify', True))"` geeft `False`), werk dan alleen `.needs-rebuild` bij en sla de automatische `/graphify --update` over.

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
- Crasht stap 3 halverwege: laat de watermark ONGEMOEID (sla stap 4 over). De
  al-geimporteerde raw-sessielogs blijven staan; stap 2 re-import is dan een no-op
  (de importer slaat bestaande targets over), dus het herstel leunt op het
  7-daagse raw-log-venster van `/wiki`: draai `/destilleer` of `/wiki` binnen 7
  dagen zodat die logs alsnog gecompileerd worden.
- Een transcript dat TIJDENS de run binnenkomt zit niet in `$BATCH` en blijft dus
  pending: het wordt bij de volgende `/destilleer` aangeboden. Geen stil verlies.
- Verwacht weinig net-nieuwe kennis: `/destilleer` overlapt zwaar met een in-sessie
  `/sessielog`, die dezelfde kennis vaak al naar `02-wiki/` schreef. Dat is de
  normale baseline, geen tekort. Wees kritisch en vermijd duplicaat-artikelen;
  bias naar UPDATE of overgeslagen boven een tweede artikel over hetzelfde.
- Taal: volgt de prompt. Geen em dashes.

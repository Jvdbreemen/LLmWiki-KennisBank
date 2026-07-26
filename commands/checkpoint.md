Leg de werkstand van deze sessie vast als checkpoint, of herstel/sluit een eerder checkpoint. Argument: $ARGUMENTS (leeg of `save` = vastleggen, `load` = herstellen, `done` = afsluiten).

## Vault-root bepalen (VERPLICHT: lees dit eerst)

Bepaal de vault-root EEN keer en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik NOOIT een letterlijk pad. Helpers staan in `$VAULT/.claude/scripts/`.

## Doel

Een checkpoint is een klein werkstand-snapshot dat een sessie-onderbreking
(context-compaction, crash, geplande stop) overbrugt. Het is GEEN sessielog:
een sessielog beschrijft achteraf wat er gebeurde; een checkpoint beschrijft
vooruit wat er nog moet gebeuren. Houd het kort — het wordt integraal in een
verse context geladen.

## Modus `save` (default, ook bij leeg argument)

1. Schrijf een checkpoint-markdown naar
   `$VAULT/01-raw/checkpoints/checkpoint-YYYY-MM-DD-HHMM-<slug>.md`
   (slug: 2-4 woorden, kebab-case, over het onderwerp). Secties:
   - `## Actieve taak` — wat er nu gebouwd/onderzocht wordt, incl. backlog-ID als die er is
   - `## Werkstand` — waar je precies bent: branch, gewijzigde bestanden, wat af is, wat halverwege
   - `## Open beslissingen` — keuzes die nog voorliggen, met de afweging in één zin per keuze
   - `## Volgende stap` — de eerstvolgende concrete actie
   - `## Gelinkte kennis` — relevante wiki-artikelen als `[[wikilinks]]`, backlog-taken, bestanden
2. Registreer het bestand mechanisch:
   ```bash
   python3 "$VAULT/.claude/scripts/kb-checkpoint.py" --register "<pad-uit-stap-1>"
   ```
   (Windows: `py -3`.) Weigert paden buiten `01-raw/checkpoints/`.
3. Bevestig kort: pad + één zin wat er vastligt.

## Modus `load`

1. Toon de open checkpoints:
   ```bash
   python3 "$VAULT/.claude/scripts/kb-checkpoint.py" --list
   ```
2. Lees het meest recente checkpoint-markdown (bij een handmatig checkpoint
   staat het pad in de lijst; bij een auto-checkpoint is er alleen een
   transcript-verwijzing — meld dat dan en gebruik het transcript-pad als
   leesbron voor de laatste werkstand).
3. Vat de herstelde werkstand in 3-5 regels samen en ga door met de
   "Volgende stap" uit het checkpoint. Vraag niet om bevestiging; het
   checkpoint IS de opdracht.
4. Sluit het checkpoint af zodra de werkstand hersteld is:
   ```bash
   python3 "$VAULT/.claude/scripts/kb-checkpoint.py" --done
   ```

## Modus `done`

Sluit alle open checkpoints af zonder ze te laden:
```bash
python3 "$VAULT/.claude/scripts/kb-checkpoint.py" --done
```
Gebruik dit als de werkstand inmiddels achterhaald is (werk af, of allang
hervat). `/sessielog` doet dit ook automatisch: een geschreven sessielog
vervangt elk ouder checkpoint.

## Regels

- Checkpoint-markdown is wegwerp-werkstand, geen kennis: het hoort NIET in de
  wiki en wordt niet geïndexeerd als artikel. Duurzame inzichten gaan via
  `/sessielog` en `/wiki` de vault in.
- Kort houden: streef naar minder dan 40 regels markdown.
- Taal: volgt de sessie. Geen em dashes.

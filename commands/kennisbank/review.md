Loop de wachtrij van unverified memories door en laat de gebruiker per item beslissen: approve, reject of skip. Optioneel filter op onderwerp: $ARGUMENTS

## Vault-root bepalen (VERPLICHT — lees dit eerst)

Bepaal de vault-root ÉÉN keer aan het begin van dit command en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik `$VAULT` voor ELK pad hieronder. Gebruik NOOIT een letterlijk `~/KennisBank`- of `C:\...\KennisBank`-pad: dat negeert de `KENNISBANK_VAULT`-env-var en werkt in de verkeerde vault.

## Doel

De memory-sweep en agent-captures laten fragmenten als `status: unverified` landen; de mens is de update-autoriteit die ze promoot of intrekt. Buiten Atlas bestond daar geen ingang voor (TASK-23: 31 gestuwde unverified memories). Dit command is die ingang: het systeem toont, de gebruiker beslist, het command voert uit.

## Stappen

1. Haal de wachtrij op:
   ```
   python3 $VAULT/.claude/scripts/memory-doctor.py pending --json
   ```
   - Als $ARGUMENTS is opgegeven: filter items waarvan `stem`, `title` of `snippet` het onderwerp bevat.
   - Lege lijst: rapporteer "Review-queue leeg: geen unverified memories." en stop.

2. Presenteer elk item aan de gebruiker, één voor één, oudste eerst:
   - Toon: titel, memory_type, importance, leeftijd (`age_days`), `evidence_basis` en het snippet.
   - Lees bij twijfel het volledige fragment (`$VAULT/09-memory/<stem>.md`) en toon de kern.
   - Vraag de beslissing:
     - **approve** — het fragment klopt en is blijvend nuttig → status `current`
     - **reject** — fout, ruis of niet meer waar → status `retracted`
     - **skip** — nu geen oordeel; blijft unverified in de queue
   - Hint bij twijfel: `evidence_basis: getypt` is door de gebruiker zelf aangeleverd en doorgaans betrouwbaar; `agent` verdient een kritischer blik. Maar de **gebruiker beslist** — dit command beslist NOOIT zelf, ook niet bij "evident juiste" fragmenten.

3. Voer elke beslissing direct door (niet opsparen tot het einde):
   ```
   python3 $VAULT/.claude/scripts/memory-doctor.py decide <stem> <approve|reject|skip> --via command
   ```
   - Exit 0: meld kort het resultaat (`<stem> -> current`, `-> retracted`, of `blijft unverified`).
   - Exit ≠ 0: toon de foutmelding LETTERLIJK aan de gebruiker en ga door met het volgende item. Het item blijft dan gewoon in de queue — meld het nooit als afgehandeld (crash-veilige belofte: een fout mag nooit als beslissing verschijnen).

4. Rapporteer na afloop:
   - Hoeveel items bekeken, hoeveel approved / rejected / skipped, hoeveel fouten.
   - Als er items overblijven (skips of fouten): noem het aantal dat in de queue blijft.

## Regels

- De gebruiker beslist altijd, per item. Geen bulk-goedkeuring ("keur alles maar goed") zonder dat de gebruiker die opdracht zelf expliciet en letterlijk gaf — en bevestig ook dan eerst de aantallen.
- Alleen `unverified` is beslisbaar; andere statussen weigert de tooling met een 409-melding. Dat is correct gedrag, geen bug.
- Wijzig memory-bestanden uitsluitend via `memory-doctor.py decide` — nooit met een eigen edit; de tooling bewaakt de crash-veilige volgorde en het audit-log (`$VAULT/.claude/memory-review-log.jsonl`).
- Taal: volg de gebruiker.

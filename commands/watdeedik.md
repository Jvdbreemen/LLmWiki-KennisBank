Beantwoord "wat deed ik op/in deze periode?" vanuit KennisBank temporal activity recall. Argumenten: $ARGUMENTS

## Vault-root bepalen

Bepaal de vault-root een keer en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik nooit een hardcoded `~/KennisBank` pad als `$KENNISBANK_VAULT` bestaat.

## Doel

Geef een compact, auditeerbaar antwoord op dag- of periodevragen.

Voorbeelden:
- `/watdeedik 2026-07-03`
- `/watdeedik gisteren`
- `/watdeedik vorige week`
- `/watdeedik onderwerp "OpenRouter" afgelopen 7 dagen`

## Uitvoering

1. Controleer of de activity index bestaat:
   ```bash
   python3 "$VAULT/.claude/scripts/kb-activity.py" --vault "$VAULT" status
   ```
2. Als de index ontbreekt of stale is, bouw hem eerst:
   ```bash
   python3 "$VAULT/.claude/scripts/build-activity-index.py" --vault "$VAULT" --progress-interval 300
   ```
3. Draai de recall:
   ```bash
   python3 "$VAULT/.claude/scripts/kb-activity.py" --vault "$VAULT" watdeedik $ARGUMENTS
   ```

## Outputregels

- Compact antwoord met bronrefs.
- Bij lege resultaten: zeg dat er geen activity events gevonden zijn.
- Bij parsefouten: toon de machineleesbare fout/suggesties uit het script.
- Geen externe search voor dit command.

Maak een compact KennisBank weeklog. Argumenten: $ARGUMENTS

## Vault-root bepalen

Bepaal de vault-root een keer en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik nooit een hardcoded `~/KennisBank` pad als `$KENNISBANK_VAULT` bestaat.

## Doel

Toon wat er in een week gebeurde, met bronverwijzingen. Default is `vorige week`.

Voorbeelden:
- `/weeklog`
- `/weeklog vorige week`
- `/weeklog deze week --topic "Codex MCP"`
- `/weeklog tussen 2026-07-01 en 2026-07-07`

## Uitvoering

1. Controleer of de activity index bestaat:
   ```bash
   python3 "$VAULT/.claude/scripts/kb-activity.py" --vault "$VAULT" status
   ```
2. Als de index ontbreekt of stale is, bouw hem eerst deterministisch op:
   ```bash
   python3 "$VAULT/.claude/scripts/build-activity-index.py" --vault "$VAULT" --progress-interval 300
   ```
3. Draai daarna de weeklog:
   ```bash
   python3 "$VAULT/.claude/scripts/kb-activity.py" --vault "$VAULT" weeklog $ARGUMENTS
   ```

## Outputregels

- Toon alleen de command-output en een korte slotzin als er waarschuwingen zijn.
- Elke activiteit moet een `source_ref` of expliciete waarschuwing tonen.
- Geen externe search; dit command is lokale temporal recall.
- Bij parsefouten: toon de fout en suggesties uit het script, niet zelf gokken.

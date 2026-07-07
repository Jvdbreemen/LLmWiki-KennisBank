Maak een chronologische KennisBank tijdlijn. Argumenten: $ARGUMENTS

## Vault-root bepalen

Bepaal de vault-root een keer en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik nooit een hardcoded `~/KennisBank` pad als `$KENNISBANK_VAULT` bestaat.

## Doel

Beantwoord temporale vragen met een strikte periodefilter en bronverwijzingen.

Voorbeelden:
- `/timeline vorige week`
- `/timeline 2026-07-03`
- `/timeline tussen 2026-07-01 en 2026-07-07`
- `/timeline onderwerp "Codex MCP" vorige week`

## Uitvoering

1. Controleer of de activity index bestaat:
   ```bash
   python3 "$VAULT/.claude/scripts/kb-activity.py" --vault "$VAULT" status
   ```
2. Als de index ontbreekt of stale is, bouw hem eerst:
   ```bash
   python3 "$VAULT/.claude/scripts/build-activity-index.py" --vault "$VAULT" --progress-interval 300
   ```
3. Draai de timeline:
   ```bash
   python3 "$VAULT/.claude/scripts/kb-activity.py" --vault "$VAULT" timeline $ARGUMENTS
   ```

## Outputregels

- Resultaten buiten de periode niet tonen.
- Bronrefs intact laten.
- Bij topicvragen matchroute tonen als het script die geeft.
- Geen samenvatting verzinnen als er geen events zijn.

Voer een stale-check uit op de KennisBank wiki.

## Vault-root bepalen (VERPLICHT — lees dit eerst)

Bepaal de vault-root ÉÉN keer aan het begin van dit command en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik `$VAULT` voor ELK pad hieronder. Gebruik NOOIT een letterlijk `~/KennisBank`- of `C:\...\KennisBank`-pad: dat negeert de `KENNISBANK_VAULT`-env-var en schrijft naar de verkeerde vault (de oorzaak van een eerdere skeleton-misser).


1. Draai: python3 $VAULT/.claude/scripts/stale-check.py
2. Presenteer de output gegroepeerd:
   - Eerst: artikelen met nieuwere sessielogs (prioriteit — bijwerken)
   - Dan: artikelen zonder recente input (misschien archiveren of markeren als status: stabiel)
3. Vraag welke artikelen bijgewerkt moeten worden, voer dat dan uit

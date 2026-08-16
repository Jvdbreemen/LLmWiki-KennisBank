Toon wat het autonome memory-review de laatste tijd heeft besloten en bied per regel een terugweg. Optioneel filter op onderwerp: $ARGUMENTS

## Vault-root bepalen (VERPLICHT — lees dit eerst)

Bepaal de vault-root ÉÉN keer aan het begin van dit command en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik `$VAULT` voor ELK pad hieronder. Gebruik NOOIT een letterlijk `~/KennisBank`- of `C:\...\KennisBank`-pad: dat negeert de `KENNISBANK_VAULT`-env-var en werkt in de verkeerde vault.

## Doel

Sinds TASK-195 zit er geen mens meer in de beslislus: promoties doet de
grounded verifier (lokaal) of de client-adjudicatie, intrekkingen vereisen
dubbele overeenstemming plus een mislukte weerlegging. Dit command is daarom
GEEN werkwachtrij meer — het is de audit-view: het laat zien wat het systeem
besloot, op welk bewijs, en draait op verzoek een regel terug. Geen enkele
stap in de pijplijn wacht op dit command.

## Stappen

1. Haal beide logboeken op:
   ```
   python3 $VAULT/.claude/scripts/memory-doctor.py promotions --json --limit 30
   python3 $VAULT/.claude/scripts/memory-doctor.py closed --json --limit 30
   ```
   Als $ARGUMENTS is opgegeven: filter regels waarvan `stem` of `reason` het
   onderwerp bevat.

2. Presenteer compact, nieuwste eerst, in twee blokken:
   - **Promoties** — stem, route (`stamp`/`windows` = lokaal bewijs,
     `client` = hele-transcript-lezing, `undo` = eerdere terugdraaiing) en
     het bewijscitaat.
   - **Sluitingen** — stem, status (retracted/superseded/expired) en de
     reden. Een autoreview-intrekking vermeldt beide oordelen in de reden.

3. Meld de queue-stand in één regel:
   ```
   python3 $VAULT/.claude/scripts/memory-doctor.py pending --json
   ```
   Tel de entries; dat aantal unverified is wat de volgende
   sweep/autoreview-cyclus oppakt.

4. Terugdraaien — alleen als de gebruiker dat per regel vraagt:
   - verkeerde **promotie**: `python3 $VAULT/.claude/scripts/memory-doctor.py demote <stem>`
     → terug naar `unverified` (de volgende cyclus kijkt opnieuw). Demotie
     zegt "de promotie was voorbarig", niet "de inhoud is fout" — voor dat
     laatste is een sluiting het juiste gereedschap.
   - verkeerde **sluiting**: `python3 $VAULT/.claude/scripts/memory-doctor.py reopen <stem>`
     → terug naar `current`.
   - Draai daarna `python3 $VAULT/.claude/scripts/build-kb-index.py` zodat
     recall de wijziging ziet.

## Regels

- Dit command beslist zelf NIETS en keurt niets goed; het toont en draait
  terug op expliciet verzoek. De pijplijn wacht nergens op een mens.
- Terugdraaien uitsluitend via `memory-doctor.py demote|reopen` — nooit met
  een eigen frontmatter-edit; de tooling schrijft de audit-regel.
- Beide logboeken zijn append-only (`$VAULT/.claude/memory-promote-log.jsonl`
  en `memory-closed-log.jsonl`); elke actie, ook een terugdraaiing, laat een
  regel achter.
- Taal: volg de gebruiker.

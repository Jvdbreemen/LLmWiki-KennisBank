Verwerk de bestanden in $VAULT/00-inbox/.

## Vault-root bepalen (VERPLICHT — lees dit eerst)

Bepaal de vault-root ÉÉN keer aan het begin van dit command en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik `$VAULT` voor ELK pad hieronder. Gebruik NOOIT een letterlijk `~/KennisBank`- of `C:\...\KennisBank`-pad: dat negeert de `KENNISBANK_VAULT`-env-var en schrijft naar de verkeerde vault (de oorzaak van een eerdere skeleton-misser).


## Stap 1: Scan
Draai: python3 $VAULT/.claude/scripts/intake-scan.py
Als de output "empty": true is: rapporteer "00-inbox is leeg" en stop.

## Stap 2: Verwerk per bestand
Voor elk bestand, voer de suggested_action uit:

**add_frontmatter**: Voeg YAML frontmatter toe, verplaats naar $VAULT/01-raw/
**move_to_raw**: Verplaats naar $VAULT/01-raw/
**convert_to_markdown**: Schrijf als .md met frontmatter naar $VAULT/01-raw/
**fetch_and_convert**: Haal URL op via WebFetch, sla op als $VAULT/01-raw/raw-[datum]-[slug].md
**extract_text**: Rapporteer dat PDF-verwerking handmatig moet
**describe_and_tag**: Beschrijf afbeelding, sla beschrijving op als .md in $VAULT/07-media/

## Stap 3: Verwijder verwerkte bestanden uit 00-inbox

## Bevestiging
Rapporteer per bestand: pad, actie, resultaat.

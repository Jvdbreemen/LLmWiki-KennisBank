Verwerk de bestanden in ~/KennisBank/00-inbox/.

## Stap 1: Scan
Draai: python3 ~/KennisBank/.claude/scripts/intake-scan.py
Als de output "empty": true is: rapporteer "00-inbox is leeg" en stop.

## Stap 2: Verwerk per bestand
Voor elk bestand, voer de suggested_action uit:

**add_frontmatter**: Voeg YAML frontmatter toe, verplaats naar ~/KennisBank/01-raw/
**move_to_raw**: Verplaats naar ~/KennisBank/01-raw/
**convert_to_markdown**: Schrijf als .md met frontmatter naar ~/KennisBank/01-raw/
**fetch_and_convert**: Haal URL op via WebFetch, sla op als ~/KennisBank/01-raw/raw-[datum]-[slug].md
**extract_text**: Rapporteer dat PDF-verwerking handmatig moet
**describe_and_tag**: Beschrijf afbeelding, sla beschrijving op als .md in ~/KennisBank/07-media/

## Stap 3: Verwijder verwerkte bestanden uit 00-inbox

## Bevestiging
Rapporteer per bestand: pad, actie, resultaat.

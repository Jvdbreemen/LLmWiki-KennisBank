Daag een stelling of beslissing uit met wat de vault al weet. Stelling/beslissing: $ARGUMENTS

## Doel

Sparringstool voor journalistiek denken. Geen essay, geen algemene kennis. Alleen wat er al in de vault staat.

## Stappen

1. Neem de stelling of beslissing uit $ARGUMENTS.

2. Zoek de meest relevante vault-artikelen:
   ```
   python3 ~/KennisBank/.claude/scripts/kb-search.py "$ARGUMENTS" --top 5
   ```
   > Geef de stelling als ÉÉN geciteerd argument en ontsnap interne aanhalingstekens (anders breekt de shell).

   Parseer de JSON-uitvoer: een lijst van `{path, score, snippet}`.

3. **Als de lijst leeg is** (geen resultaten boven de drempelwaarde):
   Meld dit direct: "Niets in de vault dat hierop aansluit."
   Stop hier. Val niet terug op algemene kennis.

4. **Als er matches zijn:**
   Lees elk gevonden artikel volledig.

5. Produceer een analyse UITSLUITEND op basis van de gelezen vault-artikelen. Geen buiten-vault kennis, geen uitvinding.

   Geef per punt een `[[bron-artikel]]` wikilink op basis van de bestandsstam (filename zonder extensie) van het gevonden pad.

   Structuur:

   **Tegenargumenten / weerleggingen**
   Wat in de vault weerspreken of ondermijnen de stelling?

   **Precedenten / eerdere beslissingen**
   Welke eerdere gevallen of beslissingen in de vault zijn relevant?

   **Blinde vlekken / aannames**
   Welke aannames maakt de stelling die de vault in twijfel trekt of niet onderbouwt?

## Regels

- Elke claim citeert zijn bron als `[[artikel-naam]]`.
- Niets uitvinden. Niets afleiden buiten de vault.
- Compact en direct. Dit is een sparringpartner, geen betoog.
- Bij lege resultaten: zeg het eerlijk en stop.

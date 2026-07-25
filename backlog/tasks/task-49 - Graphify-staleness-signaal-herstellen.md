---
id: TASK-49
title: Graphify staleness-signaal herstellen
status: Done
assignee: []
created_date: '2026-07-25 03:33'
updated_date: '2026-07-25 07:50'
labels:
  - bug
  - graphify
  - docs
dependencies: []
priority: medium
ordinal: 63000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De `.needs-rebuild`-vlag die aangeeft dat de kennisgraaf verouderd is, werkt nergens.

De vlag wordt alleen geschreven door markdown-commands (`commands/sessielog.md`, `commands/wiki.md`), maar `scripts/build-embed-index.py:69-74` verwijdert hem onvoorwaardelijk bij elke SessionStart — gegate op de volstrekt ongerelateerde `embed_index`-toggle. Beide lezers (`commands/sessiestart.md` en de Atlas-sidecar) melden daardoor altijd "niet stale". Erger: `tests/test_build_embed_index_gate.py:41-47` legt dit gedrag vast als bedoeld, dus de test cementeert de bug en moet in dezelfde wijziging mee.

Context die de implementeerder moet weten: de producent van de graaf zit NIET in deze repository. `graphify-out/graph.json` wordt door geen enkele regel code hier geschreven; producent is een globale skill bovenop een los geïnstalleerd PyPI-pakket. Deze repo maakt alleen de map (`setup.sh`) en `doctor.sh` controleert uitsluitend het bestaan van die map, nooit van het bestand. Vijf consumenten lezen de graaf en falen allemaal open. De externe skill kent de `.needs-rebuild`-vlag niet en doet zijn eigen change-detection.

Daarnaast staan er drie doc-claims over dit onderwerp die aantoonbaar onjuist zijn: `CONFIGURATION.md` noemt één lezer van `graph.json` waar er vijf zijn, beweert dat de graphify-skill de vlag leegt (die kent hem niet), en `TROUBLESHOOTING.md` beschrijft een vlag die "nooit wordt geleegd" terwijl hij elke SessionStart verdwijnt.

Let bij de lezerskant op het verschil tussen "bestand bestaat" en "bestand is niet leeg": als de vlag ooit met truncate in plaats van verwijderen wordt geleegd, divergeren de lezers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `build-embed-index.py` raakt de graphify-rebuild-vlag niet meer aan
- [ ] #2 `tests/test_build_embed_index_gate.py` assert dat een embed-run de vlag ongemoeid laat; deze test is vandaag rood
- [ ] #3 De lezer in `commands/sessiestart.md` test op een niet-lege vlag in plaats van op louter bestaan
- [ ] #4 `doctor.sh` rapporteert de aan- of afwezigheid van `graph.json` zelf, niet alleen van de map
- [ ] #5 De drie onjuiste doc-claims over graphify in CONFIGURATION.md en TROUBLESHOOTING.md zijn gecorrigeerd naar wat de code doet
- [ ] #6 De testwijziging mockt de embedding-cache, zodat de test niet de echte cache van tientallen megabytes parseert
- [ ] #7 De volledige testsuite draait groen
<!-- AC:END -->

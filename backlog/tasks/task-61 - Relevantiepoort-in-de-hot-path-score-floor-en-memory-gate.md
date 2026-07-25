---
id: TASK-61
title: 'Relevantiepoort in de hot path: score-floor en memory-gate'
status: Done
assignee: []
created_date: '2026-07-25 05:54'
updated_date: '2026-07-25 07:35'
labels:
  - hot-path
  - retrieval
  - structureel
dependencies: []
priority: high
ordinal: 71000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De retrieval-hot-path injecteert onvoorwaardelijk de top-k. `_kbindex.search` fuseert vector- en FTS-rankings met RRF en snijdt af op `out[:k]` zonder ondergrens, dus een prompt zonder ook maar één relevante treffer krijgt alsnog de drie minst-slechte documenten geïnjecteerd. Het memory-blok heeft bovendien helemaal geen relevantiepoort: de cosinus-drempel plus FTS-treffer geldt alleen voor de wiki-kant. Dat is precies de onterechte onderbreking die noord-ster 6 in CLAUDE.md verbiedt.

RRF-scores zijn niet vergelijkbaar met cosinus, dus de drempel moet ergens op toegepast worden dat wél betekenis heeft. De KNN levert de afstand al op; die wordt vandaag weggegooid. Uit die afstand volgt de cosinus gratis, mits de vectoren genormaliseerd zijn. Een aparte SQL-functie aanroepen om de cosinus te berekenen kost 118 ms per aanroep en dus 236 ms per prompt — onaanvaardbaar op deze weg.

De normalisatie-aanname moet off de hot path gecontroleerd worden, bij het bouwen van de index, en als vlag in de metadata landen. Ontbreekt die vlag, dan geen floor: dat houdt het gedrag op een bestaande index exact zoals het nu is, en laat de wijziging pas ingaan na een herbouw.

Let ook op de FTS-kant: de gate en de ranking gebruiken nu verschillende expressies, en de rauwe prompt loopt stuk op leestekens die FTS5 als syntax leest, waarna de fout stil wordt ingeslikt. Eén gedeelde expressie-bouwer voor beide.

VERIFICATIE: dit verandert de ranking voor elke prompt. De eval-harnas moet vóór en na gedraaid worden op een echte vault met lokaal embedmodel; CI kan dat niet. Neem de cosinus daarom op in de teruggegeven hits, anders kan de harnas de drempel niet eens meten.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De zoekfunctie geeft per treffer een vergelijkbare relevantiescore terug plus een indicatie of de FTS-kant hem vond
- [ ] #2 De relevantiescore komt uit de afstand die de KNN al teruggeeft, zonder extra database-functie op de hot path
- [ ] #3 De normalisatie-aanname wordt bij het bouwen van de index gecontroleerd en als vlag vastgelegd; ontbreekt de vlag dan wordt er geen drempel toegepast en blijft het gedrag ongewijzigd
- [ ] #4 Zowel het wiki- als het memory-blok past een drempel toe voordat er afgekapt wordt op k, niet erna
- [ ] #5 De memory-drempel is een eigen expliciete waarde en erft niet van de wiki-drempel
- [ ] #6 Gate en ranking gebruiken dezelfde FTS-expressie, en een prompt met leestekens levert geen stil ingeslikte fout meer op
- [ ] #7 Test met tegengesteld gerichte vectoren, niet met vectoren die toevallig boven de drempel liggen; een test die ook zonder de fix slaagt telt niet
- [ ] #8 Test: bij k=1 met de beste gefuseerde treffer onder de drempel en de tweede erboven komt de tweede terug
- [ ] #9 De relevantiescore staat in de teruggegeven hits zodat de eval-harnas hem kan meten
- [ ] #10 De volledige testsuite draait groen
<!-- AC:END -->

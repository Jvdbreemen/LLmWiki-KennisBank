---
id: TASK-62
title: JSON-embeddingcache uit de hot path halen
status: To Do
assignee: []
created_date: '2026-07-25 05:54'
labels:
  - hot-path
  - performance
  - structureel
dependencies:
  - TASK-61
priority: high
ordinal: 72000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De retrieval-hook parseert bij elke niet-triviale prompt de volledige embedding-cache als JSON — tientallen megabytes — en draait daarna een cosinus-lus in pure Python over de hele corpus, puur om te bepalen of er iets relevants is. Dat werk is al gedaan door de vectorindex, die er precies voor bestaat.

Niet verwijderen maar verplaatsen: de JSON-cache is de terugvalweg voor een vault waarvan de index ontbreekt of stuk is. Zet hem achter de tak die pas draait als de index geen treffers gaf. Dan is de winst dezelfde en gaat een kapotte-index-vault niet donker.

Twee kleinere posten op dezelfde weg: het memory-blok voert een module twee keer uit, en de gebruikstelemetrie opent per stem een eigen databaseverbinding waar één batch-query volstaat.

Laat de in-process budget-timer vallen die eerder is overwogen: die kan alleen vuren nádat de trage fase al voorbij is, en dupliceert de harde timeout die de client zelf al afdwingt.

Let op bij het testen: een van de bestaande tests die dit raakt draait alleen wanneer een integratie-omgevingsvariabele gezet is, en is dus onzichtbaar in CI.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De wiki-tak van de retrieval-hook raakt de JSON-cache niet meer wanneer de index treffers oplevert
- [ ] #2 De JSON-cache blijft werken als terugvalweg wanneer de index geen treffers geeft
- [ ] #3 Een vault zonder JSON-cache maar met een werkende index levert nog steeds resultaten; vandaag geeft dat een leeg blok
- [ ] #4 Het memory-blok voert geen module dubbel uit
- [ ] #5 De gebruikstelemetrie haalt de tellers voor alle stems in één databaseverbinding op
- [ ] #6 De bestaande tests die de oude volgorde vastleggen zijn meegewijzigd, inclusief de test die alleen onder een integratievlag draait
- [ ] #7 De volledige testsuite draait groen
<!-- AC:END -->

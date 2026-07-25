---
id: TASK-64
title: Eén gedeclareerd hook-plafond en herstelbare lockstaleness
status: To Do
assignee: []
created_date: '2026-07-25 05:55'
labels:
  - hooks
  - structureel
dependencies:
  - TASK-63
priority: medium
ordinal: 74000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De timeouts van de lifecycle-hooks staan verspreid: de Copilot-integratie declareert een eigen waarde, de Codex-installatie een andere, en voor Claude wordt er helemaal geen timeout geschreven — geen enkel bestand in deze repo legt vast wat de default daar is. Dat maakt het onmogelijk om te redeneren over het budget, en het verklaart waarom de coördinator zijn eigen plafond kon overschrijden.

Breng de plafonds samen op de plek die al de enige bron van waarheid is voor de hookset, en laat de drie installatiewegen daaruit lezen. Schrijf de waarde alleen wanneer hij ontbreekt, zodat een gebruiker die zelf een timeout heeft gezet die behoudt.

Koppel daarna de vervaltijd van het onderhoudslock aan datzelfde plafond in plaats van aan een los getal.

Twee dingen die de implementatie kunnen breken. De Copilot-module heeft geen zoekpad-aanpassing op moduleniveau, dus een import van de manifest-module bovenaan dat bestand faalt in de tests; importeer lazy of geef de waarden door vanuit de installer. En de lockverwerving moet een negatieve leeftijd afvangen: een klokverzetting maakt het lock anders permanent ongeldig of juist permanent geldig.

Deze taak mag niet vóór het detachen van de indexbouwers landen. Een lager plafond declareren terwijl de worst case nog hoger ligt, maakt de situatie strikt slechter.

De Claude-hooktimeout-sleutel is nergens in deze repo primair vastgelegd. Verifieer empirisch welke sleutel de client leest voordat je hem gaat schrijven.

Bij het testen: parametriseer de stale-test niet op de constante zelf, want dan slaagt hij bij elke waarde en toetst hij niets.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De hook-plafonds staan op één plek, in de module die al de bron van waarheid voor de hookset is
- [ ] #2 Alle drie de installatiewegen lezen die plafonds; geen client declareert nog een eigen los getal
- [ ] #3 De registratie schrijft een timeout alleen wanneer die ontbreekt, zodat een handmatig gezette waarde behouden blijft
- [ ] #4 De sleutel die de Claude-client voor hook-timeouts leest is empirisch geverifieerd voordat er naar geschreven wordt
- [ ] #5 De vervaltijd van het onderhoudslock is afgeleid van het gedeclareerde plafond en niet van een los getal
- [ ] #6 Een afgebroken onderhoudscyclus herstelt binnen één plafond; een test toont dat aan zonder de constante zelf te parametriseren
- [ ] #7 Een negatieve lockleeftijd door een klokverzetting leidt niet tot een permanente blokkade
- [ ] #8 Een bestaande registratie zonder timeout wordt bij de volgende setup aangevuld
- [ ] #9 De volledige testsuite draait groen
<!-- AC:END -->

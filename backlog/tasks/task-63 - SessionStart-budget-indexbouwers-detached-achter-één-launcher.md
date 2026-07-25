---
id: TASK-63
title: 'SessionStart-budget: indexbouwers detached achter één launcher'
status: Done
assignee: []
created_date: '2026-07-25 05:54'
updated_date: '2026-07-25 07:35'
labels:
  - performance
  - hooks
  - structureel
dependencies: []
priority: high
ordinal: 73000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De sessiestart-coördinator draait de indexbouwers blokkerend. Worst case is ongeveer 210 seconden voor Claude en Codex en 300 seconden voor Copilot — terwijl de Copilot-integratie zelf een lagere timeout declareert dan die 300, zodat de coördinator zijn eigen plafond kan overschrijden. De capture-fase en de import staan bovendien buiten de versheidspoort, dus die betaal je ook wanneer er niets te doen is.

Dat botst frontaal met noord-ster 1 in CLAUDE.md: zware verwerking hoort off de interactieve weg, op schrijftijd of achtergrond.

Verplaats de bouwers naar één achtergrondproces achter een lock, zodat de sessiestart alleen nog de goedkope dingen blokkerend doet.

Twee valkuilen die de implementatie moet respecteren. Ten eerste moet de geheugensweep in dezelfde worker meelopen: zolang de bestaande sweep-launcher zelf nog een indexbouw start, is de claim van één schrijver onwaar en houd je twee processen die dezelfde database schrijven. Ten tweede mag de faalrapportage niet afgaan op de aanwezigheid van uitvoer op de foutstroom: de activity-bouwer schrijft daar voortgang naartoe, dus dat vuurt op elke gezonde run. Gebruik het bestaande rapportagemechanisme dat onderscheid maakt tussen relevante en routinematige meldingen.

Naamgeving: kies een naam die niet botst met de bestaande onderhoudsmodule.

De vervaltijd van het lock moet strikt boven de som van de per-bouwer-timeouts liggen, anders kan een tweede sessie een nog draaiende worker als verlopen beschouwen.

Twee bestaande sessiestart-tests leggen de blokkerende volgorde vast en moeten meewijzigen; dat is bedoeld gedrag, geen regressie.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De indexbouwers draaien niet langer blokkerend in de sessiestart-coördinator
- [ ] #2 Er is één achtergrondproces achter een lock dat alle bouwers plus de geheugensweep draait, zodat er nooit twee processen tegelijk dezelfde index schrijven
- [ ] #3 De bestaande sweep-launcher start geen eigen indexbouw meer
- [ ] #4 Het blokkerende deel van de sessiestart blijft ruim onder het gedeclareerde plafond van elke client
- [ ] #5 Faalrapportage gebruikt het bestaande onderscheid tussen relevante en routinematige uitvoer; voortgang op de foutstroom leidt niet tot een valse melding
- [ ] #6 De vervaltijd van het lock ligt strikt boven de som van de per-bouwer-timeouts
- [ ] #7 Een tweede sessie die start terwijl de worker draait, start geen tweede worker
- [ ] #8 De sessiestart-tests die de oude blokkerende volgorde vastlegden zijn meegewijzigd
- [ ] #9 De volledige testsuite draait groen
<!-- AC:END -->

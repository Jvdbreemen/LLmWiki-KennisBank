---
id: TASK-47
title: 'safe-edit: padnormalisatie en encoding-hardening voor niet-ASCII vaultpaden'
status: Done
assignee: []
created_date: '2026-07-25 03:32'
updated_date: '2026-07-25 07:50'
labels:
  - bug
  - windows
  - wiki
dependencies: []
priority: high
ordinal: 61000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De dirty-guard in `scripts/safe-edit.py` heeft een uitzondering die het doelbestand zelf toestaat vuil te zijn. Die uitzondering vuurt op Windows nooit: rond `:234` wordt het pad met de OS-scheidingsteken opgebouwd (`02-wiki\artikel.md`) terwijl `git status --porcelain` altijd forward slashes emitteert (`02-wiki/artikel.md`). Een repo waarin alléén het doelbestand vuil is, wordt daardoor geweigerd met exit 3. Gereproduceerd; geen enkele test pint deze uitzondering vast.

Daarnaast twee encoding-problemen op hetzelfde pad. `git status --porcelain` quote paden met niet-ASCII tekens tenzij `core.quotepath=false` is gezet, en de subprocess-decodering gebruikt de platform-default codec — op een Nederlandse Windows-installatie cp1252. Een pad als `ideeën.md` of een cyrillische bestandsnaam geeft dan een verkeerd antwoord of een `UnicodeEncodeError` met lege stdout, wat voor de aanroeper niet te onderscheiden is van een crash.

Deze taak hangt af van de rollback-taak en mag daar niet vóór landen: zonder rollback zorgt het repareren van de self-exception ervoor dat safe-edit ongecommitte WIP in het doelbestand overschrijft bij een mislukte commit. Nu wordt dat scenario per ongeluk afgevangen doordat de guard te streng is.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De vergelijking tussen het doelpad en de porcelain-uitvoer gebruikt aan beide kanten forward slashes
- [ ] #2 De git-aanroepen draaien met `core.quotepath=false` zodat niet-ASCII paden ongequote terugkomen
- [ ] #3 Subprocess-uitvoer wordt expliciet als UTF-8 gedecodeerd met een vervangingsstrategie, niet met de platform-default codec
- [ ] #4 De JSON-uitvoer is ASCII-veilig, zodat een niet-cp1252 pad geen UnicodeEncodeError met lege stdout oplevert
- [ ] #5 Test: een repo waarin alleen het doelbestand vuil is, levert exit 0 in plaats van exit 3 (vandaag rood)
- [ ] #6 Test: hetzelfde met een niet-ASCII bestandsnaam levert exit 0
- [ ] #7 Test: een vuil NIET-doelbestand met een niet-cp1252 teken levert exit 3 en een stdout die als JSON parseert
- [ ] #8 De volledige testsuite draait groen
<!-- AC:END -->

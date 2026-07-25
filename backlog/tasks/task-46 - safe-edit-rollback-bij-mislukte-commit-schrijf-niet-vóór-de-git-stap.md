---
id: TASK-46
title: 'safe-edit: rollback bij mislukte commit, schrijf niet vóór de git-stap'
status: Done
assignee: []
created_date: '2026-07-25 03:32'
updated_date: '2026-07-25 07:50'
labels:
  - bug
  - data-integrity
  - wiki
dependencies: []
priority: high
ordinal: 60000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`scripts/safe-edit.py` is het schrijfpad naar gecureerde wiki-content: stap 3.5 van `/wiki` en de loser-edits van `/reconcile` lopen erdoorheen. Het "git-vangnet" uit de docstring is geen stash, branch of backup, maar weigeren-bij-vuile-boom plus een auto-commit ná de write.

De volgorde is fout. `target.write_text` staat op `:295`, de `git add` en `git commit` op `:294-318`. Faalt de commit — een falende pre-commit hook, een niet-schrijfbare index, een lockfile — dan is het artikel al overschreven én staged, exit 4, en er is geen rollback. Daarna weigert elke volgende aanroep zonder `--force` omdat de boom nu vuil is, en `commands/wiki.md:60` en `commands/reconcile.md:55` verbieden `--force` expliciet. Eén mislukte commit blokkeert dus het hele `/wiki`-schrijfpad tot handmatig ingrijpen.

De realistische trigger is niet een exotische git-hook maar een niet-ASCII vaultpad: daar reproduceert dit vandaag, met een overschreven artikel als resultaat.

Aandachtspunten voor de implementatie: bewaar de oorspronkelijke inhoud als bytes, niet als tekst — een tekst-roundtrip herschrijft LF naar CRLF op schijf. Neem bij het rapporteren van de fout zowel stderr als stdout mee: bij een falende git-hook is stderr leeg en staat de reden in stdout. Een nieuw aangemaakt bestand moet bij rollback verdwijnen, niet leeg achterblijven.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Bij een mislukte `git add` of `git commit` wordt het doelbestand teruggezet naar de exacte byte-inhoud van vóór de aanroep
- [x] #2 Een bij deze aanroep nieuw aangemaakt bestand wordt bij rollback verwijderd, niet leeg achtergelaten
- [x] #3 Na een rollback is het doelbestand niet meer staged (de index is teruggedraaid voor dat pad)
- [x] #4 De JSON-uitvoer bij een faalpad bevat een expliciete indicatie dat er is teruggerold, en de faalreden bevat zowel stderr als stdout van de git-aanroep
- [x] #5 `tests/test_safe_edit.py` dekt: (a) exit 4 met teruggezette byte-identieke inhoud, (b) verwijderd nieuw bestand, (c) een volgende edit slaagt weer zodra de faaloorzaak weg is
- [x] #6 Alle bestaande tests in `tests/test_safe_edit.py` blijven groen
- [x] #7 De volledige testsuite draait groen
<!-- AC:END -->

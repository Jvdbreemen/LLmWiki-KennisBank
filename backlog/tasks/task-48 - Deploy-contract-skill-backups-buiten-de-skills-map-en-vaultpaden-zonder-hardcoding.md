---
id: TASK-48
title: >-
  Deploy-contract: skill-backups buiten de skills-map en vaultpaden zonder
  hardcoding
status: Done
assignee: []
created_date: '2026-07-25 03:33'
updated_date: '2026-07-25 07:50'
labels:
  - bug
  - deploy
  - adr-0002
dependencies: []
priority: high
ordinal: 62000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Twee defecten in wat er tijdens installatie en upgrade de gebruikersomgeving in gaat.

**1. Upgrade-backups landen in de map die de host scant.** `skills/kennisbank-upgrade/SKILL.md` schrijft back-ups weg als `<naam>.pre-<tag>.bak` binnen `~/.claude/skills/`. Dat is precies de map waaruit de client skills laadt. Gevolg: verouderde skill-versies staan triggerbaar naast de echte, met identieke `description`, dus de agent kan de oude kiezen. Op de machine van de auteur staan er vandaag drie zo in de roster. De gecorrigeerde locatie helpt pas bij de vólgende upgrade, dus een opruimstap voor bestaande back-ups en een doctor-signaal zijn het eigenlijke werk.

**2. Hardcoded vaultpaden in geshipte artefacten.** `CLAUDE.md.template` bevat `~/KennisBank`-paden en `setup.sh:327` kopieert dat bestand verbatim naar de vault, terwijl `$VAULT` in datzelfde script wél `KENNISBANK_VAULT` eert. Op een vault met een andere naam wijst de gedeployde `CLAUDE.md` dus naar een niet-bestaande map. Hetzelfde geldt voor `skills/autoresearch/SKILL.md`. Dit is een geshipte schending van ADR-0002, dat hardcoded vaultpaden verbiedt.

Let op bij de fix: `CLAUDE.md` is user-owned en wordt door `setup.sh` bewust nooit overschreven. De correctie bereikt dus alleen nieuwe installaties; bestaande vaults hebben een doctor-signaal nodig. Gebruik de shell-conventie die elke `commands/*.md` al hanteert in plaats van een nieuw templating-mechanisme. De doctor-conditie mag niet zijn "vault verschilt van de default" — in elke deploytest zijn die identiek.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Upgrade-backups van skills worden buiten `~/.claude/skills/` geplaatst, zodat verouderde kopieën niet triggerbaar zijn
- [ ] #2 De upgrade-skill bevat een stap die bestaande `.bak`-skills uit de skills-map opruimt
- [ ] #3 `doctor.sh` geeft WARN wanneer er `.bak`-items in de skills-map staan
- [ ] #4 `CLAUDE.md.template` en `skills/autoresearch/SKILL.md` bevatten geen hardcoded vaultpad meer maar resolven de vault via de bestaande shell-conventie
- [ ] #5 Er is een test die shell-fences in commands en skills scant op hardcoded vaultpaden en die vandaag rood is; prozaregels buiten codefences worden niet meegenomen
- [ ] #6 `doctor.sh` waarschuwt wanneer een bestaande gedeployde `CLAUDE.md` nog een hardcoded vaultpad bevat, zonder aan te nemen dat de vault een niet-default naam heeft
- [ ] #7 De volledige testsuite draait groen
<!-- AC:END -->

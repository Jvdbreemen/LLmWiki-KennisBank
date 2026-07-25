---
id: TASK-54
title: 'Backlog-integriteit: ID-botsingen, niet-gecommitte taken en lege milestones'
status: Done
assignee: []
created_date: '2026-07-25 03:35'
updated_date: '2026-07-25 07:50'
labels:
  - governance
  - backlog
  - tech-debt
dependencies: []
priority: medium
ordinal: 68000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
CLAUDE.md wijst Backlog.md aan als enige bron van waarheid voor werk. Inhoudelijk wordt die discipline gedragen — 75 commits raken de takenmap — maar mechanisch lekt het.

**1. Taken die niemand commit.** `backlog/config.yml` zet automatisch committen uit en de gitignore sluit de backlogmap niet uit. Backlog.md schrijft dus bestanden die vervolgens niet in git belanden. Op dit moment staan er meerdere taken untracked, waaronder een taak met status Done wiens enige resultaat in geen enkele commit bestaat, plus een map met onderzoeksdocumentatie die het verste vooruitkijkende architectuurartefact van de repo bevat.

**2. Vier botsende taak-ID's.** Twee paren binnen de takenmap en twee paren over de takenmap en het archief heen. De botsingen zitten precies op de nieuwste, vooruitkijkende items — dus juist waar verwarring het meest kost. Hernummeren mag geen bestaande verwijzingen breken; controleer of andere taken, ADR's of documentatie naar de betrokken nummers verwijzen.

**3. Restanten en lege mappen.** Er staat minstens één archieftaak die door een ander gereedschap is aangemaakt en een duplicaat is van een bestaande taak. De mappen voor documenten, beslissingen en milestones zijn leeg, terwijl twaalf taken een milestone bij naam noemen.

**4. Preventie.** Een CI-test kan untracked bestanden per definitie niet zien; die kant moet dus via een sessiesignaal. Er bestaat al een script dat bij sessiestart de git-toestand tegen de upstream controleert — dat is de logische plek voor een waarschuwing over niet-gecommitte backlogbestanden. Let op dat die controle vóór de vroege returns van dat script moet komen, anders wordt hij overgeslagen zodra er geen upstream is.

Merk op: het uitvoerlogboek onder de superpowers-map is bewust uitgesloten via een geneste gitignore en is géén onderdeel van dit probleem.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Alle taakbestanden en de onderzoeksdocumentatie die Backlog.md heeft geschreven staan in git
- [ ] #2 Geen twee taakbestanden delen nog een ID, ook niet over de takenmap en het archief heen
- [ ] #3 Verwijzingen naar hernummerde taken elders in de repo zijn meegewijzigd
- [ ] #4 Het duplicaat in het archief dat door ander gereedschap is aangemaakt, is verwijderd
- [ ] #5 De milestones die door taken worden genoemd bestaan als milestone-bestand
- [ ] #6 Er is een test die faalt zodra twee taakbestanden hetzelfde ID claimen
- [ ] #7 Bij sessiestart verschijnt een waarschuwing wanneer er niet-gecommitte backlogbestanden zijn; die controle draait ook wanneer er geen upstream is geconfigureerd
- [ ] #8 De volledige testsuite draait groen
<!-- AC:END -->

---
id: TASK-80
title: >-
  Oriëntatie-summary bij sessiestart: counts + trending onderwerpen (idee uit
  Mind)
status: To Do
assignee: []
created_date: '2026-07-26 14:14'
labels:
  - idee-gestolen
  - retrieval
milestone: Agent-geheugen
dependencies: []
references:
  - 'https://github.com/GabrielMartinMoran/mind'
priority: low
ordinal: 90000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Geleend van github.com/GabrielMartinMoran/mind: space_get geeft een goedkope oriëntatie-samenvatting (aantal memories, trending memories) als eerste context voor een agent.

KennisBank /sessiestart geeft al een sessie-check, maar geen compacte "wat leeft er in deze vault"-oriëntatie: aantallen per type, recent gewijzigde/veel geraadpleegde artikelen, actieve taken. Bouw dit als goedkope query op kb-index.db (geen embeddings, sub-seconde, hot-path-budget respecteren) en voeg toe aan /sessiestart en/of SessionStart-hookoutput.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Compacte oriëntatie: documentcounts per type, top-N recent gewijzigde artikelen, actieve backlog-taken
- [ ] #2 Puur SQL op kb-index.db, geen embedding-call; runtime sub-seconde
- [ ] #3 Geïntegreerd in /sessiestart (en optioneel SessionStart-hooktier, opt-in via settings)
- [ ] #4 Output feitelijk en kort, geen log-ruis (noord-ster punt 4)
<!-- AC:END -->

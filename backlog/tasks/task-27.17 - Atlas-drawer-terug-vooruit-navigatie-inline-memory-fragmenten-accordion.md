---
id: TASK-27.17
title: 'Atlas: drawer terug/vooruit-navigatie + inline memory-fragmenten (accordion)'
status: In Progress
assignee: []
created_date: '2026-07-13 22:38'
labels:
  - atlas
  - frontend
  - ux
dependencies: []
references:
  - >-
    docs/superpowers/specs/2026-07-14-atlas-drawer-navigatie-inline-memories-design.md
parent_task_id: TASK-27
priority: medium
ordinal: 47000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
UX-fix voor de inspect-drawer op basis van gebruikersfeedback: (1) wikilink-navigatie heeft geen weg terug; (2) memory-ingangen vervangen het artikel i.p.v. inline te tonen.

Ontwerp goedgekeurd, zie docs/superpowers/specs/2026-07-14-atlas-drawer-navigatie-inline-memories-design.md.

Kern: back/forward-stacks + ←/→ knoppen in de drawer-kop (Alt+←/→), reset bij sluiten of nieuw root-document; memory-entry-points worden accordion-items die het fragment lazy laden via client.doc en cachen per stem, artikel blijft staan. Alleen frontend (inspect.ts, style.css). Na implementatie Tauri-bundle opnieuw bouwen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ←/→ knoppen in de drawer-kop navigeren door de documenthistory; disabled bij lege stack; Alt+←/→ werkt
- [ ] #2 History reset bij drawer sluiten en bij openen van een nieuw root-document vanuit een lens
- [ ] #3 Klik op memory-ingang klapt het fragment inline uit (▸/▾), lazy geladen en per stem gecachet; artikel blijft staan
- [ ] #4 Wikilinks binnen een uitgeklapt fragment gebruiken de drawer-navigatie met werkende terug-knop
- [ ] #5 Laadfout in een fragment toont één foutregel, artikel blijft intact
- [ ] #6 Vitest-tests voor history-stack en accordion toggle/cache draaien groen
- [ ] #7 Tauri-bundle (MSI/NSIS) opnieuw gebouwd met de wijzigingen
<!-- AC:END -->

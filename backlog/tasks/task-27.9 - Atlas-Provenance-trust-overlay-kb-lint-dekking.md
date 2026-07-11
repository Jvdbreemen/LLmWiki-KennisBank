---
id: TASK-27.9
title: Atlas - Provenance/trust-overlay (kb-lint dekking)
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 22:06'
labels:
  - visualization
  - atlas
  - provenance
  - trust
  - lens
dependencies:
  - TASK-27.4
parent_task_id: TASK-27
priority: medium
ordinal: 31900
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Voeg een provenance/trust-overlay toe op de Graph-lens die de
anti-hallucinatiegarantie zichtbaar maakt.

Gedrag:
- Overlay `kb-lint.py`-resultaten op de graph: welke wiki-kernpunten/artikelen
  tracen naar een echte bron (raw-sessie of `05-bronnen/...`) en welke niet.
- Kleurschaal "trust coverage": volledig gesourcete artikelen vs artikelen met
  ontbrekende of niet-resolvende sessie-herkomst (risico).
- Toggle om alleen de "unsourced/at-risk" nodes te tonen, zodat de editor snel
  ziet waar bewijs ontbreekt.
- Node-inspect toont per kernpunt de provenance-link en of die resolveert.
- Overlay is afgeleid van dezelfde lint-logica, niet een eigen heuristiek, zodat
  het consistent is met `/wiki`/`kb-lint`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De overlay markeert unsourced/at-risk nodes conform `kb-lint.py`. Bewijs: fixture met een artikel dat een niet-resolvende sessie-herkomst heeft; test verifieert dat exact dat artikel als at-risk verschijnt en een correct artikel niet.
- [ ] #2 De trust-coverage kleurschaal is datagedreven en verklaard in een legenda. Bewijs: test verifieert de kleur van een bekend gesourcet vs unsourced artikel.
- [ ] #3 De "toon alleen at-risk" toggle werkt. Bewijs: test toggelt en verifieert dat alleen at-risk nodes zichtbaar blijven.
- [ ] #4 Node-inspect toont per kernpunt de provenance-link en resolutiestatus. Bewijs: test verifieert de getoonde links voor een fixture-artikel.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TAURI RE-SCOPE (zie TASK-27 + 27.1-ADR): data LIVE van sidecar-endpoint /provenance (27.2, hergebruikt kb-lint); als overlay op de Graph-lens (27.4) in de TS-frontend. Ongesourcte claims worden live gemarkeerd. Geen statische export. Lens-logica/ACs blijven gelden.
<!-- SECTION:NOTES:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 De overlay hergebruikt kb-lint-uitkomsten (geen duplicaat-heuristiek); data-parity tegen kb-lint output via /provenance.
- [ ] #2 Frontend-test dekt markering, legenda, toggle en inspect; screenshot als bewijs.
- [ ] #3 Lege staat (alles gesourcet) toont een nette '100% provenance' boodschap.
- [ ] #4 Kleurschaal is kleurenblind-vriendelijk en werkt in light/dark.
<!-- DOD:END -->

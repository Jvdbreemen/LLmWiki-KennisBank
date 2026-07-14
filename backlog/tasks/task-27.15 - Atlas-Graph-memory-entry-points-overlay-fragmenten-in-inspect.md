---
id: TASK-27.15
title: Atlas - Graph memory-entry-points-overlay + fragmenten in inspect
status: Done
assignee: []
created_date: '2026-07-12 17:41'
updated_date: '2026-07-12 18:00'
labels:
  - visualization
  - atlas
  - graph
  - memory
  - frontend
dependencies:
  - TASK-27.14
parent_task_id: TASK-27
priority: high
ordinal: 44000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Frontend-helft van de twee-lagen-visualisatie (optie 5+6). Op de Graph-lens een toggle 'memory-ingangen' die per artikel de entry-point-count (uit TASK-27.14) encodeert als grootte/gloed — zo zie je welke kennis goed ontsloten is voor agents en welke artikelen blinde vlekken zijn (0 ingangen). Klik op een artikel → de inspect-drawer toont de lijst memory-fragmenten (ingangen) die naar dat artikel wijzen, met hun type. Geen tweede permanent paneel (linked-view via de bestaande drawer). Pure encoding-functie + vitest; live geverifieerd.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Graph-lens heeft een 'memory-ingangen'-modus die artikelen encodeert op entry-point-count (grootte/gloed), datagedreven + legenda
- [ ] #2 Blinde vlekken (0 ingangen) zijn visueel onderscheidbaar
- [ ] #3 Klik op artikel → inspect toont de fragmenten die ernaar wijzen, met type
- [ ] #4 Pure encoding-helper + vitest; geen console-errors; fail-open lege staat
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Memory-entry-points-overlay + fragmenten in inspect afgerond (commit 1878204). Voltooit de twee-lagen-visualisatie (optie 5+6). Graph-lens 'entry-points'-kleurmodus: artikel gekleurd op #memory-fragmenten die erop wijzen (grijs = blinde vlek, geen ingang voor een agent; helderder blauw = goed ontsloten), met legenda. Counts lazy geladen bij eerste select (eerste /memory-links kan ~47s duren, dan gecached + bij start gewarmd). Inspect-drawer voegt bij een wiki-artikel een 'Memory-ingangen'-sectie toe: de fragmenten die erheen leiden, elk met memory_type en klikbaar → open fragment (linked-view/optie 6 via bestaande drawer, geen tweede paneel). /memory-links levert nu ook per-fragment types. entryPointColor = pure unit-geteste helper.

AC-dekking: #1 entry-points-modus encodeert artikelen op count (kleur) + legenda ✓; #2 blinde vlekken (0) grijs onderscheidbaar ✓; #3 klik artikel → inspect toont fragmenten met type ✓ (live: 'Windows hoge load diagnose' → 24 ingangen, [procedure]-getagd, klikbaar); #4 pure encoding-helper + vitest, geen console-errors, fail-open ✓. 32 sidecar + 13 vitest groen, tsc schoon, build groen. Twee-lagen-visualisatie compleet: wiki = kaart, memory = ingangen als dekkings-overlay + fragmentlijst in de drawer.
<!-- SECTION:FINAL_SUMMARY:END -->

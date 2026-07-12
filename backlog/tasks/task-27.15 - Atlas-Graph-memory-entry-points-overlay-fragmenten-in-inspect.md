---
id: TASK-27.15
title: Atlas - Graph memory-entry-points-overlay + fragmenten in inspect
status: To Do
assignee: []
created_date: '2026-07-12 17:41'
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

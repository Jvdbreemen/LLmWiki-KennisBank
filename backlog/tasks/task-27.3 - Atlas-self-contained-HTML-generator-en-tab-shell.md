---
id: TASK-27.3
title: Atlas - self-contained HTML generator en tab-shell
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 16:43'
labels:
  - visualization
  - atlas
  - generator
  - html
dependencies:
  - TASK-27.2
parent_task_id: TASK-27
priority: high
ordinal: 31300
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouw `scripts/build-atlas.py`: neemt de canonical JSON (26.2) en produceert één
self-contained `<vault>/.claude/atlas.html` met alle JS/CSS inline en de data
ingebed. Lever de app-shell met tab-navigatie waarin de lens-taken (26.4-26.9)
inpluggen.

Eisen:
- Volledig offline: geen `<script src>`/`<link href>` naar het net, geen fetch,
  geen CDN. Graph-lib (keuze uit 26.1) wordt in-repo gevendord en inline
  geembed. Data als inline JSON blob.
- Opent over `file://`: werkt met dubbelklik, zonder webserver.
- Tab-shell: navigatie tussen lenzen (Graph, Time, Memory Health, Timeline,
  Recall, Provenance) met een router die per lens een lege/placeholder-staat
  toont tot die lens geimplementeerd is.
- Theme-aware en leesbaar (light/dark), responsive; brede content scrollt in
  eigen container.
- Header toont vault-naam, `generated_at`, en tellingen (nodes, memories,
  events) uit de payload.
- Fail-open lege staat: als een sectie in de JSON leeg is, toont de lens een
  nette uitleg + de regeneratie-hint, geen JS-error.
- Deterministische output op `generated_at` na (stabiele volgorde).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `build-atlas.py` schrijft één `atlas.html` met inline JS/CSS en ingebedde data; er zijn geen externe resource-verwijzingen. Bewijs: grep op het bestand vindt geen `http(s)://`/`src=`/`href=` naar externe hosts; een test telt externe refs == 0.
- [ ] #2 Het bestand opent en rendert de shell over `file://` zonder server en zonder netwerk. Bewijs: headless browser (Playwright, Chromium op `/opt/pw-browsers`) laadt `file://.../atlas.html` met netwerk geblokkeerd; de tabbar en header renderen; screenshot als artefact.
- [ ] #3 Tab-navigatie schakelt tussen alle geplande lenzen; nog niet gebouwde lenzen tonen een placeholder, geen error. Bewijs: Playwright klikt elke tab; console bevat geen errors; elke tab toont content of placeholder.
- [ ] #4 De header-tellingen komen overeen met de payload. Bewijs: test vergelijkt DOM-tellingen met JSON-tellingen.
- [ ] #5 Lege/ontbrekende secties leiden tot nette lege staat. Bewijs: genereer met een minimale JSON; elke lens toont de lege-staat tekst, console blijft schoon.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Playwright smoke-test (`file://`, netwerk uit) verifieert render + geen console-errors en produceert een screenshot als bewijs.
- [ ] #2 Test bewijst 0 externe resource-requests (network interception leeg).
- [ ] #3 Gevendorde graph-lib heeft een expliciete licentie/versienotitie in de repo.
- [ ] #4 Generator is stdlib-first (templating zonder externe pip-dependency) en idempotent.
<!-- DOD:END -->

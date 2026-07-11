---
id: TASK-27.10
title: 'Atlas - launcher (kennisbank-atlas), doctor, setup en docs'
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 22:06'
labels:
  - visualization
  - atlas
  - command
  - hook
  - doctor
  - setup
  - docs
dependencies:
  - TASK-27.4
parent_task_id: TASK-27
priority: high
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Lever de kennisbank-atlas launcher die de Tauri-app start (dev + bundled), optioneel via een /atlas-command. doctor.sh krijgt een Atlas-sectie (app/bundle aanwezig, build-toolchain-status cargo/tauri, sidecar-health). setup integreert de Atlas-build/install voor geselecteerde agents of documenteert de build. Docs (README/CONFIGURATION/POST-INSTALL) beschrijven installeren en starten.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 kennisbank-atlas start de Tauri-app (dev + bundled); een /atlas-command of launcher opent hem. Bewijs: launch + app verschijnt.
- [ ] #2 doctor.sh rapporteert Atlas-status: app/bundle aanwezig, build-toolchain (cargo/tauri), sidecar-health; 0 FAIL wanneer Atlas niet geinstalleerd (optioneel). Bewijs: doctor atlas-regel.
- [ ] #3 setup integreert de Atlas-build/install of documenteert de build-prerequisites (cargo/tauri). Bewijs: setup-output of docs.
- [ ] #4 Docs (README/CONFIGURATION/POST-INSTALL) beschrijven installeren + starten van de Atlas-app.
- [ ] #5 De acceptatie-smoke uit 27.1 draait groen: app start, sidecar-health, een lens rendert tegen echte data, live recall werkt.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 End-to-end smoke: kennisbank-atlas/atlas start de app -> shell + sidecar + minimaal 1 lens rendert tegen echte data; screenshot als bewijs.
- [ ] #2 Doctor-gedrag heeft tests (Atlas-app aanwezig/afwezig, sidecar-health, build-toolchain).
- [ ] #3 Setup-integratie/build-stappen zijn idempotent en actualiseren bij her-run (upgrade-pad).
- [ ] #4 Documentatie is consistent met de echte command-naam en paden; geen dode verwijzingen.
<!-- DOD:END -->

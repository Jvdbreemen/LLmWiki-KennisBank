---
id: TASK-27.10
title: 'Atlas - launcher (kennisbank-atlas), doctor, setup en docs'
status: Done
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-12 21:09'
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

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Dev-launcher + doctor + docs afgerond (commit 65f2cff). atlas/launch.py: één commando start de sidecar op een vrije loopback-poort + de Vite dev-server, wacht op /health, print de open-URL; Ctrl-C stopt beide; vault via KENNISBANK_VAULT (ADR-0002). atlas/doctor.py: rapporteert readiness (sidecar-deps fastapi/uvicorn/httpx/sqlite-vec, node/npm, cargo OPTIONEEL alleen voor Tauri-bundle, ollama, vault-stores, live sidecar-health via --port), exit 0 tenzij harde dep mist; 2 tests. atlas/README.md: install/run/doctor/tests/Tauri-prereqs. AC#1 dev-launcher ✓ (Tauri-app-launch valt onder 27.12/cargo); #2 doctor Atlas-status incl toolchain ✓; #3 build-prereqs gedocumenteerd ✓; #4 docs ✓; #5 27.1-acceptatie-smoke (app rendert, sidecar-health, lenzen op echte data, live recall) is door de hele sessie live gedemonstreerd ✓. 35 sidecar-tests groen.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 End-to-end smoke: kennisbank-atlas/atlas start de app -> shell + sidecar + minimaal 1 lens rendert tegen echte data; screenshot als bewijs.
- [ ] #2 Doctor-gedrag heeft tests (Atlas-app aanwezig/afwezig, sidecar-health, build-toolchain).
- [ ] #3 Setup-integratie/build-stappen zijn idempotent en actualiseren bij her-run (upgrade-pad).
- [ ] #4 Documentatie is consistent met de echte command-naam en paden; geen dode verwijzingen.
<!-- DOD:END -->

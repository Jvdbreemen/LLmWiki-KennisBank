---
id: TASK-27.12
title: 'Atlas - Tauri packaging en bundling (cargo, gefreezede sidecar)'
status: To Do
assignee: []
created_date: '2026-07-11 21:59'
updated_date: '2026-07-11 22:06'
labels:
  - visualization
  - atlas
  - packaging
  - tauri
dependencies:
  - TASK-27.3
  - TASK-27.10
parent_task_id: TASK-27
priority: medium
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Package de Tauri-app voor distributie: cargo/tauri build, freeze/bundle de Python FastAPI-sidecar (PyInstaller of embeddable), tauri.conf.json bundle-config, Windows-first (WebView2). Behandel de 'twee runtimes packagen'-consequence (ADR-007). Code-signing = gedocumenteerd/out-of-scope.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 tauri build produceert een installeerbaar bundle op Windows dat de gefreezede sidecar meelevert. Bewijs: bundle start zonder losse Python-install.
- [ ] #2 De gebundelde sidecar draait zonder systeem-Python-afhankelijkheid (gefreezed/embedded). Bewijs: start op een schone omgeving.
- [ ] #3 Build-prerequisites (cargo-toolchain, tauri-cli, sidecar-freeze-tool) zijn gedocumenteerd + door doctor/setup detecteerbaar. Bewijs: doctor-regel + docs.
- [ ] #4 Bundle-omvang blijft klein (Tauri <10MB shell + redelijke sidecar-freeze); geen Electron-achtige 100MB+. Bewijs: bundle-grootte.
- [ ] #5 Geen cloud/netwerk in runtime (dep-download alleen bij build); de app draait volledig offline. Bewijs: offline-run.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 tauri build produceert een offline-startend Windows-bundle met gefreezede sidecar; getest op een schone omgeving.
- [ ] #2 Build-prerequisites (cargo/tauri/freeze-tool) zijn gedocumenteerd en door doctor/setup detecteerbaar.
- [ ] #3 Bundle-omvang is gemeten en redelijk (geen Electron-achtige 100MB+).
- [ ] #4 Geen cloud/netwerk in runtime (dep-download alleen bij build); offline-run bewezen.
<!-- DOD:END -->

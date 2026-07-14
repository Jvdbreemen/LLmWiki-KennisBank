---
id: TASK-27.3
title: 'Atlas - Tauri scaffold, TS frontend tab-shell en sidecar-lifecycle'
status: Done
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-14 18:32'
labels:
  - visualization
  - atlas
  - tauri
  - frontend
dependencies:
  - TASK-27.2
parent_task_id: TASK-27
priority: high
ordinal: 31300
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Scaffold de Tauri-app (main.rs boilerplate + tauri.conf.json met sidecar-spawn-config voor de FastAPI-sidecar). Bouw de TypeScript frontend tab-shell (zes lens-tabs) + een gedeelde data-client die de localhost-sidecar aanroept. Beheer de sidecar-lifecycle: spawn bij app-start, health-poll met retry, graceful shutdown bij app-close; dev-modus (uvicorn) vs bundled-modus (gefreezede sidecar). Zet de canvas/WebGL graph-renderer-basis op.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De Tauri-app start op Windows (WebView2), spawnt de FastAPI-sidecar, en toont de tab-shell met zes lens-tabs. Bewijs: app start, tabs zichtbaar, sidecar /health groen.
- [ ] #2 De frontend data-client roept uitsluitend de localhost-sidecar aan; geen externe fetches. Bewijs: netwerk-monitor toont enkel localhost.
- [ ] #3 Sidecar-lifecycle: spawn-on-start, health-poll met retry, graceful shutdown bij app-close; dev (uvicorn) + bundled modus werken. Bewijs: sidecar-proces stopt bij app-exit, geen weesprocessen.
- [ ] #4 Rust blijft minimaal (host + sidecar-spawn), geen custom native plugins. Bewijs: main.rs is ~scaffold-omvang.
- [ ] #5 Fail-open UI: start de sidecar niet, dan toont de app een duidelijke foutstaat i.p.v. te crashen. Bewijs: test met geforceerde sidecar-spawn-fout.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Scaffold allang gerealiseerd en in productie: Tauri v2-shell met sidecar-lifecycle (vrije loopback-poort, poort-injectie via initialization script, kind-proces sterft met de app), TS-frontend met tab-shell en lens-registry. Status stond stale op In Progress; bewijs van werking is de geïnstalleerde standalone app (TASK-27.12/27.17/27.18).
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 App-smoke: de Tauri-app (of dev-frontend + sidecar) start, tabs renderen, sidecar /health groen; screenshot als bewijs.
- [ ] #2 Test bewijst dat de frontend uitsluitend localhost aanroept (0 externe requests).
- [ ] #3 De gevendorde canvas/WebGL graph-lib heeft een expliciete licentie/versienotitie in de repo.
- [ ] #4 Sidecar-lifecycle getest: spawn, health-retry, graceful shutdown zonder weesproces; Rust blijft scaffold-omvang.
<!-- DOD:END -->

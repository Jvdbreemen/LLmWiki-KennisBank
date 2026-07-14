---
id: TASK-27
title: >-
  EPIC: KennisBank Atlas - soevereine, lokale visualisatie van kennis, geheugen
  en tijd
status: Done
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-13 07:07'
labels:
  - epic
  - visualization
  - atlas
  - memory
  - wiki
  - temporal
dependencies: []
references:
  - docs/superpowers/specs/2026-07-11-knowledge-visualization-atlas-design.md
  - 'https://arxiv.org/abs/2501.13956'
  - 'https://github.com/getzep/graphiti'
  - 'https://github.com/vladignatyev/brain-map-skill'
  - 'https://github.com/rohitg00/agentmemory'
  - 'https://github.com/sachitrafa/YourMemory'
  - 'https://mem0.ai/blog/graph-memory-solutions-ai-agents'
  - docs/adr/0004-atlas-tauri-architecture.md
priority: high
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Epic: KennisBank Atlas — standalone lokale desktop-app.

Doel: geef een mens een soevereine, lokale manier om de kennis (02-wiki), het geheugen (09-memory) en de temporele dimensie (kb-activity.db) te bekijken en te bevragen, zonder Obsidian, externe plugin of cloud.

Probleem (zie docs/superpowers/specs/2026-07-11-knowledge-visualization-atlas-design.md): de repo produceert geen visueel artefact; de rijk gestructureerde geheugenlaag (typed, bi-temporeel, importance, status, evidence/trust) wordt nergens gevisualiseerd.

ARCHITECTUUR — Tauri standalone app (gekozen na haalbaarheidsanalyse tegen de ECHTE vault-schaal; zie TASK-27.1 ADR):
- Native OS-webview (WebView2 op Windows / WKWebView op macOS), <10MB, lage RAM (vs Electron 100MB+). Rust ~nul: scaffold main.rs + tauri.conf.json (webview-host + sidecar-spawn).
- Frontend: TypeScript + canvas/WebGL force-graph. HARDE reden: de echte graaf heeft 2514 nodes / 3388 links; SVG/d3-force schaalt niet >~1k → WebGL/canvas verplicht. Tab-shell met de zes lenzen.
- Backend: Python FastAPI-sidecar (localhost-only) die de lokale KennisBank-data leest (kb-index.db 813 docs, kb-activity.db 10.868 events, kb-usage.db, 09-memory, graphify-out/graph.json) en LIVE recall doet (query -> Ollama-embedding -> retrieval-waterfall). Hergebruikt _activity/_kbindex/_rank/_memory/kb-recall.
- Volledig lokaal: sidecar op localhost, Ollama lokaal, geen cloud/netwerkbinding naar buiten.

Join-key over alle stores = bestandspad (docs.path = activity_events.source_path = graphify source_file = usage stem).

Zes lenzen (nu live via de sidecar): Graph, bi-temporele Time-slider (valid-as-of), Memory Health (quarantaine/supersede/warmth — editor-in-chief cockpit), Timeline (bi-temporeel, ge-aggregeerd want 10.868 events), Recall Inspector (LIVE waterfall vector+FTS->RRF->rerank), Provenance/trust-overlay (kb-lint).

Kost (ADR-007-lijn): Rust-toolchain bij build + twee runtimes packagen (Python-sidecar + webview).

Niet-doel: geen hosted platform, geen cloud, geen netwerkbinding naar buiten (localhost-sidecar + lokale Ollama mag); geen Obsidian/Understand-Anything-afhankelijkheid; geen samenvatting zonder bewijslinks (elke node/panel traceert naar bronfile/event).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Er is een geneste backlog onder deze epic die Tauri-ADR/design, de FastAPI-sidecar-API, de Tauri-scaffold + TS-frontend-shell, elke lens, launch/doctor/setup/docs, packaging en performance dekt; elke child heeft concrete AC + bewijs/verificatie-eis. Bewijs: ls backlog/tasks/task-27.* toont children met AC- en DoD-blok.
- [ ] #2 De Atlas start als Tauri-app (native webview laadt de gebundelde frontend); de FastAPI-sidecar serveert data uitsluitend over localhost; GEEN externe/cloud-requests (alleen localhost-sidecar + optioneel lokale Ollama). Bewijs: start de app, netwerk-monitor toont enkel localhost/Ollama, geen externe hosts.
- [ ] #3 De Atlas toont minimaal de Graph-lens (canvas/WebGL, performant bij 2514 nodes), de bi-temporele Time-slider en Memory Health; encodings mappen aantoonbaar op echte frontmatter/DB-velden; de Recall Inspector draait een LIVE query-waterfall via de sidecar. Bewijs: per lens een test die renderdata vergelijkt met een directe bronquery; recall-waterfall reproduceerbaar.
- [ ] #4 De oplossing behoudt de noord-ster: local-first, no-cloud default, sidecar localhost-only, sub-seconde interacties, auditeerbaar via source-provenance, fail-open bij ontbrekende index/model/sidecar. Bewijs: doctor-check + performance-budget-test uit de children zijn groen.
- [ ] #5 De epic blijft open tot alle children Done zijn en doctor.sh de Atlas-status rapporteert (app aanwezig, toolchain, sidecar-health). Bewijs: doctor.sh-output bevat een atlas-regel.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Tauri-architectuur; volgorde en afhankelijkheden:
1. TASK-27.1 Tauri-ADR + design (poort; legt architectuur + alternatieven-verwerping vast).
2. TASK-27.2 FastAPI-sidecar + data-API (endpoints per lens; hergebruikt _activity/_kbindex/_rank/_memory).
3. TASK-27.3 Tauri-scaffold + TS-frontend tab-shell + sidecar-lifecycle (dev + bundled).
4. TASK-27.4 Graph-lens (canvas/WebGL) -> 27.5 Time-slider, 27.9 Provenance-overlay.
5. TASK-27.6 Memory Health, 27.7 Timeline (ge-aggregeerd), 27.8 Recall Inspector (LIVE) — hangen aan de shell (27.3).
6. TASK-27.10 Launch (kennisbank-atlas) + doctor + setup + docs.
7. TASK-27.11 Performance/scale hardening (WebGL 2514 nodes, timeline-aggregatie, sidecar-latency) + visuele eval.
8. TASK-27.12 Tauri packaging + bundling (cargo-toolchain, gefreezede Python-sidecar, cross-platform bundle).
<!-- SECTION:PLAN:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
EPIC KennisBank Atlas volledig afgerond (branch feat/atlas-sidecar). Een soevereine, lokale, standalone dashboard-app over de vault: wiki, geheugen, kennisgraaf, tijdlijn en live-retrieval — volledig offline. Alle 16 subtaken Done:
27.1 ADR + design-spec · 27.2 FastAPI-sidecar (8 endpoints, read-only, loopback) · 27.3 TS-frontend shell + lenzen · 27.4 Graph-lens (datagedreven encoding, legenda, filters) · 27.5 bi-temporele Time-slider (pure valid-as-of-filter) · 27.6 Memory Health cockpit · 27.7 Timeline · 27.8 Recall Inspector (waterfall) · 27.9 Provenance-overlay (kb-lint) · 27.10 launcher + doctor + docs · 27.11 perf/LOD + eval · 27.12 Tauri-bundle (MSI/NSIS + gefreezede sidecar) · 27.13 Wordcloud · 27.14 fragment→artikel-linking · 27.15 memory-entry-points-overlay + fragmenten in inspect · 27.16 twee-lagen-graaf (memory-nodes).

Kernresultaat: 7-lens dashboard met markdown-wiki inspect-drawer (klikbare wikilinks/images), twee-lagen-visualisatie (wiki=kaart, memory=ingangen als overlay + satelliet-graaf), en een werkende standalone Windows-installer (MSI 40MB / NSIS 39MB) met gefreezede Python-sidecar. 36 sidecar- + 22 frontend-tests groen. Dev-modus: python3 atlas/launch.py.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Alle child-taken (TASK-27.1 t/m TASK-27.12) zijn Done met hun eigen bewijs.
- [ ] #2 kennisbank-atlas start de Tauri-app op de Windows-vault Kluis (WebView2); alle lenzen renderen tegen echte vault-data.
- [ ] #3 doctor.sh detecteert de Atlas-app, de sidecar-health en de build-toolchain-status.
- [ ] #4 Geen cloud-dependency of externe netwerkbinding toegevoegd (alleen localhost-sidecar + optionele lokale Ollama); de sidecar is FastAPI + stdlib en hergebruikt bestaande scripts.
<!-- DOD:END -->

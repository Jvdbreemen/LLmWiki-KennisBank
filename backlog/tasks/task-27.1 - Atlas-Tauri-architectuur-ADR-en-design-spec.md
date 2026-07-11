---
id: TASK-27.1
title: Atlas - Tauri-architectuur ADR en design spec
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 22:05'
labels:
  - visualization
  - atlas
  - design
  - adr
dependencies: []
parent_task_id: TASK-27
priority: high
ordinal: 31100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Schrijf de Atlas-architectuur-ADR (docs/adr/0004-atlas-tauri-architecture.md) die de Tauri-keuze vastlegt, gegrond in de haalbaarheidsanalyse tegen de ECHTE vault-schaal (2514 graph-nodes/3388 links, 10.868 activity-events, 813 docs).

Architectuur: Tauri-shell (native WebView2/WKWebView, <10MB) + TypeScript/canvas-WebGL frontend + Python FastAPI-sidecar (localhost-only backend) + minimale Rust (host + sidecar-spawn).

De ADR moet ADR-format volgen: status/context, decision, minimaal TWEE verworpen alternatieven met redenen (static self-contained HTML over file:// = schaalt niet naar 2514 nodes met SVG + geen live recall; lokale server+browser = geen app-packaging, los proces; Electron = 100MB+/zware runtime), consequenties (Rust-toolchain bij build + twee runtimes packagen), en een declaratief Enforcement-blok (volledig lokaal, sidecar localhost-only, hergebruik bestaande scripts, geen cloud). Definieer de sidecar-API-contract (endpoints per lens) en de frontend module-grenzen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 docs/adr/0004-atlas-tauri-architecture.md bestaat en is Accepted, met minimaal 2 verworpen alternatieven + redenen, consequenties, en een declaratief Enforcement-blok.
- [ ] #2 De ADR legt de sidecar-API-contract vast (endpoints /graph /timeline /memory-health /recall /provenance /health) met request/response-vorm; elke latere child kan naar een endpoint-definitie verwijzen.
- [ ] #3 De ADR benoemt de exacte tech-keuzes (WebView2/WKWebView, canvas/WebGL-graphlib, FastAPI, Rust-scaffold) en motiveert ze tegen de echte vault-schaal (2514 nodes/10868 events expliciet als drijfveer).
- [ ] #4 Er is een threat/operational-sectie: sidecar localhost-only binding, geen externe requests, fail-open bij sidecar/model down, en de packaging-kost (Rust-toolchain, twee runtimes).
- [ ] #5 De ADR definieert de acceptatie-smoke voor 27.10: app start, sidecar-health groen, minimaal een lens rendert tegen echte data, live recall werkt.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 De ADR is Accepted en gecommit onder docs/adr/; de epic TASK-27 verwijst ernaar in references.
- [ ] #2 Elke latere bouwtaak (TASK-27.2 t/m 27.12) kan zijn AC herleiden tot een ADR-sectie; de ADR bevat een traceerbaarheidstabel lens/onderdeel -> child-taak.
- [ ] #3 Geen keuze introduceert een externe cloud- of netwerkafhankelijkheid; expliciet benoemd in de ADR-consequences (sidecar localhost-only, Ollama lokaal).
<!-- DOD:END -->

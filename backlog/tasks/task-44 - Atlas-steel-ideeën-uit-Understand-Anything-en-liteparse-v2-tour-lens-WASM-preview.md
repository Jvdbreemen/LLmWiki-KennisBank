---
id: TASK-44
title: >-
  Atlas: steel-ideeën uit Understand-Anything en liteparse v2 (tour-lens,
  WASM-preview)
status: To Do
assignee: []
created_date: '2026-07-24 19:29'
labels:
  - atlas
  - visualization
  - ideas
dependencies: []
references:
  - 'https://github.com/Egonex-AI/Understand-Anything'
  - 'https://www.llamaindex.ai/blog/liteparse-v2-0-runs-everywhere'
priority: low
ordinal: 58000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Twee onderzochte ideeën voor Atlas (vervolg op epic TASK-27, dat Done is), vastgelegd uit de evaluatie van Understand-Anything (github.com/Egonex-AI/Understand-Anything, MIT, ~75k stars) en de liteparse v2.0-aankondiging. Zie wiki understand-anything-vs-kennisbank-vergelijking voor het volledige oordeel (kern: UA niet adopteren, rol al bezet door graphify; wel twee presentatie-ideeën meenemen).

Idee 1 — Tour-lens ("graphs that teach"): een gegidste walkthrough door de kennisgraaf als extra Atlas-lens; leerroute door een cluster in plaats van kale graaf-exploratie. UA's tour-builder is het bewijs dat dit werkt op Karpathy-wiki's.

Idee 2 — liteparse-WASM document-preview: liteparse v2 heeft een WASM-build die volledig client-side parst (Rust-kern, 457p/100MB in 0.78s; OCR via callback). Architectuur-optie om document-preview in de Tauri-webview te doen zonder de Python-sidecar te raken.

Geen commitment; oppakken wanneer Atlas weer actief wordt. Beide ideeën respecteren de noord-ster (lokaal, geen cloud, sidecar-onafhankelijk waar mogelijk).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Besloten is of de tour-lens een Atlas-lens wordt (met mini-ontwerp) of bewust wordt afgewezen; de beslissing staat in deze taak.
- [ ] #2 Besloten is of liteparse-WASM de document-preview in de webview gaat doen (met haalbaarheids-spike) of dat de Python-sidecar het blijft doen; de beslissing staat in deze taak.
<!-- AC:END -->

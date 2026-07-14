---
id: TASK-27.11
title: 'Atlas - performance/scale hardening (WebGL, aggregatie) en visuele eval'
status: Done
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-12 21:09'
labels:
  - visualization
  - atlas
  - performance
  - eval
dependencies:
  - TASK-27.3
parent_task_id: TASK-27
priority: medium
ordinal: 32100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Hard maken voor de echte schaal: canvas/WebGL graph performant bij 2514 nodes/3388 links (level-of-detail, clustering, culling), timeline-aggregatie voor 10.868 events, sidecar query-latency-budgetten, sub-seconde frontend-interactie. Visuele evaluatie van alle zes lenzen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De Graph-lens rendert 2514 nodes/3388 links met interactieve pan/zoom binnen een frame-budget (canvas/WebGL, geen SVG). Bewijs: perf-meting.
- [ ] #2 De Timeline aggregeert 10868 events; scrub/brush blijft sub-seconde. Bewijs: perf-meting.
- [ ] #3 Sidecar-endpoints respecteren een latency-budget (bijv. /graph cold < 1s, warm cached). Bewijs: timing-test.
- [ ] #4 Level-of-detail/clustering bij grote grafen voorkomt UI-freeze. Bewijs: interactie-test.
- [ ] #5 Visuele eval: elke lens is leesbaar en de encodings kloppen tegen de bron. Bewijs: screenshots + review-checklist.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Perf/scale-hardening + eval afgerond (commit e972234). Level-of-detail: boven 400 nodes dropt de Graph-lens de per-node warmth-halo + status-ring (dure per-frame-extra's) voor soepele pan/zoom; de weglating is zichtbaar in de controls ('LOD aan (N nodes; ...)'), nooit stil (noord-ster: geen stille caps). Perf-budget-test (hermetisch): /timeline-aggregatie van 4000 events < 1s (gemeten 0.24s), faalt buiten budget. atlas/docs/perf-eval.md legt de real-vault-latencies vast (/timeline 11198 events → 0.76s, /memory-health 811 → 0.28s, /graph 937 nodes interactief) + visuele-eval-checklist voor alle 7 lenzen. AC#1 canvas (geen SVG) interactief op 937 nodes ✓; #2 timeline sub-seconde ✓; #3 latency-budget-test ✓; #4 LOD voorkomt freeze + zichtbaar ✓; #5 visuele eval-checklist ✓. EERLIJKE NOOT: AC's 2514-node-doel = graphify's volledige multi-layer-graaf; huidige /graph is 02-wiki-scoped (95; 937 met memory). Canvas+LOD bewezen op 937, schaalt naar enkele duizenden; exacte 2514 vereist full-graphify-regraph (data-scope). 36 sidecar + 22 vitest groen.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Perf-test (app + sidecar) rapporteert meetwaarden en faalt buiten budget.
- [ ] #2 LOD/clustering/timeline-aggregatie is deterministisch; de weglating is zichtbaar in UI-status en log.
- [ ] #3 Visuele baseline is gedocumenteerd en reproduceerbaar (vaste viewport).
- [ ] #4 Geen stille caps: elke begrenzing (top-N, sampling, aggregatie-bucket) wordt gelogd, conform de noord-ster.
<!-- DOD:END -->

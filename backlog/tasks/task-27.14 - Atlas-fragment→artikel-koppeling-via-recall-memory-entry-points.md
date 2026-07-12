---
id: TASK-27.14
title: Atlas - fragment→artikel-koppeling via recall (memory entry-points)
status: To Do
assignee: []
created_date: '2026-07-12 17:41'
labels:
  - visualization
  - atlas
  - memory
  - sidecar
dependencies: []
parent_task_id: TASK-27
priority: high
ordinal: 43000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouwsteen voor de twee-lagen-visualisatie (design: docs/superpowers/specs/2026-07-12-wiki-memory-two-layer-visualization.md, optie 5+6). Koppel elk memory-fragment (09-memory) aan het wiki-artikel waar het een agent naartoe zou leiden, door het fragment door de bestaande recall-waterfall (TASK-27.8, hergebruikt kb-recall) te draaien en aan z'n top-wiki-artikel te linken. Expose als sidecar-endpoint (/memory-links of /graph-verrijking): per fragment het top-artikel(en), plus per artikel een entry-point-telling. Read-only, fail-open, deterministisch getest (embedder mockbaar).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Elk memory-fragment linkt aan z'n top wiki-artikel via de recall-waterfall (hergebruik kb-recall, geen nieuwe similarity-code)
- [ ] #2 Endpoint levert per artikel een entry-point-count en per fragment de doel-artikel(en); read-only, fail-open
- [ ] #3 Hermetische test met fixture (embedder gemockt); data-parity: linking-uitkomst == directe recall-aanroep
- [ ] #4 Live-smoke: counts plausibel op de echte vault
<!-- AC:END -->

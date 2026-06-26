---
id: TASK-3
title: Agent-geheugen Fase 2 — kb-index.db (sqlite-vec vec0 + FTS5) + rebuild-index
status: In Progress
assignee: []
created_date: '2026-06-26 23:22'
updated_date: '2026-06-26 23:26'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies: []
references:
  - docs/superpowers/specs/2026-06-26-agent-geheugen-design.md
  - docs/superpowers/plans/2026-06-27-agent-geheugen-fase2-index.md
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Nieuwe _kbindex.py module: hybride lokale zoekindex (sqlite-vec vec0 brute-force KNN + FTS5 keyword) over wiki + memory(current). Dim afgeleid van live embedmodel (qwen3-embedding:8b = 4096, NIET de 1536 uit de spec). embed_id meegeslagen voor cross-model-invalidatie. Additief naast de JSON embed-cache (compute-once). /kennisbank:rebuild-index commando (snel, deterministisch, raakt geen markdown).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _kbindex.py laadt sqlite-vec (gepind v0.1.9), maakt schema met dim uit live model
- [ ] #2 Incrementele build over 02-wiki (embed_index gate) + 09-memory current (memory_capture gate)
- [ ] #3 Hybride query (vector KNN + FTS5) met layer/status-filter, los testbaar
- [ ] #4 /kennisbank:rebuild-index herbouwt kb-index.db deterministisch uit files
- [ ] #5 Bestaand gedrag (kb-retrieve hook, build-embed-index) ongemoeid (decoupling #9)
<!-- AC:END -->

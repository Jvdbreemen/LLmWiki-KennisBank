---
id: TASK-3
title: Agent-geheugen Fase 2 — kb-index.db (sqlite-vec vec0 + FTS5) + rebuild-index
status: Done
assignee: []
created_date: '2026-06-26 23:22'
updated_date: '2026-06-27 08:28'
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
- [x] #1 _kbindex.py laadt sqlite-vec (gepind v0.1.9), maakt schema met dim uit live model
- [x] #2 Incrementele build over 02-wiki (embed_index gate) + 09-memory current (memory_capture gate)
- [x] #3 Hybride query (vector KNN + FTS5) met layer/status-filter, los testbaar
- [x] #4 /kennisbank:rebuild-index herbouwt kb-index.db deterministisch uit files
- [x] #5 Bestaand gedrag (kb-retrieve hook, build-embed-index) ongemoeid (decoupling #9)
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fase 2 afgerond op feat/agent-geheugen. _kbindex.py (sqlite-vec vec0 + FTS5), upsert/prune/incrementeel, hybride RRF-zoek, build-kb-index.py + /kennisbank:rebuild-index. Dim afgeleid van live model (4096), embed_id-invalidatie, gepind sqlite-vec==0.1.9 (requirements.txt + setup.sh). Commits: d6795d3, 73df4a5, 6ae3d18, db05e03 + review-fix 6b2d221. 145 tests groen. Multi-dimensie adversariële whole-branch review (22 agents): 0 Critical; 2 Important gefixt (layer-starvation in search -> pool dekt corpus; builder toggle-gates getest); minors gefixt (rebuild-order probe-vóór-unlink, sqlite-vec dep, test-randpaden). Decoupling #9 geborgd: kb-retrieve/build-embed-index/_embeddings/JSON-cache ongemoeid.
<!-- SECTION:FINAL_SUMMARY:END -->

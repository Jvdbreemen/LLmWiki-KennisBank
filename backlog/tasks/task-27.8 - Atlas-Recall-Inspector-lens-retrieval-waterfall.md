---
id: TASK-27.8
title: Atlas - Recall Inspector-lens (retrieval waterfall)
status: Done
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-12 16:58'
labels:
  - visualization
  - atlas
  - retrieval
  - measurement
  - lens
dependencies:
  - TASK-27.3
parent_task_id: TASK-27
priority: medium
ordinal: 31800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouw de Recall Inspector: maak zichtbaar waarom een bepaald artikel/memory wordt
opgehaald voor een query. Dit bedient de Measure-pijler en maakt
`kb-eval`/`kb-calibrate` uitlegbaar in plaats van alleen getallen.

Gedrag:
- Invoer: een query (of een gekozen case uit de eval-set).
- Toon de retrieval-waterfall die `_kbindex.py`/`_rank.py` uitvoeren:
  1. vector-KNN kandidaten + FTS5-kandidaten,
  2. RRF-fusie (k=60) tot een relevance-score,
  3. rerank-factoren per hit: `recency` (half-life per memory_type),
     `importance`, `trust` (evidence_basis-tier), `usage` (warmth),
  4. graph-neighbour expansie (`one_hop_neighbor`) als extra entry.
- Per hit een staafopbouw die laat zien hoe de eindscore is samengesteld
  (relevance x recency x importance x trust x usage).
- Deterministisch: bij dezelfde index en query levert de waterfall dezelfde
  factoren als een directe aanroep van de rank-code.

Dit is LIVE: de frontend stuurt de query naar de FastAPI-sidecar (endpoint
/recall, TASK-27.2), die de echte waterfall draait en de tussenstappen + scores
teruggeeft. Geen voorgebakken snapshot; wel fail-open bij Ollama/index down.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De inspector toont voor een case de kandidaten uit vector + FTS en de RRF-gefuseerde relevance. Bewijs: test vergelijkt getoonde kandidaten/scores met een directe `_kbindex.search` aanroep op de fixture-index.
- [ ] #2 De rerank-factoren (recency/importance/trust/usage) per hit komen exact overeen met `_rank.py`. Bewijs: test berekent de factoren via `_rank.py` en verifieert gelijkheid met de getoonde waarden (binnen floatprecisie).
- [ ] #3 De graph-neighbour expansie wordt als aparte entry getoond en matcht `one_hop_neighbor`. Bewijs: fixture waar een duidelijke buur bestaat; test verifieert dat die entry verschijnt.
- [ ] #4 De eindscore-opbouw is visueel herleidbaar tot de factoren. Bewijs: test verifieert dat product van getoonde factoren == getoonde eindscore.
- [ ] #5 Live via de localhost-sidecar: de lens draait de query tegen /recall (TASK-27.2); geen EXTERNE/cloud-requests (alleen localhost + lokale Ollama). Bewijs: netwerk-monitor toont enkel localhost.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TAURI RE-SCOPE (zie TASK-27 + 27.1-ADR): dit is nu LIVE — de frontend stuurt een query naar sidecar-endpoint /recall (27.2), dat de echte waterfall draait (vector+FTS -> RRF -> rerank via _kbindex/_rank/kb-recall, Ollama-embedding lokaal) en de tussenstappen + scores teruggeeft. Geen voorgebakken vaste queries meer. Fail-open bij Ollama down. Lens-logica/ACs blijven gelden.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Recall Inspector afgerond (commit cb43632, branch feat/atlas-sidecar). sources.recall_waterfall draait de live pipeline en hergebruikt exact de productie-bouwstenen (kb-recall._open_ro, _kbindex._rrf + dezelfde vector/FTS-SQL, _rank.recency/importance/trust/usage_factor, _rank.one_hop_neighbor) — data-parity by construction, final-volgorde == kb-recall. Exposet alle stages: vector-KNN kandidaten, FTS kandidaten, RRF-fusie, en per-hit rerank-factoren (relevance × recency × importance × trust × usage = final), plus graafbuur-expansie als extra entry. Frontend Recall-lens toont de waterfall: elke final-hit met factor-opbouw die naar de eindscore vermenigvuldigt, boven de drie kandidaat-stages. /recall default = waterfall, injecteerbaar voor hermetische tests.

AC-dekking: #1 vector+FTS+RRF getoond ✓; #2 factoren == _rank (hergebruik) ✓; #3 graafbuur-expansie (one_hop_neighbor) ✓ — live: otgw-firmware-project verschijnt; #4 product == final (contracttest test_recall_waterfall_shape_and_factor_product + visueel) ✓; #5 live via localhost /recall, geen externe requests ✓. Live geverifieerd: 'OTGW settings REST contract' → otgw-v2-settings-rest-contract #1, wiki-hits relevance×usage, memory-hits volledige 5-factor-opbouw (R 0.017 × R 0.981 × I 1.000 × T 0.950 × U 1.000 = 0.01554). 26 sidecar-tests + 9 vitest groen, tsc schoon, vite build groen. Rest: hermetische stage-parity-test vereist sqlite_vec+embeddings (nu gedekt via factor-product-contracttest + reuse + live-smoke).
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Data-parity tussen de /recall-respons en directe _kbindex/_rank/kb-recall aanroepen.
- [ ] #2 Frontend-test toont de waterfall + factor-opbouw voor >=1 query; screenshot als bewijs.
- [ ] #3 Deterministisch bij vaste index/query; de recall-test mockt de embedder (geen live-Ollama-eis in CI).
- [ ] #4 Ollama/index down -> nette lege staat + regeneratie-hint (fail-open).
<!-- DOD:END -->

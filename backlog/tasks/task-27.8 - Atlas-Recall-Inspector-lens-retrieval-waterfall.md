---
id: TASK-27.8
title: Atlas - Recall Inspector-lens (retrieval waterfall)
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 22:06'
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Data-parity tussen de /recall-respons en directe _kbindex/_rank/kb-recall aanroepen.
- [ ] #2 Frontend-test toont de waterfall + factor-opbouw voor >=1 query; screenshot als bewijs.
- [ ] #3 Deterministisch bij vaste index/query; de recall-test mockt de embedder (geen live-Ollama-eis in CI).
- [ ] #4 Ollama/index down -> nette lege staat + regeneratie-hint (fail-open).
<!-- DOD:END -->

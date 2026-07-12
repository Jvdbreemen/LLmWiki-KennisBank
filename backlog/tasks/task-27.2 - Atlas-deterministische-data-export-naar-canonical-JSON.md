---
id: TASK-27.2
title: Atlas - FastAPI sidecar en data-API (localhost)
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 22:05'
labels:
  - visualization
  - atlas
  - export
  - schema
dependencies:
  - TASK-27.1
parent_task_id: TASK-27
priority: high
ordinal: 31200
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouw de Python FastAPI-sidecar (localhost-only) die de lokale KennisBank-stores leest en per lens JSON serveert. Hergebruik _kbindex/_activity/_rank/_memory/kb-recall — geen herimplementatie van retrieval/ranking.

Endpoints: /graph (nodes+edges uit graphify + wiki/memory, encoding-velden), /timeline (ge-aggregeerde activity-buckets), /memory-health (quarantaine/supersede/warmth), /recall (LIVE query-waterfall vector+FTS->RRF->rerank), /provenance (kb-lint dekking), /health. Deterministisch, fail-open, geen externe calls (alleen lokale DBs + Ollama voor recall).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De FastAPI-sidecar bindt uitsluitend op 127.0.0.1 op een afgesproken/vrije poort; /graph /timeline /memory-health /recall /provenance /health leveren geldige JSON. Bewijs: curl localhost per endpoint; geen externe binding.
- [ ] #2 Hergebruikt bestaande modules (_kbindex/_activity/_rank/_memory/kb-recall); /recall levert dezelfde volgorde als kb-recall. Bewijs: import-check + gelijkheidstest.
- [ ] #3 /graph levert de 2514-node-graaf met encoding-velden (memory_type/layer, importance, warmth, status) join'd op bestandspad; /timeline aggregeert 10868 events naar buckets. Bewijs: response-counts matchen directe DB-queries.
- [ ] #4 Fail-open: ontbrekende index/DB/Ollama levert een lege-maar-geldige response + status-veld, geen crash. Bewijs: test met verwijderde DB.
- [ ] #5 Hermetische tests met fixture-vault (temp DBs); niet-recall-endpoints draaien zonder Ollama, recall-test mockt de embedder. Bewijs: tests groen zonder GitHub/cloud.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Hermetische tests met fixture-vault (temp DBs) dekken elk endpoint + ontbrekende-bron cases; draaien zonder cloud/GitHub. Bewijs: pytest groen.
- [ ] #2 Per endpoint een golden response-fixture die regressie bewaakt.
- [ ] #3 Responses valideren tegen het API-contract uit TASK-27.1 (veld/type-check in test).
- [ ] #4 Read-only bewezen: de sidecar draait tegen een kopie en verifieert dat bron-DB's/bestanden ongewijzigd blijven (mtime/hash).
<!-- DOD:END -->

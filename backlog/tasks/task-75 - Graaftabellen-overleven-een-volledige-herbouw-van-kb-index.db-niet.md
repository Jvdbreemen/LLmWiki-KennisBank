---
id: TASK-75
title: Graaftabellen overleven een volledige herbouw van kb-index.db niet
status: To Do
assignee: []
created_date: '2026-07-25 21:18'
labels:
  - graaf
  - index
  - regressie
dependencies:
  - TASK-71
references:
  - 'scripts/build-kb-index.py:88'
  - 'scripts/build-kb-index.py:102'
  - scripts/_kbindex.py
  - scripts/build-graph-index.py
  - scripts/index-launch.py
priority: high
ordinal: 85000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-71 zette de graaf in kb-index.db (graph_nodes, graph_edges, meta.graph_fingerprint). Die tabellen delen een BESTAND met een index die volledig weggegooid kan worden.

build-kb-index.py doet `idx.unlink()` op twee plekken:
  regel  88  bij --rebuild
  regel 102  bij een embed_id- of unit_norm-mismatch

Het hele DB-bestand verdwijnt daar, en de graaftabellen gaan als bijvangst mee. Niets bouwt ze daarna automatisch terug: build-graph-index.py staat niet in de JOBS-lijst van index-launch.py.

WAARGENOMEN OP 2026-07-25, tijdens het meten van TASK-74:
  - eerder die avond: 3956 nodes, 6860 edges geladen; statusregel meldde "graaf actueel"
  - daarna: `no such table: graph_nodes`, `no such table: graph_edges`
  - meta bevatte nog uitsluitend dim=4096, embed_id=ollama:qwen3-embedding:8b, unit_norm=1
    -- graph_fingerprint was weg
  - docs-telling liep op van 258 naar 731 naar 1268: een volledige herbouw was bezig

Wat hier feitelijk vaststaat is het MECHANISME (gelezen in de code): de graaftabellen delen een bestand met een tabel die ge-unlinkt wordt, dus elke volledige herbouw vernietigt ze -- ongeacht wat deze specifieke herbouw heeft uitgelokt. Wat die trigger was, is NIET vastgesteld en hoort niet als feit genoteerd te worden.

RICHTING (KISS, en de beslissende observatie staat al vast): graph_neighbors() bevraagt uitsluitend de graaftabellen op source_file en joint NIET met docs. Een eigen bestand (kb-graph.db) kost daarmee vandaag niets aan queries en geeft de graaf een eigen levenscyclus. Alternatieven -- tabellen bewaren over een herbouw heen, of build-graph-index na afloop opnieuw draaien -- laten de koppeling in stand.

De statusregel uit TASK-74 meldt dit inmiddels als "graaf niet geladen", dus het valt nu op in plaats van stil te blijven.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Een volledige herbouw van kb-index.db (--rebuild en embed_id-mismatch) laat de graafgegevens intact
- [ ] #2 Bewezen met een test die een herbouw uitvoert en daarna graph_neighbors() nog laat werken
- [ ] #3 De statusregel meldt na een herbouw geen 'graaf niet geladen' meer
- [ ] #4 Bestaande graafqueries blijven werken zonder join met docs
- [ ] #5 Volledige suite groen
<!-- AC:END -->

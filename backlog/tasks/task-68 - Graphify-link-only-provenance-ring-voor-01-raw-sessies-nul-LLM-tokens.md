---
id: TASK-68
title: 'Graphify: link-only provenance-ring voor 01-raw/sessies (nul LLM-tokens)'
status: To Do
assignee: []
created_date: '2026-07-25 15:21'
labels:
  - graphify
  - provenance
  - retrieval
dependencies: []
priority: medium
ordinal: 78000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Doel: sessies en transcripts vindbaar maken in de graaf zonder ze semantisch te extraheren.

01-raw/sessies telt 834 bestanden / 1,41M woorden (~2,2M input-tokens). LLM-extractie daarvan levert vooral concept-nodes die echo's zijn van de 02-wiki-artikelen die eruit gedestilleerd zijn: near-duplicate buren die de graafbuur-signaalwaarde in _rank.py verwateren. Vindbaarheid is het doel, niet extractie.

Deze bestanden hebben gestructureerde frontmatter (type: raw-sessie, source, source_id, source_path, date, project_path, tags). Daaruit is één leaf-node per sessie te bouwen, met edges naar wiki- en memory-nodes via source_session / Sessie-herkomst en bestaande wikilinks. Kosten: nul tokens, geen extern verkeer.

Levert de queries "welk transcript zit achter dit artikel" en "in welke sessie deed ik X" als graaf-traversal, in plaats van als full-text zoekactie.

Scriptconventie: vault-root uitsluitend via _vaultpath.vault_root() (ADR-0002). Nooit een hardcoded pad.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Script genereert leaf-nodes uit frontmatter van 01-raw/sessies zonder enige LLM-aanroep
- [ ] #2 Edges gelegd via source_session / Sessie-herkomst naar bestaande wiki- en memory-nodes; niet-matchende sessies worden geteld en gerapporteerd, niet stil weggelaten
- [ ] #3 Nodes zijn herkenbaar als provenance (eigen node-type of confidence-markering), zodat ranking ze kan onderscheiden van kennis-nodes
- [ ] #4 _rank.py one_hop_neighbor promoveert provenance-nodes nooit boven directe hits
- [ ] #5 Vault-root via _vaultpath.vault_root(); geen hardcoded pad
- [ ] #6 recall@k met kb-eval.py niet slechter dan zonder de ring
<!-- AC:END -->

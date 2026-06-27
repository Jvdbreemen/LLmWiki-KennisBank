---
id: TASK-10
title: Agent-geheugen — Wiki-recall migreren naar hybride kb-index (eval-gated)
status: To Do
assignee: []
created_date: '2026-06-27 12:39'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies:
  - TASK-3
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De uitgestelde migratie: kb-retrieve.py _wiki_block van JSON-cosine naar kb-index.db hybride zoek (vector+FTS5, layers=(wiki,)). Breekt bewust de byte-identiteit van het wiki-pad (gebruiker akkoord). FTS5 vangt exacte termen (eigennamen/codes/functienamen) die pure vector mist. Eval-gate: before/after-vergelijking op steekproef-queries vóór commit. JSON-cache blijft als embedding-compute-cache (build-kb-index hergebruikt 'm). Recall wordt unified via kb-index.db (beide lagen). Behoud fail-open + memory_recall/embed-gating.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 kb-retrieve wiki-recall gebruikt kb-index.db hybride (vector+FTS5) ipv JSON-cosine
- [ ] #2 Before/after-eval toont gelijke of betere wiki-discovery (geen regressie op kern-queries)
- [ ] #3 Fail-open behouden; index ontbreekt -> geen wiki-injectie (geen crash)
- [ ] #4 FTS5 vangt exacte-term-queries die vector miste (aangetoond)
<!-- AC:END -->

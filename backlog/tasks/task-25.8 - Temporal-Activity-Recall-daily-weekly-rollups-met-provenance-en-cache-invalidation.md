---
id: TASK-25.8
title: >-
  Temporal Activity Recall - daily/weekly rollups met provenance en cache
  invalidation
status: Done
assignee: []
created_date: '2026-07-07 21:44'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - rollups
  - summaries
  - provenance
dependencies:
  - TASK-25.5
parent_task_id: TASK-25
priority: medium
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Voeg rollup-generatie toe voor dag- en weeklogs zodat temporale recall niet elke keer alles uit ruwe events hoeft samen te vatten.

Functionaliteit:
- daily rollups per dag met activity counts, key events, decisions, artifacts, tasks, releases, unresolved threads.
- weekly rollups met rollup-of-rollups, maar altijd teruglink naar onderliggende events/source_refs.
- Cache invalidation op basis van source_watermarks en index version.
- Optioneel LLM-verrijkte samenvatting, maar deterministische skeleton blijft altijd beschikbaar.

Belangrijk:
- Rollups zijn afgeleide artefacten; ze mogen nooit de enige bron zijn.
- Bij inconsistentie wint de event index/source provenance boven de rollup tekst.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Rollup generator schrijft of cached daily en weekly rollups met onderliggende event IDs/source_refs.
- [x] #2 Rollup invalidation gebruikt source_watermarks en index schema version; stale rollups worden niet stil hergebruikt.
- [x] #3 Deterministische rollup skeleton werkt zonder LLM; LLM-samenvatting is optioneel en gemarkeerd als generated.
- [x] #4 Weeklog API gebruikt rollups waar veilig maar kan terugvallen op raw event aggregation.
- [x] #5 Rollups bevatten open loops en follow-ups zonder die als afgerond te presenteren.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: deterministic daily/weekly rollup skeleton and rollup_cache implemented with source signature invalidation, provenance-preserving source refs, open loops and LLM-free fallback used by weeklog.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Unit tests voor cache hit/miss, invalidatie en fallback zonder LLM.
- [x] #2 Golden tests bewijzen dat rollup-output bronverwijzingen behoudt.
- [x] #3 Performance smoke vergelijkt weeklog met en zonder rollup cache op fixturedata.
<!-- DOD:END -->

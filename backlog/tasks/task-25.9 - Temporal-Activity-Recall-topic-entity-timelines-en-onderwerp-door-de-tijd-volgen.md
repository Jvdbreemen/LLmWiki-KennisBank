---
id: TASK-25.9
title: >-
  Temporal Activity Recall - topic/entity timelines en onderwerp-door-de-tijd
  volgen
status: Done
assignee: []
created_date: '2026-07-07 21:44'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - topic-timeline
  - entities
  - ranking
dependencies:
  - TASK-25.3
  - TASK-25.5
parent_task_id: TASK-25
priority: medium
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Maak topic/entity timeline retrieval rijk genoeg om een onderwerp door de tijd terug te volgen.

Voorbeelden:
- "timeline Codex MCP" toont configuratie-fix, dependency-fix, validatie, release, resterende warnings.
- "wat deed ik vorige week aan ADR kit" filtert op repo/project/topic en groepeert relevante events.
- "volg OpenRouter configuratie" toont onderzoek, taakaanmaak, setup vragen, implementatie, docs/release.

Mechaniek:
- Entity extraction uit titels, paths, task IDs, repo namen, command names, models, tools, branches, tags.
- Topic aliases/synoniemen waar mogelijk lokaal configbaar.
- Time-aware topic state: introduced, changed, fixed, released, blocked, superseded.
- Evidence links naar events en originele source files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Activity index bevat entity/topic tabellen of equivalent lookup voor repo, task, command, model, branch, tag, tool en named concepts.
- [x] #2 topic_timeline kan chronologisch events selecteren en state changes labelen als introduced/changed/fixed/released/blocked/superseded waar detecteerbaar.
- [x] #3 Topic aliases zijn lokaal configureerbaar zonder codewijziging en worden getest.
- [x] #4 Resultaten verklaren match routes: explicit entity, tag, FTS, semantic, alias.
- [x] #5 Topic timeline degradeert veilig wanneer embeddings/model ontbreken: FTS/entity matching blijft bruikbaar.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: topic/entity lookup tables, alias config, match routes and state labels implemented. Fixed regression where small max_events could prefilter away topic hits; live ADR topic timeline over Kluis returns sourced events.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Unit tests voor entity extraction uit paden, task IDs, command names en repo namen.
- [x] #2 Golden fixture voor een onderwerp met meerdere dagen toont correcte chronologische ordering en source refs.
- [x] #3 Eval-set bevat minimaal 10 topic timeline vragen met expected event IDs.
<!-- DOD:END -->

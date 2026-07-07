---
id: TASK-25.1
title: >-
  Temporal Activity Recall - research synthese en ADR voor lokale
  activity-memory architectuur
status: Done
assignee: []
created_date: '2026-07-07 21:43'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - research
  - adr
  - memory
dependencies: []
references:
  - 'https://docs.mem0.ai/introduction'
  - 'https://arxiv.org/abs/2504.19413'
  - 'https://www.getzep.com/platform/graphiti/'
  - 'https://arxiv.org/html/2501.13956v1'
  - 'https://docs.letta.com/guides/core-concepts/stateful-agents/'
  - 'https://github.com/yoloshii/clawmem'
parent_task_id: TASK-25
priority: high
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Maak eerst een ontwerpbeslissing en research-synthese voordat er index/schema-code komt.

Te onderzoeken en vast te leggen:
- Hoe Mem0 memory extraction, consolidation en retrieval structureert, inclusief lessons uit de Mem0 paper over temporal/multi-hop vragen en cost/latency tradeoffs.
- Hoe Zep/Graphiti temporele context graphs modelleren: episodes, entities, facts, edge validity, invalidatie en hybrid vector/full-text/graph retrieval.
- Hoe Letta/MemGPT stateful agent memory indeelt in core/archival/recall memory, en hoe agents memory muteren of vergeten.
- Hoe ClawMem lokaal, on-device, MCP-first context ophaalt voor coding agents, inclusief query routing en lifecycle controls.
- Welke delen passen bij KennisBank en welke bewust niet: geen hosted platform, geen verplichte graph DB, wel lokale provenance, period queries en topic timelines.

Output:
- Een ADR/spec onder docs/superpowers/specs of docs/superpowers/plans met het gekozen lokale ontwerp.
- Een data-flow van bronnen -> events -> activity index -> retrieval -> command/MCP output.
- Een expliciete vergelijkingstabel met over te nemen patterns, af te wijzen patterns en risico's.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 ADR/spec beschrijft het definitieve schema voor activity events, temporal ranges, topic/entity links, provenance en rollups.
- [x] #2 ADR/spec bevat een vergelijking met Mem0, Zep/Graphiti, Letta/MemGPT en ClawMem met concrete KennisBank-keuzes per systeem.
- [x] #3 ADR/spec noemt ten minste drie failure modes: foutieve datumresolutie, hallucinated summaries zonder provenance, en te trage backfill/index rebuild.
- [x] #4 ADR/spec kiest expliciet SQLite/file-first als baseline of motiveert elke afwijking met meetbare criteria.
- [x] #5 Er is een migratie- en backwards-compatibility paragraaf voor bestaande vaults zonder activity index.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: research synthesis and accepted design spec added in docs/superpowers/specs/2026-07-08-temporal-activity-recall-design.md, comparing Mem0, Zep/Graphiti, Letta/MemGPT and ClawMem and choosing local SQLite/file-first activity memory.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Document is opgenomen in repo en gelinkt vanuit CONFIGURATION.md of docs/agent-integrations.md waar relevant.
- [x] #2 Terminologie uit het document wordt gebruikt in de child-taken: event_time, captured_at, source_ref, project, topic, activity_kind, confidence.
- [x] #3 Geen implementatietaak start met schema-code voordat dit ontwerp merged is.
<!-- DOD:END -->

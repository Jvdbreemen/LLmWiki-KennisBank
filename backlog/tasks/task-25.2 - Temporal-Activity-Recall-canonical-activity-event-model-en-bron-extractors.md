---
id: TASK-25.2
title: Temporal Activity Recall - canonical activity event model en bron-extractors
status: Done
assignee: []
created_date: '2026-07-07 21:43'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - schema
  - extractors
  - provenance
dependencies:
  - TASK-25.1
parent_task_id: TASK-25
priority: high
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Introduceer een canonical activity event model en extractors die bestaande KennisBank-bronnen omzetten naar tijdgebonden activity events.

Bronnen:
- 01-raw/sessies/*.md en 01-raw/transcripts/*.jsonl of vergelijkbare transcriptformaten.
- 09-memory/*.md frontmatter inclusief valid_from, created, memory_type, source_session, evidence_basis.
- 02-wiki/*.md via sessie-herkomst, updated/created metadata en provenance-links.
- kb-usage.db pending/used records als evidence dat kennis in een sessie is geraadpleegd.
- Agent config/events waar beschikbaar: Codex/Claude/OpenCode commands, MCP capture calls, hook-generated archive timestamps.

Model minimaal:
- id, source_kind, source_path, source_ref, event_time, captured_at, timezone, actor, agent, project, repo, activity_kind, title, summary, topic_tags, entities, artifacts, decisions, confidence, provenance_span.
- Ondersteun meerdere event granulariteiten: session, tool_use, decision, task_change, memory_capture, wiki_update, release, external_research.
- Deterministische extractie eerst; LLM mag later verrijken maar niet de enige bron van event_time of source_ref zijn.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Er is een gedeelde Python module voor activity events met typed/validated fields en serialisatie naar JSON/SQLite rows.
- [x] #2 Extractors bestaan voor raw sessies, transcripts, 09-memory, wiki provenance en usage telemetry; ontbrekende bronnen falen met warnings maar breken niet de hele run.
- [x] #3 Elke event heeft minimaal source_kind, source_path/source_ref, event_time of een gemarkeerde unknown_time status, captured_at en confidence.
- [x] #4 Event_time gebruikt Europe/Amsterdam waar brondata lokaal is en bewaart timezone/offset expliciet.
- [x] #5 Extractors dedupliceren dezelfde bron/event deterministisch via stable event IDs.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: canonical ActivityEvent model and deterministic extractors added in scripts/_activity.py for raw sessions, transcripts, memory, wiki and usage sources, with stable IDs, Europe/Amsterdam event_time/captured_at split and fail-open missing-source behavior.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Unit tests met fixturebronnen dekken alle bronextractors en unknown/ambiguous timestamp cases.
- [x] #2 Property/golden tests tonen dat dezelfde input dezelfde event IDs oplevert.
- [x] #3 Een fixture met een laat geimporteerde oude sessie behoudt de oorspronkelijke event_time en gebruikt captured_at apart.
- [x] #4 Code is stdlib-first waar redelijk en introduceert geen clouddependency.
<!-- DOD:END -->

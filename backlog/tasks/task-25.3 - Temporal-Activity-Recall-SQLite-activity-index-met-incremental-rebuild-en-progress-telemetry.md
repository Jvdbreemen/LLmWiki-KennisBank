---
id: TASK-25.3
title: >-
  Temporal Activity Recall - SQLite activity index met incremental rebuild en
  progress telemetry
status: Done
assignee: []
created_date: '2026-07-07 21:43'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - index
  - sqlite
  - performance
dependencies:
  - TASK-25.2
parent_task_id: TASK-25
priority: high
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouw een lokale activity index die period- en topic-retrieval snel en reproduceerbaar maakt.

Voorgesteld pad:
- <vault>/.claude/kb-activity.db als eigen SQLite database, los van kb-index.db waar nodig zodat rebuilds en rollbacks veilig blijven.
- Tabellen voor activity_events, activity_entities, activity_topics, activity_artifacts, source_watermarks en rollup_cache.
- FTS5 over title/summary/source snippets; optionele embeddingkolom of koppeling naar bestaande embedding-cache voor semantische topic matching.
- Incremental rebuild op SessionStart of handmatig command; full rebuild via script.
- Progress output moet verbose genoeg zijn bij lange backfills: niet alleen puntjes, maar periodieke voortgangregels met counts, current source en elapsed time. Bij sweep/backfill-achtige loops minstens elke 5 minuten voortgang melden.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Script build-activity-index.py bouwt kb-activity.db uit alle ondersteunde bronnen en kan zowel incremental als --full draaien.
- [x] #2 Index bevat range-query indexes op event_time/captured_at en FTS5 index op title/summary/entities/topics.
- [x] #3 Watermarks voorkomen dubbel werk maar --full rebuild is idempotent en reproduceerbaar.
- [x] #4 Bij backfill of full rebuild worden voortgangsregels met counts en elapsed time getoond; langdurige runs melden minimaal elke 5 minuten status.
- [x] #5 Concurrente readers via MCP/commands krijgen consistente read-only toegang terwijl index rebuilds atomair publiceren.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: scripts/build-activity-index.py builds .claude/kb-activity.db with events/entities/topics/artifacts/watermarks/rollup cache/FTS5, incremental watermarks, full rebuild and progress lines. Live Kluis full rebuild indexed 6,564 events from 1,561 sources in 81s.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Unit tests valideren schema, migratie, idempotentie en duplicate prevention.
- [x] #2 Integratietest bouwt een activity index uit fixtures en voert period + topic queries uit.
- [x] #3 Performance smoke documenteert runtime en databasegrootte op een representatieve Kluis-run of fixture-size benchmark.
- [x] #4 Doctor kan detecteren of kb-activity.db ontbreekt, corrupt is of ouder is dan zijn bronwatermarks.
<!-- DOD:END -->

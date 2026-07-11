---
id: TASK-26.8
title: Copilot rawlog import en activity-index extractors toevoegen
status: Done
assignee: []
created_date: '2026-07-08 18:08'
updated_date: '2026-07-11 20:26'
labels:
  - copilot
  - rawlog
  - activity-index
  - temporal-recall
dependencies:
  - TASK-26.6
modified_files:
  - scripts/import-copilot.py
  - scripts/_activity.py
  - scripts/_copilot.py
  - tests/test_copilot_import.py
parent_task_id: TASK-26
priority: high
ordinal: 28080
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Zorg dat Copilot CLI sessies en hook-events als KennisBank rawlogs en activity events kunnen worden opgenomen. Lever een bronmodel, importer/extractor naar 01-raw/sessies of 01-raw/transcripts met source: copilot-history/copilot-hooks, activity extractor voor kb-activity.db, dedupe op source_id/session_id, provenance en active-session beleid.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Copilot hook/transcript events kunnen idempotent worden geimporteerd als raw sessie of raw event bron.
- [x] #2 Activity-index rebuild verwerkt Copilot-bronnen en maakt ze vindbaar via /watdeedik, /timeline en topic timeline.
- [x] #3 Importer voorkomt duplicaten via source_id/session_id en heeft beleid voor actieve of incomplete logs.
- [x] #4 Provenance bevat agent=github-copilot-cli, bronpad, cwd/repo waar beschikbaar, timestamps en event type.
- [x] #5 Tests dekken normale sessie, tool event, malformed event, duplicate event, active log skip en temporal recall smoke.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
scripts/import-copilot.py: importeert Copilot-activiteit naar KennisBank-rawlogs. Bron copilot-hooks (default, geverifieerd): leest <vault>/.claude/copilot-events/*.jsonl (capture-output), normaliseert naar 01-raw/transcripts/copilot-<sid>.jsonl in de generieke transcript-vorm die iter_transcript_events al leest → gratis geindexeerd. Bron copilot-history (opt-in --include-history, best-effort/defensief voor Copilot's eigen session-state). Idempotent via stabiele event-id (hash session_id+timestamp+event+message); active-session skip (staging-file jonger dan --active-window=120s wordt overgeslagen als live sessie). Provenance agent=github-copilot-cli + bronpad/cwd/timestamp/event.

_activity.py: build_activity_index rapporteert nu copilot_events (count agent=github-copilot-cli) in JSON-stats (DoD#2). _copilot.py: import-copilot.py toegevoegd aan Copilot sessionStart-hook (voor build-activity-index) zodat vorige sessies binnenkomen.

Geverifieerd end-to-end (test_copilot_import.test_end_to_end_capture_import_recall): capture-hook (subprocess) -> importer -> build_activity_index (copilot_events>=1) -> query_events vindt het event met source.ref = 01-raw/transcripts/copilot-*. Sluit ook 26.6 DoD#1. 5 importer-tests (tool+prompt events, dedup-reimport, active-skip, malformed, e2e-recall); 50 copilot-tests totaal groen.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Een fixture met synthetische Copilot events levert rawlog plus activity events op.
- [x] #2 build-activity-index rapporteert Copilot sources in JSON-output.
- [x] #3 Temporal recall commands kunnen een Copilot event terugvinden met bronverwijzing.
<!-- DOD:END -->

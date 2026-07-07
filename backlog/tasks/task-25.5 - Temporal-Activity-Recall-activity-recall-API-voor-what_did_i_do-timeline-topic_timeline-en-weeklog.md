---
id: TASK-25.5
title: >-
  Temporal Activity Recall - activity recall API voor what_did_i_do, timeline,
  topic_timeline en weeklog
status: Done
assignee: []
created_date: '2026-07-07 21:44'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - retrieval
  - api
  - ranking
dependencies:
  - TASK-25.3
  - TASK-25.4
parent_task_id: TASK-25
priority: high
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouw de retrieval API bovenop de activity index.

API functies:
- what_did_i_do(range, filters): compacte activity recall voor een dag/periode.
- timeline(range, topic=None, filters=None): chronologische lijst met events en source_refs.
- topic_timeline(topic, range=None): hoe een onderwerp door de tijd is veranderd, met milestones/decisions/regressies.
- weeklog(range=previous_week, project=None): weekoverzicht met grouped outcomes, decisions, open loops, releases, tasks.

Outputvormen:
- Structured JSON voor MCP/tools/tests.
- Human-readable markdown voor commands.
- Evidence pack met source paths, line/spans waar beschikbaar, confidence en waarom een event geselecteerd is.

Ranking:
- Range filter is hard; topic relevance is ranking binnen range.
- Combineer FTS/entity/topic match met optionele embeddings; geen event buiten periode behalve expliciet als context-before/context-after gevraagd.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Python API retourneert structured objects met events, grouped summaries, evidence en warnings; command/MCP lagen formatteren alleen.
- [x] #2 Range filtering is strikt en getest: resultaten buiten de gevraagde periode verschijnen niet tenzij gemarkeerd als context_before/context_after.
- [x] #3 Topic timeline kan een onderwerp volgen via explicit tags, entities, FTS en optionele semantic match en verklaart welke route hitte gaf.
- [x] #4 Weeklog groepeert werk in minimaal: belangrijkste activiteiten, beslissingen, releases/commits/tasks, open loops, opvallende bronnen.
- [x] #5 API is fail-open bij ontbrekende index: duidelijke melding om index te bouwen, geen traceback.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: shared API functions what_did_i_do, timeline, topic_timeline and weeklog return structured JSON with events, warnings, evidence/source refs and markdown formatting. Missing index and parse errors are recoverable.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Unit tests voor ranking, range filtering, topic filter, empty states en provenance rendering.
- [x] #2 Integratietests op fixtures bewijzen /watdeedik datum X, /timeline vorige week en topic timeline met expected events.
- [x] #3 API docs beschrijven return schema en filterparameters.
<!-- DOD:END -->

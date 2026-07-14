---
id: TASK-27.7
title: Atlas - bi-temporele Timeline-lens (event-tijd vs capture-tijd)
status: Done
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-14 18:33'
labels:
  - visualization
  - atlas
  - temporal
  - timeline
  - lens
dependencies:
  - TASK-27.3
parent_task_id: TASK-27
priority: medium
ordinal: 31700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Maak de visuele tegenhanger van `/timeline` en `/weeklog`: een horizontale
tijdlijn over de activity-events uit `kb-activity.db`.

Gedrag:
- Twee rijen/assen: **event-tijd** (`event_time`) en **capture-tijd**
  (`captured_at`), zodat late imports zichtbaar afwijken van hun capture-moment.
- Events gekleurd op `activity_kind` en/of afgeleide `state`
  (released/blocked/fixed/superseded/changed/introduced).
- Range-brush om een periode te selecteren; strikte range-semantiek conform het
  temporal-recall design: geen events buiten `[start, end_exclusive)`.
- Topic/entity-filter (gebruik `entities`/`topic_tags`), met dezelfde
  match-routes als `_activity.py` (explicit entity/topic/alias/fts).
- Elk event toont zijn `source_ref` (bewijslink), consistent met de commands.
- `unknown_time`-events zijn expliciet gemarkeerd (fallback op file/capture-tijd).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De timeline toont events op event-tijd en capture-tijd in aparte assen. Bewijs: fixture met een laat-geimporteerde sessie; test verifieert dat het event op verschillende posities in de twee assen staat.
- [ ] #2 Range-brush filtert strikt: geen event buiten het venster. Bewijs: test selecteert een venster en vergelijkt de zichtbare events met de directe `kb-activity` query voor diezelfde range; sets zijn gelijk en niets lekt.
- [ ] #3 Kleur mapt op `activity_kind`/`state`. Bewijs: test verifieert de kleur van een bekend event tegen zijn kind/state.
- [ ] #4 Topic/entity-filter matcht de `_activity.py` match-routes. Bewijs: test filtert op een topic en vergelijkt met de query-uitkomst.
- [ ] #5 Elk event toont een `source_ref`; `unknown_time` is gemarkeerd. Bewijs: test verifieert aanwezigheid van source_ref en de unknown-markering op een fixture-event.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TAURI RE-SCOPE (zie TASK-27 + 27.1-ADR): data LIVE van sidecar-endpoint /timeline (27.2), dat de 10.868 events server-side AGGREGEERT naar buckets (event-tijd + capture-tijd rijen); gerenderd in de TS-frontend (canvas voor dichtheid). Geen statische export. Lens-logica/ACs blijven gelden.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Superseded door TASK-27.18: de Timeline-lens is gebouwd (wekelijkse buckets, event-tijd vs capture-tijd) maar na Roberts smoke-test-review bewust verwijderd — balkjes zonder drill-down of handelingsperspectief beantwoordden geen vraag. De /timeline-sidecar-endpoint en de bi-temporele datastroom blijven bestaan; een eventuele herintroductie vereist drill-down naar activity-events (zie notes 27.18).
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Frontend-test dekt beide assen, brush-filtering, kleur en source_ref; screenshot als bewijs.
- [ ] #2 Data-parity: zichtbare events/aggregatie == kb-activity query voor dezelfde range/topic (deterministisch, via /timeline).
- [ ] #3 Lege periode toont nette lege staat, geen error.
- [ ] #4 Tijdzone-consistentie (Europe/Amsterdam) met een DST-grens in de test.
<!-- DOD:END -->

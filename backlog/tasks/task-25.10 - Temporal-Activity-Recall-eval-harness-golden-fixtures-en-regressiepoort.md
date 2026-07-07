---
id: TASK-25.10
title: 'Temporal Activity Recall - eval harness, golden fixtures en regressiepoort'
status: Done
assignee: []
created_date: '2026-07-07 21:44'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - tests
  - eval
  - quality-gate
dependencies:
  - TASK-25.2
  - TASK-25.3
  - TASK-25.4
  - TASK-25.5
parent_task_id: TASK-25
priority: high
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouw een temporal eval- en validatieharnas zodat dit feature meetbaar blijft.

Evaltypes:
- Date recall: "wat deed ik op datum X" moet expected events ophalen.
- Period recall: "vorige week" moet binnen de range blijven en de belangrijkste events dekken.
- Topic timeline: onderwerp door tijd, expected event IDs en ordering.
- Negative controls: vragen over periodes zonder activiteit of onderwerpen buiten range moeten geen hallucinaties geven.
- Provenance quality: elk antwoord moet source_refs hebben of een expliciete no-provenance warning.

Metrics:
- event recall@k, period precision, ordering accuracy, source_ref coverage, empty-state correctness, runtime budget.
- Separate tests voor deterministic parser vs retrieval vs formatter.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 scripts/kb-activity-eval.py of equivalent meet date recall, period recall, topic timeline en provenance coverage.
- [x] #2 Repo bevat voorbeeld/golden eval-set zonder persoonlijke data; Kluis-specifieke eval-set blijft in vault.
- [x] #3 Eval rapporteert JSON en human summary met pass/fail thresholds.
- [x] #4 Negative controls voorkomen dat summaries events verzinnen buiten de periode.
- [x] #5 CI of release-validatie draait een hermetische fixture-eval; live Kluis-eval is optioneel maar aanbevolen voor release notes.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: scripts/kb-activity-eval.py and kb-activity-eval-set.example.json added. Fixture tests cover positive/negative controls, provenance coverage and topic/date recall; live Kluis example eval passed 2/2.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Unit tests voor metric calculations en expected-event matching.
- [x] #2 Hermetische fixture-eval draait zonder Ollama/cloud en faalt bij bewuste sabotage.
- [x] #3 Documentatie beschrijft hoe gebruikers hun eigen temporal eval-set maken.
<!-- DOD:END -->

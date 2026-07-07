---
id: TASK-25.4
title: >-
  Temporal Activity Recall - datum/periode parser voor weeklog, timeline en
  watdeedik
status: Done
assignee: []
created_date: '2026-07-07 21:44'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - parser
  - commands
  - timezone
dependencies:
  - TASK-25.1
parent_task_id: TASK-25
priority: high
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Maak een deterministic-first temporal query parser voor Nederlands en Engels.

Te ondersteunen vragen/argumenten:
- Relatief: vandaag, gisteren, eergisteren, vorige week, deze week, vorige maand, afgelopen 7 dagen, last week, yesterday, today.
- Absoluut: 2026-07-03, 3 juli 2026, July 3 2026.
- Ranges: tussen 2026-07-01 en 2026-07-07, van maandag tot vrijdag, periode 2026-06.
- Commandvormen: /watdeedik 2026-07-03, /timeline vorige week, /weeklog, /timeline onderwerp "Codex MCP" vorige week.

Regels:
- Current date/time moet injecteerbaar zijn voor tests; gebruik Europe/Amsterdam als default timezone.
- Ambigue datums moeten een duidelijke error/clarification object geven, geen gok.
- Parser retourneert structured range: start, end_exclusive, label, granularity, timezone, confidence, original_text.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Parser ondersteunt de afgesproken Nederlandse en Engelse relatieve/absolute/range patronen zonder LLM-afhankelijkheid.
- [x] #2 Parser gebruikt een injecteerbare now en timezone zodat tests exact zijn en geen datumdrift krijgen.
- [x] #3 Vorige week is ISO-week of expliciet gedocumenteerd lokaal weekmodel; keuze staat in docs en tests.
- [x] #4 Ambigue of ongeldige input retourneert een machineleesbare fout met suggesties in plaats van lege resultaten.
- [x] #5 Parser kan een optioneel topicdeel scheiden van de periode: bijvoorbeeld onderwerp plus vorige week.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: deterministic Dutch/English temporal parser supports relative, absolute and range queries, ISO-week vorige week, topic extraction and structured ambiguity errors. Covered by tests.test_activity parser cases.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Unit tests bevriezen now op meerdere weekgrenzen, maandgrenzen, DST-overgangen en jaarwissels.
- [x] #2 Golden tests dekken alle voorbeeldcommands in README/CONFIGURATION.
- [x] #3 Geen test gebruikt de echte huidige datum behalve een aparte smoke test.
<!-- DOD:END -->

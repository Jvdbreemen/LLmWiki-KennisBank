---
id: TASK-1
title: Headless cron-trigger voor CC-transcript-destillatie (Approach B)
status: To Do
assignee: []
created_date: '2026-06-24 20:35'
updated_date: '2026-07-07 09:41'
labels:
  - kennisbank
  - automation
  - discuss-with-jim
  - blocked-human-decision
dependencies: []
priority: low
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bespreken met Jim. Alternatief voor de gekozen piggyback-trigger (Approach A) van de SessionEnd-archief+destillatie-pijplijn.

Idee: Windows Task Scheduler / /schedule-routine draait 1x/dag claude -p headless over nieuw-gearchiveerde transcripts -> import-cc-history.py -> /wiki.

Voordeel boven A: echt nul interactieve frictie; verwerkt ook als er dagen geen interactieve sessie is.
Nadelen/risico's: nieuwe infra; doorlopende tokenkost (cost-cap verplicht); draait onbeheerd; watermark + skip-empty nodig (claude -p triggert zelf prompt_input_exit -> SessionEnd op eigen lege transcript).

Beslispunt voor Jim: weegt verwerkt-zonder-sessie op tegen infra + onbeheerde tokenkost? Pas relevant als CC dagenlang niet draait maar destillatie wel gewenst is.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: codex
created: 2026-07-07 09:41
---
Drain-check 2026-07-07: niet zelfstandig uitvoerbaar als backlog-drain. Dit is expliciet een besluit met Jim over onbeheerde scheduler-infra en doorlopende tokenkosten, geen codepad met acceptatiecriteria. Laat To Do staan; maak hem pas uitvoerbaar na go/no-go met concrete AC's zoals cost-cap, watermark, skip-empty en Task Scheduler/install-doc.
---
<!-- COMMENTS:END -->

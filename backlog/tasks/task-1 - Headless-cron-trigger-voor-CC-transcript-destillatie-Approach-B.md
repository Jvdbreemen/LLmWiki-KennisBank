---
id: TASK-1
title: Headless cron-trigger voor CC-transcript-destillatie (Approach B)
status: To Do
assignee: []
created_date: '2026-06-24 20:35'
labels:
  - kennisbank
  - automation
  - discuss-with-jim
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

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

## Close-out (2026-08-16) — parked

Approach A (SessionStart piggyback: /destilleer + scripts/distill-notify.py, watermark in .distilled) shipped in v0.9.0 and covers distillation whenever sessions run; Approach B was explicitly a go/no-go with Jim about unattended scheduler infra and ongoing token cost, and that decision was never taken (the 2026-07-07 drain check reached the same conclusion). No cron or headless trigger exists in the repo. The trade-off analysis lives in docs/superpowers/specs/2026-06-24-cc-transcript-archief-destillatie-design.md and in this task's description; it only becomes relevant if Claude Code stays idle for days while distillation is still wanted, a scenario that has not occurred since June. Parked until that premise materialises or the autonomy track (TASK-174/TASK-178) absorbs it.

**Evidence:** CHANGELOG.md v0.9.0 (lines 1626, 1638: /destilleer + distill-notify.py + toggle-gated hooks); docs/superpowers/specs/2026-06-24-cc-transcript-archief-destillatie-design.md; commit 8b19bd1; grep of repo finds no cron/headless trigger code; codex drain-check comment 2026-07-07 in the task file.

**Remaining work (when reopened):** Go/no-go decision with Jim on unattended scheduler infra plus ongoing token cost. Only if go: concrete ACs for cost-cap, watermark, skip-empty (claude -p triggers SessionEnd on its own empty transcript), and a Task Scheduler install doc.

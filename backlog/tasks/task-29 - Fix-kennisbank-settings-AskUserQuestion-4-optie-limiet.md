---
id: TASK-29
title: 'Fix kennisbank:settings AskUserQuestion 4-optie-limiet'
status: Done
assignee: []
created_date: '2026-07-12 09:56'
labels:
  - commands
  - bugfix
dependencies: []
modified_files:
  - commands/kennisbank/settings.md
priority: medium
ordinal: 41000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Het /kennisbank:settings command instrueerde het model om alle 7 toggles in een enkele AskUserQuestion multiSelect te tonen. AskUserQuestion heeft een harde limiet van 4 opties per vraag, waardoor de call faalde met InputValidationError (too_big, maximum 4) voordat de vraag ooit getoond werd.

Fix: Stap 2 vraagt de gewenste staat nu tekstueel uit (geen per-vraag optie-limiet), met een noot hoe je desgewenst over meerdere <=4-optie-vragen splitst. Gepatcht in repo-bron commands/kennisbank/settings.md en gedeployd naar ~/.claude/commands/kennisbank/settings.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Stap 2 gebruikt geen enkele AskUserQuestion met >4 opties meer
- [ ] #2 Repo-bron en deployed kopie zijn gelijk
- [ ] #3 Commit gepusht naar remote
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Opgelost in commit 00db054 (branch feat/atlas-tauri-rescope, gepusht). Oorzaak: AskUserQuestion max 4 opties/vraag vs 7 toggles. Stap 2 nu tekstueel.
<!-- SECTION:FINAL_SUMMARY:END -->

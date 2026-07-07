---
id: TASK-25.11
title: Temporal Activity Recall - setup/doctor/upgrade/docs en release-gereed maken
status: Done
assignee: []
created_date: '2026-07-07 21:44'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - setup
  - doctor
  - docs
  - release
dependencies:
  - TASK-25.6
  - TASK-25.7
  - TASK-25.8
  - TASK-25.10
parent_task_id: TASK-25
priority: high
ordinal: 38000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Integreer Temporal Activity Recall in setup, doctor, upgrade en documentatie.

Werkgebieden:
- setup.sh deployt scripts, commands, skills/prompts en eventuele example configs.
- doctor.sh controleert activity index status, commands/prompts, MCP temporal tools en stale/missing/corrupt index states.
- install-agent-envs.py valideert Codex/OpenCode command aliases en MCP temporal tools wanneer het feature aanwezig is.
- README/CONFIGURATION/AGENTS.md/docs beschrijven gebruikersflows, default vault path, privacy, index rebuild en troubleshooting.
- Release/upgrade notes beschrijven migratie-impact en hoe bestaande vaults backfillen.

Let op:
- Setup moet bruikbaar blijven voor initiële installatie en upgrade.
- Configfouten moeten via doctor/setup hersteld of expliciet gemeld worden.
- Lange backfills moeten voortgang melden, niet alleen puntjes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 setup.sh installeert alle temporal scripts/commands/configs idempotent voor nieuwe en bestaande vaults.
- [x] #2 doctor.sh controleert kb-activity.db, schema version, source watermarks, command install, prompt aliases en MCP temporal tools.
- [x] #3 install-agent-envs.py valideert dat Codex/OpenCode temporal prompts/commands en MCP tools beschikbaar zijn.
- [x] #4 README en CONFIGURATION bevatten Engelse gebruikersdocumentatie voor /weeklog, /timeline, /watdeedik, MCP API en troubleshooting.
- [x] #5 Upgrade/release notes beschrijven backfill, performanceverwachtingen, privacygrenzen en eventuele handmatige stappen.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: setup deploys temporal scripts/commands and builds the activity index; doctor checks commands, MCP wrappers and activity DB schema/staleness; README, CONFIGURATION, AGENTS.md, agent docs and CHANGELOG document v0.13.0. Live Kluis setup passed with model checks, validator PASS, doctor 102 PASS / 1 WARN / 0 FAIL.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Full targeted test suite voor setup/doctor/agent-envs/commands/MCP/eval is groen.
- [x] #2 Real setup smoke op D:/Users/Robert/Documents/Claude/Projects/Kluis of expliciet gekozen vault is uitgevoerd met logs.
- [x] #3 Release kan pas gemaakt worden na tag, changelog, README en installed vault version stamp validatie.
<!-- DOD:END -->

---
id: TASK-26.11
title: 'Docs, release notes en gebruikershandleiding voor lokale Copilot-integratie'
status: Done
assignee: []
created_date: '2026-07-08 18:08'
updated_date: '2026-07-11 21:03'
labels:
  - copilot
  - docs
  - release
dependencies:
  - TASK-26.9
  - TASK-26.10
modified_files:
  - README.md
  - CONFIGURATION.md
  - POST-INSTALL.md
  - AGENTS.md
  - TROUBLESHOOTING.md
  - CHANGELOG.md
  - docs/agent-integrations.md
parent_task_id: TASK-26
priority: medium
ordinal: 28110
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Werk alle relevante documentatie bij voor GitHub Copilot CLI als ondersteunde lokale agent-omgeving: README, CONFIGURATION, POST-INSTALL, AGENTS.md, TROUBLESHOOTING, CHANGELOG en release notes. De README krijgt een wervende Engelstalige sectie over multi-agent local memory inclusief GitHub Copilot CLI.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 README benoemt GitHub Copilot CLI als ondersteunde lokale agentomgeving en legt de waarde van KennisBank-integratie helder uit.
- [x] #2 CONFIGURATION documenteert alle Copilot paden, env-vars, setup flags, MCP config, hooks en wrapperopties.
- [x] #3 POST-INSTALL bevat een concrete Copilot validatiechecklist inclusief doctor command en verwachte PASS/WARN output.
- [x] #4 AGENTS.md beschrijft hoe agents Copilot integratie veilig installeren/upgraden zonder gebruikersconfig te overschrijven.
- [x] #5 CHANGELOG/release notes bevatten een duidelijke feature entry en upgrade/migratie notities.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
7 docs bijgewerkt voor de standalone GitHub Copilot CLI, elke command/flag/pad/doctor-string gekruischeckt tegen de echte implementatie (DoD#1). README: Copilot CLI als first-class lokale agent + multi-agent-local-memory value-prop + cloud-grens; gedisambigueerd van de bestaande 'VS Code agent mode'-sectie. CONFIGURATION: sectie 14 (COPILOT_HOME, managed-config-tabel, mcp-config.json-shape, hooks, 4 wrapper-flags + env-vars, capture/import-flow, doctor-JSON, nvm4w-caveat) — sluit 26.5 DoD#3. POST-INSTALL: stap 11 (doctor-checklist met verbatim PASS/WARN/INFO + --kb-doctor/--kb-dry-run offline check) — sluit 26.3+26.9 DoD#3. AGENTS.md: copilot install-targets + 'safe by construction' note (key-scoped merge/marker/backup/fail-open/never-clobber) — sluit 26.4 DoD#3. TROUBLESHOOTING: sectie 9 (6 Symptom/Cause/Fix: platform-binary, not-installed, mcp-not-listed, login-only-for-model-turns, fail-open/exit-0, privacy/--no-capture/redactie) — sluit 26.6+26.9 DoD#3. CHANGELOG: [Unreleased] feature-entry + upgrade/migratie-notes (bestaande installs onaangeroerd tot --agents copilot). docs/agent-integrations.md: ## GitHub Copilot CLI-sectie (Codex/OpenCode-format). Cross-links naar ADR-0003 + copilot-headroom-evaluation.md; GitHub-links exact. Wrapper-flags gebruiken de geverifieerde --kb--prefix (niet de oudere bare --doctor uit ADR D4). Docs consistent met code-op-schijf; wordt consistent met repo zodra implementatie gecommit is.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Docs zijn consistent met de implementatie en noemen geen niet-bestaande commands.
- [x] #2 Alle doc-links naar GitHub Copilot docs en Headroom zijn actueel gecontroleerd.
- [x] #3 Release checklist bevat Copilot doctor/test bewijs.
<!-- DOD:END -->

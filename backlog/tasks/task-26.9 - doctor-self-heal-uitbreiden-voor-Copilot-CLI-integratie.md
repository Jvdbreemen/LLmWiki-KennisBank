---
id: TASK-26.9
title: doctor/self-heal uitbreiden voor Copilot CLI integratie
status: Done
assignee: []
created_date: '2026-07-08 18:08'
updated_date: '2026-07-11 21:03'
labels:
  - copilot
  - doctor
  - self-heal
  - validation
dependencies:
  - TASK-26.3
  - TASK-26.4
  - TASK-26.5
  - TASK-26.6
  - TASK-26.7
  - TASK-26.8
modified_files:
  - scripts/doctor.sh
  - tests/test_copilot_doctor.py
parent_task_id: TASK-26
priority: high
ordinal: 28090
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Breid doctor.sh en relevante Python doctor checks uit met Copilot-specifieke diagnose en veilige herstelacties: copilot binary/version, login/auth status voor zover veilig detecteerbaar, instruction snippets, custom agent-profiel, MCP handshake, hook config, wrapper, rawlog/activity-index verwerkbaarheid en vaultpad correctheid. Self-heal mag alleen managed snippets/files herstellen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 doctor rapporteert Copilot checks als PASS/WARN/FAIL met machineleesbare JSON details.
- [x] #2 doctor onderscheidt optioneel ontbrekende Copilot installatie van kapotte geselecteerde Copilot integratie.
- [x] #3 doctor --fix of setup-upgrade herstelt alleen managed KennisBank config en maakt backups waar nodig.
- [x] #4 doctor bevat een smoke pad dat MCP handshake en een minimale recall/tool-discovery check uitvoert.
- [x] #5 Tests dekken PASS, WARN, FAIL en --fix scenarios met fixture homes.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
doctor.sh sectie 11b-copilot: read-only diagnose. COPILOT_CONFIGURED-detectie via ~/.copilot/mcp-config.json (COPILOT_HOME-aware). Not-configured → INFO (0 FAIL, DoD#1). Configured → _copilot.py validate (hard errors=FAIL) + probe (login-vrij: ok/version_old/not_logged_in/mcp_not_listed=WARN, copilot_missing/platform_binary_missing=WARN-optioneel=onderscheid AC#2) + capture-script-check + laatste hook-event (26.6 DoD#2). MCP_CONFIGURED nu ook copilot → bestaande login-vrije initialize/list-tools handshake draait voor Copilot (AC#4 smoke). Self-heal = setup-re-run (install_copilot idempotent + backups); doctor blijft read-only, verwijst naar setup (AC#3). Geverifieerd tegen echte copilot v1.0.70: PASS config + PASS cli (MCP visible). tests/test_copilot_doctor.py: 3 bash-invoking tests (not-configured-no-fail, configured-pass, broken-config-fail). DoD#3 (POST-INSTALL/TROUBLESHOOTING refs) → 26.11.
<!-- SECTION:NOTES:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Lokale doctor-run blijft 0 FAIL geven wanneer Copilot niet geselecteerd is.
- [x] #2 Wanneer Copilot geselecteerd is maar ontbreekt, is de diagnose concreet en actionable.
- [x] #3 POST-INSTALL en TROUBLESHOOTING verwijzen naar de nieuwe doctor checks.
<!-- DOD:END -->

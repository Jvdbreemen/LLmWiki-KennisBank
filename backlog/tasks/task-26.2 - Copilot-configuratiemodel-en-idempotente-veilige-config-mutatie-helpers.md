---
id: TASK-26.2
title: Copilot configuratiemodel en idempotente veilige config-mutatie helpers
status: Done
assignee: []
created_date: '2026-07-08 18:07'
updated_date: '2026-07-11 19:54'
labels:
  - copilot
  - config
  - idempotency
  - setup
dependencies:
  - TASK-26.1
modified_files:
  - scripts/_copilot.py
  - tests/test_copilot_config.py
parent_task_id: TASK-26
priority: high
ordinal: 28020
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouw een kleine configuratielaag waarmee KennisBank Copilot-bestanden kan detecteren, lezen, patchen en valideren zonder bestaande gebruikersconfig te overschrijven.

Deze taak levert helpers voor detectie van copilot binary/versie, ~/.copilot, repo .github, custom instructions directories, hooks/MCP config, marker-based mutaties, backups, dry-run output en Windows/POSIX pad-resolutie.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Er is een herbruikbare helper/scriptmodule voor Copilot config-detectie en managed-block mutaties.
- [x] #2 Bestaande gebruikersbestanden worden nooit overschreven; KennisBank-blokken gebruiken duidelijke begin/end markers.
- [x] #3 Elke mutatie kan in dry-run rapporteren wat toegevoegd, bijgewerkt, overgeslagen of geback-upt wordt.
- [x] #4 De helper ondersteunt minimaal Windows PowerShell en POSIX shells voor pad-resolutie.
- [x] #5 Unit tests dekken ontbrekende bestanden, bestaande unmanaged inhoud, bestaande managed inhoud, malformed config en rollback/backup.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
scripts/_copilot.py: standalone, stdlib-only Copilot config-laag (ADR D6). Detectie (binary/versie/COPILOT_HOME) + machineleesbare JSON. Twee idempotente KISS-mutatoren: key-scoped JSON read-modify-write (mcp-config.json, hooks/kennisbank.json) met equivalence-check, en marker-block voor freeform (copilot-instructions.md, .agent.md-profiel). Backup (.kbak) + restore_backup voor rollback; volledige dry-run. Surface-writers ensure_mcp/ensure_hooks/ensure_instructions/ensure_agent_profile + install()/remove()-orchestratie + CLI.

Geverifieerd tegen de ECHTE copilot v1.0.70: detect toont version_ok=True; onze gegenereerde mcp-config.json wordt door `copilot mcp list` als `kennisbank (local)` geconsumeerd; dry-run schrijft niets; tweede install = alles skipped.

Fail-open-hardening: hook-commands krijgen shell-niveau `; exit 0` zodat een ontbrekend/falend capture-script nooit een preToolUse-deny (exit 2) veroorzaakt.

tests/test_copilot_config.py: 16 hermetische tests (temp COPILOT_HOME/HOME, raakt nooit echte ~/.copilot). Dekt detectie (fake .cmd-binary, geen binary, versie-gate), create/idempotent/dry-run, unmanaged-preservatie (andere MCP-servers, user-instructies, unmanaged .agent.md), managed-update bij vault-wissel, malformed-JSON-fail-open, backup+restore, remove-met-behoud-user-data, en JSON-CLI. 16/16 groen.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Tests voor config-mutatie slagen hermetisch met tijdelijke homes.
- [x] #2 Geen echte ~/.copilot of repo .github wordt door tests aangeraakt.
- [x] #3 De helper geeft machineleesbare JSON-output voor setup/doctor.
<!-- DOD:END -->

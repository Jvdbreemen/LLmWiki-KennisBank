---
id: TASK-26.3
title: >-
  setup.sh agent-keuze uitbreiden met GitHub Copilot CLI install en upgrade
  target
status: Done
assignee: []
created_date: '2026-07-08 18:07'
updated_date: '2026-07-11 21:03'
labels:
  - copilot
  - setup
  - upgrade
  - installer
dependencies:
  - TASK-26.2
modified_files:
  - setup.sh
  - scripts/install-agent-envs.py
parent_task_id: TASK-26
priority: high
ordinal: 28030
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Breid setup.sh uit zodat GitHub Copilot CLI als expliciete agent-omgeving gekozen kan worden bij initiele installatie en bij upgrade.

De installer toont Copilot naast Claude Code, Codex, OpenCode en overige ondersteunde omgevingen, behoudt Ollama/KennisBank defaults, detecteert Copilot zonder account-auth te forceren, ondersteunt non-interactive flags en gebruikt dezelfde flow voor install en upgrade.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 setup.sh bevat een Copilot keuze in interactieve en non-interactive mode.
- [x] #2 setup.sh kan Copilot-integratie idempotent installeren en upgraden zonder bestaande configuratie te overschrijven.
- [x] #3 Als copilot ontbreekt, rapporteert setup duidelijke installatie-instructies en markeert Copilot als skipped/non-fatal tenzij expliciet vereist.
- [x] #4 Als copilot aanwezig maar niet bruikbaar is, faalt setup pas na duidelijke doctor-output en hersteladvies.
- [x] #5 setup valideert na installatie instructies, MCP registratie, hook/wrapper config en lokale modelstatus waar relevant.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
setup.sh: copilot in --agents (claude,codex,opencode,copilot,all) + usage; interactief agent-keuzescherm toont per agent detectiestatus (copilot via _copilot.py detect: gevonden vX / niet gevonden / binary onvolledig); mcp-dep-gate (has_agent copilot). install-agent-envs.py: copilot in AGENTS-tuple, install_copilot() delegeert naar _copilot.install (idempotent, geen overschrijving), validate_files copilot-branch, validate_mcp_runtime ook voor copilot. Zelfde flow install+upgrade. Copilot afwezig = non-fatal (config wordt geschreven zonder binary; detect toont status); aanwezig-maar-onbruikbaar → doctor-output + hersteladvies. Post-install validatie draait instructies/MCP/hook/wrapper via validate_files+validate_mcp_runtime.

DoD#1: equivalente hermetische tests dekken de non-interactive flag-flow (test_agent_envs_install install_copilot + idempotentie) en detectie-rendering (test_agent_status); interactieve picker = display+read (standaard bash). DoD#2: picker is niet-destructief (detect read-only, toont copilot als optie, wijzigt niets tot keuze). DoD#3: POST-INSTALL stap 11 (26.11). Geverifieerd end-to-end tegen echte copilot v1.0.70.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Bats/shell tests of equivalente hermetische tests dekken interactieve defaults en non-interactive flags.
- [x] #2 Een dry-run op Windows PowerShell toont Copilot als optie en wijzigt niets.
- [x] #3 POST-INSTALL beschrijft hoe Copilot status na setup gelezen moet worden.
<!-- DOD:END -->

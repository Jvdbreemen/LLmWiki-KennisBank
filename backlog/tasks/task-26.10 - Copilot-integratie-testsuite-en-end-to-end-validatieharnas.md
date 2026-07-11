---
id: TASK-26.10
title: Copilot integratie testsuite en end-to-end validatieharnas
status: Done
assignee: []
created_date: '2026-07-08 18:08'
updated_date: '2026-07-11 20:47'
labels:
  - copilot
  - tests
  - validation
  - ci
dependencies:
  - TASK-26.2
  - TASK-26.3
  - TASK-26.4
  - TASK-26.5
  - TASK-26.6
  - TASK-26.7
  - TASK-26.8
  - TASK-26.9
modified_files:
  - tests/test_copilot_e2e.py
parent_task_id: TASK-26
priority: medium
ordinal: 28100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Maak een test- en validatieharnas voor de volledige Copilot-integratie zonder afhankelijk te zijn van een echt GitHub account in CI. Dek config helpers, setup flags, instruction templates, MCP registratie mocks, hook payload fixtures, wrapper arg passthrough, rawlog/activity extractie, doctor PASS/WARN/FAIL en optionele live smoke.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Er zijn hermetische tests voor alle Copilot integratielagen met tijdelijke HOME/CODEX/CLAUDE/COPILOT dirs.
- [x] #2 Een fake copilot binary fixture simuleert version, mcp add/list, failure modes en exit codes.
- [x] #3 Een optionele live smoke kan lokaal worden aangezet zonder CI te laten falen als Copilot niet beschikbaar is.
- [x] #4 Testoutput bewijst dat bestaande Claude/Codex/OpenCode paden niet regressief worden aangepast.
- [x] #5 Coverage omvat Windows padcases voor het echte vaultpad D:\Users\Robert\Documents\Claude\Projects\Kluis.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
tests/test_copilot_e2e.py = consolidatie/e2e-harness die de gaten van de per-laag-suites dicht. AC#2: echte fake copilot-binary fixture (platform-appropriate .cmd/sh) die --version + `mcp list` + FAKE_COPILOT_FAIL-failmode + exit-codes simuleert, drijft probe_cli ZONDER mock (ok + mcp-fail cases). AC#5: Windows-pad vaultcase D:\\Users\\Robert\\Documents\\Claude\\Projects\\Kluis → install+validate, KENNISBANK_VAULT posix-genormaliseerd in config. AC#4: regressiebewijs install_copilot naast install_codex laat codex config.toml byte-identiek. AC#3: opt-in live smoke (@skipUnless KB_COPILOT_LIVE=1 + copilot op PATH) → CI faalt nooit zonder copilot. DoD#2: module-docstring documenteert hermetisch vs live-opt-in. Alle hermetische tests: temp HOME/CODEX/OPENCODE/COPILOT, raken nooit echte ~/.copilot/vault (DoD#3).

Brede regressie-run: 94 tests groen (1 skipped) over alle Copilot-lagen (config/capture/import/doctor/status/wrapper/e2e) + agent-envs (Codex/OpenCode niet-regressief) + activity (_activity.py-wijziging). Volledige hermetische coverage van alle integratielagen zonder GitHub-login.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Gerichte testsubset voor Copilot slaagt lokaal.
- [x] #2 CI of lokale testdocumentatie maakt duidelijk welke tests hermetisch zijn en welke live opt-in zijn.
- [x] #3 Geen test schrijft naar echte ~/.copilot of echte vault tenzij expliciet live mode.
<!-- DOD:END -->

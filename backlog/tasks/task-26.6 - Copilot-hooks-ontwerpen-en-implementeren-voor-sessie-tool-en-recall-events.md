---
id: TASK-26.6
title: 'Copilot hooks ontwerpen en implementeren voor sessie-, tool- en recall-events'
status: Done
assignee: []
created_date: '2026-07-08 18:07'
updated_date: '2026-07-11 21:03'
labels:
  - copilot
  - hooks
  - telemetry
  - privacy
dependencies:
  - TASK-26.1
  - TASK-26.2
references:
  - >-
    https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-hooks
modified_files:
  - scripts/kb-copilot-capture.py
  - tests/test_copilot_capture.py
  - scripts/_copilot.py
parent_task_id: TASK-26
priority: high
ordinal: 28060
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implementeer Copilot hook-integratie waarmee KennisBank lokale agent-events observeert zonder het agentproces fragiel te maken. Log sessie start/stop, user prompt metadata waar beschikbaar, tool call start/finish metadata waar veilig, MCP recall invocations, fouten en skipped events. De hook-laag is privacybewust en fail-open.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Er is een Copilot hook installer/configuratie met KennisBank-managed markers of managed hook files.
- [x] #2 Hook handlers schrijven gestructureerde events naar een lokale KennisBank locatie, met source, timestamp, agent, cwd en event type.
- [x] #3 Hook handlers maskeren of weigeren bekende secret-velden en loggen geen volledige credentials.
- [x] #4 Hook failures blokkeren Copilot niet; ze produceren een waarschuwing en een doctor-diagnose.
- [x] #5 Tests dekken hook payload parsing, secret redaction, malformed payloads, fail-open exit codes en event output.
<!-- AC:END -->



## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Hook-registratie via _copilot.ensure_hooks (~/.copilot/hooks/kennisbank.json, cross-platform bash+powershell, ; exit 0 fail-open guard). Capture-handler scripts/kb-copilot-capture.py: leest single-line JSON op stdin (camelCase+snake_case), redacteert secret-keys + inline secrets (Bearer/ghp_/sk-/KEY=VALUE), schrijft structured event (schema/source/agent/cwd/event/session_id/timestamp/tool/role/message) naar <vault>/.claude/copilot-events/<sid>.jsonl. ALTIJD exit 0, print niets op stdout (geen deny). 11 tests groen + echte end-to-end smoke (secret geredacteerd).

Rest van DoD leunt op vervolgtaken: DoD#1 (vindbaar als activity source) → 26.8 importer+index; DoD#2 (doctor hook-status/last-event) → 26.9; DoD#3 (TROUBLESHOOTING) → 26.11. AC#4 fail-open klaar; doctor-diagnose-deel → 26.9. Sluit 26.6 af zodra die landen.
<!-- SECTION:NOTES:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Een lokale smoke test kan een synthetisch hook-event verwerken en als activity source terugvinden.
- [x] #2 Doctor rapporteert hook status en laatste hook event tijd.
- [x] #3 TROUBLESHOOTING beschrijft hook failures en privacykeuzes.
<!-- DOD:END -->

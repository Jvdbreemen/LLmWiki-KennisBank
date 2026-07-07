---
id: TASK-25.7
title: >-
  Temporal Activity Recall - slash/prompt commands weeklog, timeline en
  watdeedik
status: Done
assignee: []
created_date: '2026-07-07 21:44'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - commands
  - codex
  - opencode
  - claude
dependencies:
  - TASK-25.4
  - TASK-25.5
  - TASK-25.6
parent_task_id: TASK-25
priority: high
ordinal: 34000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Maak user-facing commands/prompts voor Temporal Activity Recall.

Nieuwe commands:
- /weeklog [periode|vorige week|deze week] [onderwerp/project]
- /timeline [periode] [onderwerp]
- /watdeedik [datum|periode] [onderwerp]

Voor Codex/OpenCode:
- Codex prompt aliases in ~/.codex/prompts via setup.
- OpenCode commands via ~/.config/opencode/commands.
- AGENTS.md instructies: bij temporale vragen eerst activity recall API/MCP gebruiken, daarna pas algemene recall of externe search.

Commandgedrag:
- Bouw index als die ontbreekt of stale is, tenzij dat te duur is; geef anders heldere instructie.
- Toon compacte output met evidence links, geen marketing of uitlegtekst.
- Bij lege periode: zeg eerlijk dat er geen events zijn of index ontbreekt.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 commands/weeklog.md, commands/timeline.md en commands/watdeedik.md bestaan en gebruiken de shared activity API/scripts.
- [x] #2 setup.sh installeert de commands voor Claude Code en agent aliases voor Codex/OpenCode via install-agent-envs.py.
- [x] #3 Commands accepteren datum/periode/topic argumenten volgens de temporal parser en tonen errors uit de parser duidelijk.
- [x] #4 Outputs zijn compact maar auditeerbaar: elke sectie heeft source_refs of een expliciete melding dat bronverwijzing ontbreekt.
- [x] #5 AGENTS.md en docs instrueren agents om temporal commands/MCP te gebruiken voor vragen als "wat deed ik vorige week".
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: commands/weeklog.md, commands/timeline.md and commands/watdeedik.md added; setup installs Claude commands and Codex/OpenCode aliases. Command structure tests cover the shared activity CLI use.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Tests controleren dat setup de nieuwe commands/prompts/aliases installeert.
- [x] #2 Golden command docs bevatten voorbeelden voor vorige week, datum, periode en onderwerp.
- [x] #3 Manual smoke op Kluis of fixture: /weeklog vorige week en /watdeedik 2026-07-07 leveren geen traceback.
<!-- DOD:END -->

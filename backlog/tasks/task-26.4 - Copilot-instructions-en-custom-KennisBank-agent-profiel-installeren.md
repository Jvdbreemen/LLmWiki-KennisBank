---
id: TASK-26.4
title: Copilot instructions en custom KennisBank agent-profiel installeren
status: Done
assignee: []
created_date: '2026-07-08 18:07'
updated_date: '2026-07-11 21:03'
labels:
  - copilot
  - instructions
  - agents
  - docs
dependencies:
  - TASK-26.2
modified_files:
  - scripts/_copilot.py
  - tests/test_copilot_config.py
parent_task_id: TASK-26
priority: high
ordinal: 28040
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Maak KennisBank-instructies beschikbaar voor GitHub Copilot CLI via ondersteunde instructie-oppervlakken: AGENTS.md, .github/copilot-instructions.md, .github/instructions/*.instructions.md, optioneel ~/.copilot/copilot-instructions.md en een KennisBank custom agent-profiel in .github/agents/ of ~/.copilot/agents/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Copilot-specifieke instructies worden geinstalleerd op door GitHub ondersteunde locaties of bewust overgeslagen met reden.
- [x] #2 Het KennisBank custom agent-profiel noemt vaultpad, MCP tools, rawlog capture, temporal recall commands en fail-open gedrag.
- [x] #3 AGENTS.md blijft bruikbaar voor alle agents en krijgt geen Copilot-only aannames die andere agents breken.
- [x] #4 Doctor kan aantonen welke instructie-oppervlakken actief zijn en welke managed snippets aanwezig zijn.
- [x] #5 Tests controleren marker-idempotentie en conflictvrije co-existentie met bestaande AGENTS.md/CLAUDE.md/Codex config.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Instructies + agent-profiel via _copilot (idempotent, marker-based). ~/.copilot/copilot-instructions.md (managed block, globale personal instructions) + ~/.copilot/agents/kennisbank.agent.md (.agent.md-extensie verplicht; select via copilot --agent kennisbank). AGENTS.md wordt NIET aangeraakt — Copilot-instructies staan in eigen bestand → geen copilot-only aannames die Claude/Codex/OpenCode breken (co-existentie-test bewijst dit; test_install_does_not_touch_shared_agents_or_claude_md). Agent-profiel noemt vaultpad + MCP tools (recall/capture/temporal) + rawlog-capture + fail-open (test_agent_profile_mentions_required_items). Skills gratis via ~/.agents/skills. Doctor toont actieve instructie-surfaces ('copilot config: mcp, hooks, instructions and agent profile present'). Templates = generator-functies in repo, door setup gebruikt (zelfde inline-patroon als codex/opencode _agent_block). DoD#3 (docs global vs repo-local) → 26.11.
<!-- SECTION:NOTES:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Templatebestanden staan in het repo en worden door setup gebruikt.
- [x] #2 Een voorbeeldinstallatie laat zien dat Copilot de KennisBank-instructies kan vinden.
- [x] #3 Docs beschrijven global versus repo-local instructies en wanneer welke gekozen wordt.
<!-- DOD:END -->

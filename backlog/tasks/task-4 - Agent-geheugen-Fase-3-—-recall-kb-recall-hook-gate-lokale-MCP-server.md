---
id: TASK-4
title: Agent-geheugen Fase 3 — recall (kb-recall + hook-gate + lokale MCP-server)
status: To Do
assignee: []
created_date: '2026-06-26 23:22'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies:
  - TASK-3
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
kb-recall query-lib (hybride, beide lagen, current-only, recency-tiebreak) gebruikt door zowel de uitgebreide kb-retrieve hook (gegate op memory_recall) als een nieuwe lokale stdio MCP-server (Cursor/LM Studio/Claude Desktop). MCP-dep (mcp pip) is optioneel + fail-soft: ontbreekt 'ie, dan werkt de hook-recall gewoon door. Geen cloud-bind.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 kb-recall fuseert vector+FTS, beide lagen, filtert status!=current, recency-tiebreak
- [ ] #2 kb-retrieve hook injecteert memory alleen als memory_recall aan (anders enkel wiki, als nu)
- [ ] #3 Lokale stdio MCP-server exposeert recall; mcp-dep ontbreekt -> fail-soft, hook werkt door
- [ ] #4 Geen externe host-calls (no-cloud test)
<!-- AC:END -->

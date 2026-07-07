---
id: TASK-25.6
title: >-
  Temporal Activity Recall - MCP tools voor tijdlijn, weeklog en wat-deed-ik
  recall
status: Done
assignee: []
created_date: '2026-07-07 21:44'
updated_date: '2026-07-07 23:00'
labels:
  - temporal-activity-recall
  - mcp
  - api
  - agents
dependencies:
  - TASK-25.5
parent_task_id: TASK-25
priority: high
ordinal: 33000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Exposeer Temporal Activity Recall via de lokale MCP server zodat agents dezelfde API gebruiken als slash commands.

Nieuwe of uitgebreide MCP tools:
- what_did_i_do(date_or_period: str, topic: optional, project: optional, k/max_events: optional)
- timeline(period: str, topic: optional, project: optional, granularity: optional)
- weeklog(period: optional, project: optional)
- Optional: activity_search(query, period: optional) als generieke escape hatch.

Eisen:
- Tools gebruiken exact dezelfde parser/API als commands.
- Tools geven structured JSON of compacte markdown terug volgens MCP-client bruikbaarheid; kies consistent en documenteer.
- Existing recall/capture blijven backwards compatible.
- MCP startup mag niet afhankelijk worden van Ollama beschikbaarheid; tools mogen bij runtime netjes melden dat semantic topic matching is gedegradeerd.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 kb-mcp.py exposeert temporal tools zonder bestaande recall/capture contracten te breken.
- [x] #2 MCP tools initialiseren ook wanneer kb-activity.db ontbreekt; tool calls geven dan een herstelbare melding.
- [x] #3 MCP list_tools toont recall, capture en de nieuwe temporal tools; setup validator controleert dit als temporal feature actief is.
- [x] #4 Tool output bevat evidence refs en waarschuwingen over degraded semantic matching of stale index.
- [x] #5 Codex/OpenCode agent docs noemen wanneer agents temporal MCP tools moeten gebruiken in plaats van algemene recall.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: kb-mcp.py exposes what_did_i_do, timeline, weeklog and topic_timeline while preserving recall/capture. install-agent-envs.py validates these tools during MCP handshake; Codex MCP validation passed on Kluis.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Unit tests voor tool wrappers met gemockte activity API.
- [x] #2 E2E stdio MCP handshake test initialiseert server en list_tools bevat temporal tools.
- [x] #3 Een tool-call smoke test op fixture-vault retourneert verwachte timeline/weeklog output.
<!-- DOD:END -->

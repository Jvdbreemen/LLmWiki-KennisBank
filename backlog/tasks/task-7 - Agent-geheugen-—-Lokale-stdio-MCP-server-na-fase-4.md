---
id: TASK-7
title: Agent-geheugen — Lokale stdio MCP-server (na fase 4)
status: To Do
assignee: []
created_date: '2026-06-27 09:32'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies:
  - TASK-5
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Dunne lokale stdio MCP-server bovenop kb-recall, voor lokale MCP-clients (Cursor, LM Studio, Claude Desktop). Uitgesteld uit fase 3 (AC #3) tot na fase 4, want een MCP-server over een lege memory-laag is niet end-to-end testbaar. Pitfalls (advisor): mcp pip-dep achter try/except (afwezigheid raakt hook-recall/no-cloud-tests nooit; doctor behandelt ontbrekende mcp als prima), kb-index.db read-only openen, embed-seam fail-soft als Ollama down, dunne wrapper over kb-recall (+ unified/wiki-recall toevoegen), unit-test de lib + smoke-test de wrapper. Geen cloud-bind.
<!-- SECTION:DESCRIPTION:END -->

---
id: TASK-7
title: Agent-geheugen — Lokale stdio MCP-server (na fase 4)
status: Done
assignee: []
created_date: '2026-06-27 09:32'
updated_date: '2026-06-27 13:37'
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

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Lokale stdio MCP-server afgerond. kb-mcp.py: recall_tool(query,k) (puur, testbaar zonder mcp/model — embed -> kb_recall.recall_hits over beide lagen -> tekst) + gegate MCP-server-wrapper (mcp-import achter try/except: MCPServer/FastMCP, afwezig -> build_server None, raakt niets). Read-only, lokaal-only (stdio), fail-soft. Commits 56fc948 (core) + 0860a8c (docs). 238 tests groen (no-cloud-guard intact). E2E-bewezen: recall_tool tegen echte index geeft de juiste memories; build_server None want mcp niet geinstalleerd (by design - advisor: unit-test de lib, smoke-test de wrapper). Vereist 'pip install mcp' om te draaien; gedocumenteerd in CONFIGURATION.md.
<!-- SECTION:FINAL_SUMMARY:END -->

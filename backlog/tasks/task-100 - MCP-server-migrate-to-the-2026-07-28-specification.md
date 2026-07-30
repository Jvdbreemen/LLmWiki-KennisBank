---
id: TASK-100
title: 'MCP server: migrate to the 2026-07-28 specification'
status: In Progress
assignee: []
created_date: '2026-07-29 21:47'
labels: []
dependencies: []
ordinal: 103700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The 2026-07-28 MCP revision makes the protocol stateless: the initialize handshake is gone, server/discover becomes a MUST for servers, resultType is required on every result, and ttlMs/cacheScope are required on CacheableResult types (tools/list, resources/list, resources/read, prompts/list, resources/templates/list). Per-request _meta carries io.modelcontextprotocol/protocolVersion and clientCapabilities. All session/SSE/header breakage is HTTP-only and does not touch our stdio server. Nothing is broken today: the spec's stdio backward-compatibility rule makes modern clients fall back to initialize when server/discover fails, so this is a planned migration rather than a repair. Deliverable of this task: docs/superpowers/plans/mcp-2026-07-28-migration.md with the route comparison (SDK v2 bump versus a stdlib transport versus hybrid), the step-by-step migration, and the tool-surface proposal. Context: we pin mcp==1.28.1; mcp 2.0.0 shipped 2026-07-28 (same day as the spec, no patch releases yet); kb-mcp.py already carries a speculative, unverified v2 import at lines 41-49; and today, without the mcp package, the MCP surface does not exist at all.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Plan document written with route comparison and a plain recommendation on minimal dependency versus minimal code
- [ ] #2 Every normative claim in the plan carries a primary-source URL
- [ ] #3 Tool-surface proposal separates add-now from defer, with reasons
- [ ] #4 Open questions listed with the cheapest experiment that closes each
<!-- AC:END -->

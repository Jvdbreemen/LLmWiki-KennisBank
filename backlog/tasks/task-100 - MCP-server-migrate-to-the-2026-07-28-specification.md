---
id: TASK-100
title: 'MCP server: migrate to the 2026-07-28 specification'
status: Done
assignee: []
created_date: '2026-07-29 21:47'
updated_date: '2026-08-03 21:10'
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
- [x] #1 Plan document written with route comparison and a plain recommendation on minimal dependency versus minimal code
- [x] #2 Every normative claim in the plan carries a primary-source URL
- [x] #3 Tool-surface proposal separates add-now from defer, with reasons
- [x] #4 Open questions listed with the cheapest experiment that closes each
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Verified against the delivered plan document rather than assumed. §4 gives the full route comparison (A/B/C/D) with a plain recommendation (C, Hybrid) and a measured refutation of route B (AC#1). 19 primary-source URLs cited, including the versioning spec for the era-as-date-compare refutation and the tools spec for input validation (AC#2). §6's "Zero new tools" finding plus the D7 decision-log entry name three candidates (read_note, orientation, capture provenance) and defer each with a stated trigger — the add-now/defer split the AC asks for (AC#3). §9 lists five open questions (Q1-Q5) plus a risk (R1), each with its cheapest closing experiment (AC#4).

One finding worth carrying forward: Q1's own measurement (all inspectable clients pre-2026-07-28, checked 2026-07-30) is the primary-source evidence that TASK-110's gate is not met today, and D7's "capture provenance deferred, trigger not fired" directly supersedes TASK-107 as currently scoped. Neither should be executed as written without that context.
<!-- SECTION:FINAL_SUMMARY:END -->

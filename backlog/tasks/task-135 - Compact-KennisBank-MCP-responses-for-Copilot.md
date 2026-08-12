---
id: TASK-135
title: Compact KennisBank MCP responses for Copilot
status: In Progress
assignee: []
created_date: '2026-08-09 20:51'
updated_date: '2026-08-09 20:52'
labels:
  - mcp
  - copilot
  - ux
dependencies: []
priority: medium
ordinal: 130700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make the managed Copilot integration and KennisBank MCP tools return compact, purpose-specific content so the Copilot CLI does not render duplicated, oversized raw JSON payloads for normal recall and activity queries. Preserve complete structured data when consumers explicitly need it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Normal Copilot recall and temporal-activity calls return concise human-readable content without duplicated full JSON payloads.
- [ ] #2 Machine-readable structured result fields remain available where required by supported clients and tests.
- [ ] #3 The managed Copilot instructions direct the agent to request narrow, concise results.
- [ ] #4 Regression tests cover compact result shaping and existing MCP wire behavior.
<!-- AC:END -->

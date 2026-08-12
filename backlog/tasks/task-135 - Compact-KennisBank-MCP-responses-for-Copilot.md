---
id: TASK-135
title: Compact KennisBank MCP responses for Copilot
status: Done
assignee: []
created_date: '2026-08-09 20:51'
updated_date: '2026-08-12 16:13'
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
- [x] #1 Normal Copilot recall and temporal-activity calls return concise human-readable content without duplicated full JSON payloads.
- [x] #2 Machine-readable structured result fields remain available where required by supported clients and tests.
- [x] #3 The managed Copilot instructions direct the agent to request narrow, concise results.
- [x] #4 Regression tests cover compact result shaping and existing MCP wire behavior.
<!-- AC:END -->



## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed in PR #104 (merge 33458d7) and confirmed on origin/main: the managed Copilot registration sets KENNISBANK_MCP_COMPACT_OUTPUT=1 and the temporal/recall tools return the compact shape. CI green on that merge.
<!-- SECTION:NOTES:END -->

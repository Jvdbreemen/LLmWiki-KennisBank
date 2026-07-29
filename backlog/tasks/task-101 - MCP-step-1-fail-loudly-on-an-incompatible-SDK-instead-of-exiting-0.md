---
id: TASK-101
title: 'MCP step 1: fail loudly on an incompatible SDK instead of exiting 0'
status: To Do
assignee: []
created_date: '2026-07-29 22:45'
labels: []
dependencies:
  - TASK-100
ordinal: 104700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan: docs/superpowers/plans/mcp-2026-07-28-migration.md §3.2 step 1. This is the live bug, not a future one: pip install mcp now resolves to 2.x where mcp.server.fastmcp no longer exists, so the import block at kb-mcp.py:41-49 collapses to MCPServer=None, build_server() returns None at :264-265, main() writes an advisory line and returns 0 at :336-339, and the blanket except Exception at :344-348 exits 0 as well. Result: "started fine, provided nothing" is indistinguishable from success, and a freshly installed vault has a silently dead MCP surface. Record WHY the import failed, keep exit 0 only for a genuinely absent package, return non-zero when the package is present but incompatible (naming the exception type and message on stderr, which the stdio spec sanctions as the logging channel), and narrow the blanket catch so it stops masking startup failures. No wire behaviour changes, so no client is affected.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Absent mcp package: exit 0 with a message naming the missing package
- [ ] #2 Present but incompatible SDK: non-zero exit naming the actual exception type and message on stderr
- [ ] #3 The blanket except Exception that exits 0 no longer masks startup failures; KeyboardInterrupt/BrokenPipeError keep a clean path
- [ ] #4 Unit tests simulate both failure modes and assert the two paths differ
- [ ] #5 pytest suite green
<!-- AC:END -->

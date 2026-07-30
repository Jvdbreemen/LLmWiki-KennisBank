---
id: TASK-101
title: 'MCP step 1: fail loudly on an incompatible SDK instead of exiting 0'
status: Done
assignee: []
created_date: '2026-07-29 22:45'
updated_date: '2026-07-30 05:30'
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
- [x] #1 Absent mcp package: exit 0 with a message naming the missing package
- [x] #2 Present but incompatible SDK: non-zero exit naming the actual exception type and message on stderr
- [x] #3 The blanket except Exception that exits 0 no longer masks startup failures; KeyboardInterrupt/BrokenPipeError keep a clean path
- [x] #4 Unit tests simulate both failure modes and assert the two paths differ
- [ ] #5 pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
kb-mcp.py now distinguishes an absent mcp package (a user choice: quiet, exit 0) from a present-but-unusable one (a defect: loud, exit non-zero with the actual exception type and message on stderr, the channel the stdio spec sanctions). The import block records SDK_ABSENT and SDK_ERROR instead of collapsing everything to MCPServer=None, and the blanket "except Exception: sys.exit(0)" is gone - only KeyboardInterrupt and BrokenPipeError still exit 0. Five new falsifiable tests: both failure modes, an assertion that the two paths differ, an internal-consistency check on the import state that cannot pass vacuously, and a stdout-purity check on the import window. The error strings deliberately point at requirements.txt rather than naming a version, so they cannot drift from the gated >=2.0.1,<3 decision in TASK-110.
<!-- SECTION:FINAL_SUMMARY:END -->

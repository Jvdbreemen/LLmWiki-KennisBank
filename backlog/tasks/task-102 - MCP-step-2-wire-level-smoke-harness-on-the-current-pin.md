---
id: TASK-102
title: 'MCP step 2: wire-level smoke harness on the current pin'
status: To Do
assignee: []
created_date: '2026-07-29 22:46'
labels: []
dependencies:
  - TASK-101
ordinal: 105700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan §3.2 step 2. Build the instrument BEFORE bumping the dependency, so that a failure in step 3 is unambiguously caused by step 3. A test spawns kb-mcp.py as a subprocess and speaks newline-delimited JSON-RPC over its stdin/stdout, skipping cleanly when mcp is not importable. Against the currently pinned 1.28.1 it asserts the legacy era: initialize, then tools/list returning exactly the eight expected tool names, then tools/call on recall returning text. Plus a stdout-hygiene assertion, because the stdio spec requires that a server MUST NOT write anything to stdout that is not a valid MCP message, and our module-import window at kb-mcp.py:51-65 is ours to keep clean (SDK v2 diverts stdout only while serving). This step also replaces a blind guard: tests/test_kb_mcp.py:69-74 branches on MCPServer is None and passes either way, which is the PR#54 pattern the repo has a standing rule against.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Subprocess harness speaks newline-delimited JSON-RPC to kb-mcp.py and skips cleanly when mcp is absent
- [ ] #2 Legacy era asserted on mcp==1.28.1: initialize, tools/list returns the eight expected names, tools/call on recall returns text
- [ ] #3 stdout-hygiene assertion fails when a deliberate print() is injected into a module imported at kb-mcp.py:51-65
- [ ] #4 The blind guard at tests/test_kb_mcp.py:69-74 is replaced by an assertion that cannot pass both ways
- [ ] #5 pytest suite green
<!-- AC:END -->

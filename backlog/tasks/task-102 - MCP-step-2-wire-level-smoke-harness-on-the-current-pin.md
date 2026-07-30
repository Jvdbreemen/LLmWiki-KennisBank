---
id: TASK-102
title: 'MCP step 2: wire-level smoke harness on the current pin'
status: Done
assignee: []
created_date: '2026-07-29 22:46'
updated_date: '2026-07-30 05:30'
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
- [x] #1 Subprocess harness speaks newline-delimited JSON-RPC to kb-mcp.py and skips cleanly when mcp is absent
- [x] #2 Legacy era asserted on mcp==1.28.1: initialize, tools/list returns the eight expected names, tools/call on recall returns text
- [x] #3 stdout-hygiene assertion fails when a deliberate print() is injected into a module imported at kb-mcp.py:51-65
- [x] #4 The blind guard at tests/test_kb_mcp.py:69-74 is replaced by an assertion that cannot pass both ways
- [x] #5 pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
tests/test_kb_mcp_wire.py spawns kb-mcp.py as a subprocess and speaks real newline-delimited JSON-RPC over its stdin/stdout, skipping cleanly when the SDK is unusable. Six tests, all passing against the current pin mcp==1.28.1: legacy initialize succeeds, tools/list returns exactly the eight expected names (the names are a contract in deployed client configs, so a rename fails here), tools/call returns content, annotations arrive on the wire, instructions are advertised in the initialize result, and every line the server writes to stdout parses as JSON-RPC 2.0. review_pending rather than recall drives the call assertion, so the harness needs no Ollama and stays CI-safe. The blind guard at tests/test_kb_mcp.py:69 - which branched on "MCPServer is None" and passed in both branches - is replaced by a stub-SDK test that asserts the exact annotation set per tool and can genuinely fail.
<!-- SECTION:FINAL_SUMMARY:END -->

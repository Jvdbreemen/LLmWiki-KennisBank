---
id: TASK-105
title: 'MCP: tool annotations and instructions= on the current pin'
status: Done
assignee: []
created_date: '2026-07-29 22:48'
updated_date: '2026-07-30 05:30'
labels: []
dependencies:
  - TASK-103
ordinal: 108700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan §3.2 step 5. Pass instructions=INSTRUCTIONS_TEXT to the MCPServer constructor at kb-mcp.py:266 IN ADDITION to keeping the kennisbank://instructions resource at :324-330 — the DiscoverResult schema carries an optional instructions field, which is a protocol-level place to deliver the pull-nudge to clients that do not support resources (GitHub Copilot being the documented case). Add annotations= to the eight @srv.tool() calls: recall, review_pending and the four activity tools are readOnlyHint=True; capture and review_decide are writers. Both additions must be guarded the same way the existing .resource() call is (try/except), because not every SDK version accepts these keyword arguments and a TypeError at import time would take the whole server down. Honest open point: whether a client actually surfaces DiscoverResult.instructions to the model is unverified, so this is cheap insurance rather than a proven win.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 instructions= passed to the constructor, guarded so an SDK that rejects it does not break startup
- [x] #2 The kennisbank://instructions resource is retained alongside it
- [x] #3 annotations= set on all eight tools with correct readOnlyHint values, guarded the same way
- [x] #4 Test asserts the server still builds and lists eight tools when the guarded kwargs are rejected (simulated TypeError)
- [x] #5 pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
All eight tools now carry annotations, and instructions= is passed to the constructor with a TypeError guard so an SDK lacking the kwarg cannot take the server down. Both were proven on the wire, not just in source: tests/test_kb_mcp_wire.py asserts readOnlyHint arrives for the six read-only tools, destructiveHint for review_decide, and the instructions text in the initialize result. Evidence captured in docs/superpowers/plans/mcp-2026-07-28-evidence.md against mcp 1.28.1 / Python 3.14.2. This was the only MEASURED present-day defect on the surface: Claude Code derives isReadOnly() and isConcurrencySafe() from annotations.readOnlyHint and defaults both to false when annotations are absent, so six read-only retrieval tools were prompting for confirmation and serialising on the hot path. Annotation values are earned rather than guessed: capture gets destructiveHint=false because it only ever creates a new unverified file, review_decide gets destructiveHint=true because the status flip is refused afterwards by the write path. The label goes in annotations.title rather than the title= kwarg, which older SDKs reject. The pull-nudge now has three carriers (protocol field, resource, copilot-instructions block) because none reaches every client alone. Honest limit: annotations are hints, and DiscoverResult.instructions is unreachable in every client inspected today.
<!-- SECTION:FINAL_SUMMARY:END -->

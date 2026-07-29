---
id: TASK-105
title: 'MCP step 5: server instructions and tool annotations, both guarded'
status: To Do
assignee: []
created_date: '2026-07-29 22:48'
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
- [ ] #1 instructions= passed to the constructor, guarded so an SDK that rejects it does not break startup
- [ ] #2 The kennisbank://instructions resource is retained alongside it
- [ ] #3 annotations= set on all eight tools with correct readOnlyHint values, guarded the same way
- [ ] #4 Test asserts the server still builds and lists eight tools when the guarded kwargs are rejected (simulated TypeError)
- [ ] #5 pytest suite green
<!-- AC:END -->

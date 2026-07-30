---
id: TASK-107
title: 'MCP step 7: capture provenance parameters'
status: To Do
assignee: []
created_date: '2026-07-29 22:50'
labels: []
dependencies:
  - TASK-103
ordinal: 110700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan §3.2 step 7. Add optional source_session and tags parameters to the capture tool. _memory.render() already accepts both, so this is surfacing an existing capability rather than building one. Value: an agent-written memory currently lands without provenance, which makes later human review harder than it needs to be — the reviewer cannot see which session produced the claim. Both parameters stay optional so every existing caller keeps working unchanged. The memory still lands as unverified/agent: this step does not touch the rule that the human is the update authority.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 capture accepts optional source_session and tags, both defaulting to no-op
- [ ] #2 Existing capture calls without the new parameters behave byte-identically
- [ ] #3 Captured memory carries the provenance in its frontmatter when supplied
- [ ] #4 Memory still lands as unverified/agent
- [ ] #5 pytest suite green
<!-- AC:END -->

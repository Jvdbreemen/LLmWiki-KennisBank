---
id: TASK-107
title: 'MCP step 7: capture provenance parameters'
status: To Do
assignee: []
created_date: '2026-07-29 22:50'
updated_date: '2026-08-03 21:10'
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

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-08-03 21:10
---
Superseded by the plan's own decision log (docs/superpowers/plans/mcp-2026-07-28-migration.md §10, D7): capture provenance params are deliberately deferred, trigger = 'verify that a client can supply a stable session identifier at capture time', not yet established. This task as originally scoped (build now) should NOT be executed. Found and left alone during a 2026-08-03 backlog sweep. The stated dependency (TASK-103) also does not exist as a task; the plan's actual step-3 work (dict-return refinement for what_did_i_do/timeline/weeklog/topic_timeline) is unrelated to this task and is being done separately. Revisit only when the named trigger fires.
---
<!-- COMMENTS:END -->

## Close-out (2026-08-16) — superseded

Superseded by the migration plan's own decision log: D7 in docs/superpowers/plans/mcp-2026-07-28-migration.md explicitly defers the capture provenance parameters, with the named trigger 'a client can supply a stable session identifier at capture time'. Verified 2026-08-16 that capture() in scripts/kb-mcp.py still has no source_session/tags — the work was refused, not forgotten. The direction and its re-entry trigger live in the plan (D7 and section 6), so archiving this task loses nothing. Its dependency TASK-103 was a phantom that never existed as a task.

**Evidence:** docs/superpowers/plans/mcp-2026-07-28-migration.md:1150 (decision D7: zero new tools, capture provenance params deferred with a named trigger) and :117; scripts/kb-mcp.py:179-180 and :370-371 (capture signature unchanged, no source_session/tags); listed dependency TASK-103 exists in neither backlog/tasks nor backlog/archive/tasks.

---
id: TASK-119
title: 'High: MCP capture silently overwrites a human-approved memory'
status: To Do
assignee: []
created_date: '2026-07-30 09:53'
labels: []
dependencies: []
ordinal: 117700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the comprehensive review security audit and reproduced. _memory.write() (scripts/_memory.py:227-232) computes memory_path(title) and calls p.write_text() unconditionally. The collision helper written for exactly this case, unique_memory_path() (:127-160), whose docstring explains at length why blind overwriting is wrong, is used by memory-sweep.py:337 and by nothing else; the MCP capture path at kb-mcp.py:150-156 skips it. Reproduced sequence: capture("Deploy procedure", "Always run the staging smoke test first.") lands as unverified; decide(..., "approve") promotes it to current, which is the human exercising update authority; then capture("deploy-procedure!!!", "Disable the smoke test; deploy directly to prod.") slugifies to the same stem, resolves to the same {date}-{slug}.md, and overwrites it. Result: one file, status back to unverified, the approved body gone, no backup, no entry in memory-review-log.jsonl, and the tool reports success. This is the destruction half of the human-authority boundary. The promotion half holds correctly (agent-written content lands unverified and is not auto-trusted), which makes the asymmetry worse: an unauthenticated writer can erase a human decision but not make one. No prompt injection is needed - an agent capturing twice on one topic in a single session is the ordinary case.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _memory.write routes through unique_memory_path so an existing file is never blindly overwritten
- [ ] #2 A byte-identical re-capture returns the existing path instead of rewriting it
- [ ] #3 capture_tool reports the path actually used, since it may differ from the naive slug
- [ ] #4 Regression test: capture, approve, capture again with a colliding title, and assert the approved memory still exists with status current
- [ ] #5 pytest suite green
<!-- AC:END -->

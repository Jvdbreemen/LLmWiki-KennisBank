---
id: TASK-119
title: 'High: MCP capture silently overwrites a human-approved memory'
status: Done
assignee:
  - '@claude'
created_date: '2026-07-30 09:53'
updated_date: '2026-07-30 20:36'
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
- [x] #1 _memory.write routes through unique_memory_path so an existing file is never blindly overwritten
- [x] #2 A byte-identical re-capture returns the existing path instead of rewriting it
- [x] #3 capture_tool reports the path actually used, since it may differ from the naive slug
- [x] #4 Regression test: capture, approve, capture again with a colliding title, and assert the approved memory still exists with status current
- [x] #5 pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
_memory.write() computed memory_path(title) and wrote unconditionally, so a second capture whose title slugified to the same stem overwrote the first file. If a human had approved that memory in between, the approval was destroyed: status back to unverified, the approved body gone, no backup, no entry in memory-review-log.jsonl, and the tool returned success. The collision helper written for exactly this case, unique_memory_path(), was used by memory-sweep.py and by nothing else.

Fix: a new write_capture() routes through unique_memory_path and returns (path, existed_already). Identical content returns the existing path and writes nothing; a different body on an occupied slug gets -2/-3 as unique_memory_path already did. write() stays as a thin wrapper returning only the path, so the three test fixtures and memory-sweep are untouched.

The MCP capture path now uses write_capture and reports honestly. It previously said 'Vastgelegd' for a byte-identical re-capture in which nothing was written: a tool claiming success for work that did not happen, which is the same family of defect as the documentation errors fixed in v0.26.1. It now distinguishes the two outcomes.

Proven against the old behaviour rather than assumed. Replaying the exact sequence from the task with the original implementation: status flips from current back to unverified, the approved text is gone, one file on disk. With the fix: status stays current, the approved text is intact, and the hostile capture lands beside it as a second file.

Three regression tests. The first asserts its own premise before testing anything, that both titles really do resolve to the same slug, because without the collision the rest of the test proves nothing. The second covers the byte-identical re-capture returning the existing path with no -2 sibling. The third pins write()'s signature for existing callers.

Full suite: 1122 passed, 2 skipped, zero failures. Note that the first validation run showed 2 failures in test_setup_deploy.py, unrelated to this change and diagnosed as TASK-116, which is fixed in the same branch; the flake is exactly what made the first run unable to confirm this one.
<!-- SECTION:FINAL_SUMMARY:END -->

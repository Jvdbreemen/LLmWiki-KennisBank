---
id: TASK-233
title: Split feature flags and lock the public MCP and CLI policy
status: To Do
assignee: []
created_date: '2026-09-04 00:00'
labels:
  - feature-flags
  - mcp
  - cli
  - safety
dependencies:
  - TASK-231
  - TASK-232
ordinal: 177200
---

## Description

Replace coarse experimental toggles with independent capture, projection, and
explicit-read flags. Make the v1 policy visible and identical in CLI and MCP.
Legacy true values must not silently enable the new semantics.

## Planned Files

- update `scripts/_settings.py`
- update `scripts/kb-mcp.py`
- update `scripts/kb-source-recall.py` and `scripts/kb-experience-recall.py`
- update `commands/kennisbank/settings.md` and recall commands
- extend MCP wire and settings tests

## Acceptance Criteria

- [ ] #1 Add default-off `experience_capture`, `experience_projection`, `experience_explicit_recall`, and `source_explicit_recall`
- [ ] #2 Legacy `source_recall`/`experience_recall` values produce migration guidance and never auto-enable new flags
- [ ] #3 MCP exposes explicit experience recall and source search/hydration with bounded arguments and read-only annotations
- [ ] #4 Advisory, automatic fallback, ranking, promotion, and hook-injection modes are absent or return policy-disabled
- [ ] #5 CLI and MCP return the same status labels and fail-open semantics
- [ ] #6 Settings migration preserves unknown keys and corrupt-file refusal behavior
- [ ] #7 Contract, MCP wire, command, and settings tests pass

## Evidence

Record the public tool list, settings before/after examples, and negative route
test results.

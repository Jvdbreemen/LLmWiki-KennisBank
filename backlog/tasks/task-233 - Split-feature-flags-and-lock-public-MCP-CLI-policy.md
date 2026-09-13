---
id: TASK-233
title: Split feature flags and lock the public MCP and CLI policy
status: Done
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

- [x] #1 Add default-off `experience_capture`, `experience_projection`, `experience_explicit_recall`, and `source_explicit_recall`
- [x] #2 Legacy `source_recall`/`experience_recall` values produce migration guidance and never auto-enable new flags
- [x] #3 MCP exposes explicit experience recall and source search/hydration with bounded arguments and read-only annotations
- [x] #4 Advisory, automatic fallback, ranking, promotion, and hook-injection modes are absent or return policy-disabled
- [x] #5 CLI and MCP return the same status labels and fail-open semantics
- [x] #6 Settings migration preserves unknown keys and corrupt-file refusal behavior
- [x] #7 Contract, MCP wire, command, and settings tests pass

## Evidence

Record the public tool list, settings before/after examples, and negative route
test results.

- Settings/policy/MCP-wire/CLI/retrieval suite: 96 passed.
- Targeted fresh-vault setup default test: passed.
- Legacy-true migration test: all four new flags remain false, unknown and
  legacy keys are preserved, and both legacy keys emit actionable guidance.
- Negative mode tests: CLI and MCP both return `policy_disabled` without
  invoking the optional recall backend.
- Public MCP list remains ten tools; source and experience tools are read-only
  and closed-world, with source `k<=20` and experience `k<=3`.
- Detailed record: `docs/research/explicit-recall-policy-evidence-2026-09-06.md`.

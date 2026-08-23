---
id: TASK-208
title: 'C4 follow-up: five corrections the documentation pass recorded but did not fix'
status: Done
assignee: []
created_date: '2026-08-19 20:00'
labels:
  - documentation
  - follow-up
dependencies: []
type: docs
ordinal: 173700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The 2026-08-18 C4 documentation pass (PR #142) recorded gaps rather than fixing them, per the honesty rule. Five are small, mechanical, and now get fixed:

1. The old C4-Documentation/ in the repo root (32 files, pre-docs/ era) sits beside the new set in docs/C4-Documentation/. Remove the old set; docs/ is the maintained one.
2. Component docs say "six MCP tools"; scripts/kb-mcp.py registers eight (recall, capture, review_pending, review_decide, what_did_i_do, timeline, weeklog, topic_timeline). Correct every occurrence.
3. docs/C4-Documentation/c4-code-root.md claims doctor.sh lives in the repo root; it is scripts/doctor.sh.
4. kb-usage.db is referenced across component docs without a documented owner or schema. Add the owner (which module writes it) and schema to the component doc that covers usage telemetry.
5. Specs reference a repo-level .graphifyignore that does not exist in the repository (the deployed vault has one). Either add the file or correct the spec references to say it is a vault artifact.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Old root C4-Documentation/ removed; docs/C4-Documentation/ is the only set
- [x] #2 No component doc claims six MCP tools; counts and tool lists match scripts/kb-mcp.py (eight)
- [x] #3 c4-code-root.md locates doctor.sh at scripts/doctor.sh
- [x] #4 kb-usage.db has a documented owner and schema in the C4 set, verified against the code
- [x] #5 The .graphifyignore references are consistent with reality (file added or spec corrected)
- [x] #6 Documentation test subset is green
<!-- AC:END -->

## Close-out (2026-08-19)

Two of the five premises did not survive verification and cost nothing to fix:
c4-code-root.md already located doctor.sh at scripts/ everywhere, and
graphifyignore.example exists and is deployed by setup.sh:207 — both "gaps"
were errors in the PR #142 description, not in the documents (AC#3/#5 hold
as already-true).

The six-vs-eight question resolved differently than assumed: the install gate
(install-agent-envs.py:854) genuinely checks SIX tool names; the server exposes
EIGHT. Docs now distinguish gate from surface instead of replacing one count
with the other. The root C4-Documentation/ set is removed except
c4-code-github-workflows.md, which moved to docs/ as -baseline.md because a
live ci.yml comment cites its section 4 (TASK-123 runtime baselines).
kb-usage.db owner (_usage.py) and its three-table schema are documented in the
Retrieval component doc, verified against source. Doc lints: 47 passed.

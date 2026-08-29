---
id: TASK-221
title: Promote repeatedly proven experiences to procedures and skills
status: In Progress
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-29 00:00'
labels:
  - experience-memory
  - procedures
  - skills
  - human-gate
dependencies:
  - TASK-175
  - TASK-177
  - TASK-220
ordinal: 176000
---

## Description

Add the final promotion path from experience to executable guidance. A single
successful session is not enough. Promotion requires repeated evidence in a
defined scope, concrete steps, source links, no unresolved contradiction, and
the evaluation gates from TASK-220.

New skills remain proposals requiring owner approval. Existing skills may be
updated only through the controlled evolution path from TASK-177, with a
grounded verifier, diff, evidence references, rollback, and audit record.

The first implementation should produce a proposal report rather than mutate
the skills directory automatically. It must show the supporting experiences,
failures, applicability conditions, and reasons for promotion or rejection.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A deterministic promotion report identifies candidate procedures and lists all supporting experiences and source evidence
- [x] #2 Promotion thresholds include repeated evidence, scope, recency/validity, contradiction checks, and outcome quality
- [x] #3 A single success, weak proxy, or unverified LLM lesson cannot create or alter a skill
- [x] #4 New skill creation is proposal-only and human-approved
- [ ] #5 Existing skill evolution has a grounded verification result, reviewable diff, rollback path, and audit entry
- [x] #6 Rejected or retracted experiences cannot continue to drive a procedure without an explicit override
- [x] #7 Tests cover insufficient evidence, conflicting evidence, repeated success, repeated failure, and owner rejection
<!-- AC:END -->

## Evidence

- `scripts/_experience_promote.py` now applies repeated-support, concrete-action,
  scope, validity, recency, contradiction, and outcome-quality checks, and
  emits deterministic proposal ids with supporting experience/source/outcome
  references.
- `scripts/kb-experience-proposal.py` and its command document make the path
  proposal-only and offline.
- Focused evidence: 6 promotion tests pass, including stale/retracted,
  conflicting, repeated, and insufficient-evidence cases.

Existing skill evolution remains open under TASK-177: no skill mutation is
authorized by this feature branch. TASK-220 now rejects experience rollout on
a measured 0.20 false-warning rate, and consolidation found zero repeated
lessons with sufficient support. AC #5 is therefore blocked by evidence and
owner-gated dependencies rather than silently waived.

---
id: TASK-230
title: Harden experience extraction, validation, and human review
status: To Do
assignee: []
created_date: '2026-09-04 00:00'
labels:
  - experience-memory
  - validation
  - human-review
  - safety
dependencies:
  - TASK-228
  - TASK-229
ordinal: 176900
---

## Description

Make extraction candidate-only and separate status, evidence state, and review
state. Add a review operation that records an immutable owner decision. A
validated record must have exact evidence, a task-consistent known outcome,
non-contradictory semantics, version stamps, and an accepted review.

## Planned Files

- update `scripts/_experience_extract.py`
- update `scripts/_experience.py`
- extend rebuild/review CLI or add `scripts/kb-experience-review.py`
- add/update command documentation and tests

## Acceptance Criteria

- [ ] #1 Extraction always emits candidate/unreviewed regardless of model confidence
- [ ] #2 Evidence state and review state are independent, explicit schema fields
- [ ] #3 Validation checks every SourceRef and OutcomeRef plus session/task consistency
- [ ] #4 Attempt, resolution, and final outcome states remain separate
- [ ] #5 Unknown, missing, stale, contradictory, rejected, superseded, and retracted records cannot enter the production projection
- [ ] #6 Review writes an append-only decision with actor, timestamp, reason, schema, and target content hash
- [ ] #7 Re-extraction invalidates review when material lesson/evidence content changes
- [ ] #8 Focused validation and lifecycle tests pass with zero candidate leakage

## Evidence

Record transition matrices, focused tests, and one synthetic changed-content
review invalidation example.

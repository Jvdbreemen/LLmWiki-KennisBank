---
id: TASK-217
title: Add an append-only experience event model and derived store
status: Done
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-26 00:00'
labels:
  - experience-memory
  - event-log
  - provenance
  - lifecycle
dependencies:
  - TASK-212
ordinal: 175600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create the durable experience representation. Preserve immutable, typed events
for task context, attempt, observation, test result, commit, failure, fix,
decision, and user feedback. Build derived experience records from these events
without overwriting the event history.

An experience record must link to the raw transcript/source passage, outcome
evidence, exposed memories, and any resulting procedure or skill. It must
support success, failure, partial success, mixed outcomes, and unknown outcomes.
Failure experiences are first-class because they can prevent repeated dead ends.

The store must support candidate, validated, superseded, and retracted states.
Superseding a lesson must not delete the underlying event or source evidence.
Schema and extractor versions must be recorded so records can be re-derived
after a prompt/model change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Typed experience events are append-only, inspectable, versioned, and linked to source/session/task identities
- [x] #2 Derived records contain situation, goal, approach, action, observed result, lesson, applicability, outcome, evidence, confidence, and attribution limits
- [x] #3 Both successful and failed attempts are retained and queryable
- [x] #4 Candidate, validated, superseded, retracted, and unknown states have deterministic transition rules
- [x] #5 Rebuilding derived experience records from the event log is idempotent and does not mutate raw evidence
- [x] #6 Missing or contradictory evidence prevents validation rather than creating a confident lesson
- [x] #7 Tests cover duplicate events, partial sessions, retractions, supersession, schema migration, and provenance failure
<!-- AC:END -->

## Evidence

- `scripts/_experience.py` validates event types, supports `partial` outcomes,
  records schema versions, migrates derived-link columns, and preserves
  exposure/procedure/skill references.
- `scripts/_experience_extract.py` derives records idempotently and forces
  contradictory success/failure evidence to `mixed` plus `candidate` rather
  than silently validating it.
- Focused evidence: 24 experience/store/recall/CLI tests pass; the smaller
  store/extractor/promotion selection passes 15 tests.

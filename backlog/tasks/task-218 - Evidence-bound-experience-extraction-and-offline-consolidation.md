---
id: TASK-218
title: Extract and consolidate experience records with evidence-bound gates
status: Done
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-29 00:00'
labels:
  - experience-memory
  - extraction
  - consolidation
  - dead-ends
dependencies:
  - TASK-172
  - TASK-214
  - TASK-216
  - TASK-217
ordinal: 175700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Build the offline extractor that turns raw sessions, source evidence, and
outcome records into candidate experiences. It may use the local LLM to propose
structured summaries, but every proposition must cite source spans and outcome
evidence. Unsupported model statements remain unverified.

Explicitly measure whether dead ends survive extraction, as required by
TASK-172. Capture both:

- enabling lessons: what worked, under which conditions;
- preventative lessons: what failed, why it failed, and what to avoid.

Consolidation must be periodic or threshold-triggered, not an unbounded
continuous rewrite. It may merge repeated experiences into a higher-level
strategy only when the evidence is sufficiently similar and non-contradictory.
The original episodes remain available for source recall.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The extractor produces schema-valid candidate experiences with source and outcome references
- [x] #2 TASK-172 reports the observed survival rate of dead ends and records the decision to preserve, change, or reject the extraction prompt
- [x] #3 Success, failure, mixed, and unknown episodes are all represented; failure is not discarded as irrelevant intermediate work
- [x] #4 No experience can become validated without sufficient source/evidence links and an explicit confidence/uncertainty state
- [x] #5 Consolidation is offline, bounded, versioned, idempotent, and reversible
- [x] #6 Contradictory experiences remain distinguishable by scope/time rather than being silently averaged
- [x] #7 Model timeout, missing source, malformed output, and partial extraction fail open without losing the raw event
- [x] #8 Fixture tests cover unsupported lessons, duplicate experiences, repeated failures, and valid multi-level lessons
<!-- AC:END -->

## Evidence

- `scripts/_experience_extract.py` retains failure and partial outcomes,
  keeps missing/unsupported evidence as candidates, and turns contradictory
  success/failure evidence into an unvalidated mixed record.
- Bounded consolidation produces deterministic, reversible proposals and does
  not mutate source records or the event log.
- Focused evidence: 6 extractor tests pass, including dead-end survival
  measurement and idempotent consolidation; broader experience regression is
  24 tests green.
- The private reviewed projection contains 22 failure-labelled episodes. All
  22 retained an evidence-bound lesson: survival 1.00, lost 0, decision
  `preserve`. This proves lossless projection of the reviewed records, not
  independent LLM extraction quality. Consolidation proposed zero shared
  lessons, remained reversible, and performed no mutation.

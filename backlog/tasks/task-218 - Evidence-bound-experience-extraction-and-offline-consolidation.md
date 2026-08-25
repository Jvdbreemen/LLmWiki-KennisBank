---
id: TASK-218
title: Extract and consolidate experience records with evidence-bound gates
status: To Do
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-25 00:00'
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
- [ ] #1 The extractor produces schema-valid candidate experiences with source and outcome references
- [ ] #2 TASK-172 reports the observed survival rate of dead ends and records the decision to preserve, change, or reject the extraction prompt
- [ ] #3 Success, failure, mixed, and unknown episodes are all represented; failure is not discarded as irrelevant intermediate work
- [ ] #4 No experience can become validated without sufficient source/evidence links and an explicit confidence/uncertainty state
- [ ] #5 Consolidation is offline, bounded, versioned, idempotent, and reversible
- [ ] #6 Contradictory experiences remain distinguishable by scope/time rather than being silently averaged
- [ ] #7 Model timeout, missing source, malformed output, and partial extraction fail open without losing the raw event
- [ ] #8 Fixture tests cover unsupported lessons, duplicate experiences, repeated failures, and valid multi-level lessons
<!-- AC:END -->


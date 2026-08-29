---
id: TASK-219
title: Add gated experience recall and advisory failure prevention
status: Done
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-29 00:00'
labels:
  - experience-memory
  - retrieval
  - failure-prevention
  - safety
dependencies:
  - TASK-215
  - TASK-218
ordinal: 175800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Expose validated or explicitly labelled candidate experiences through a
separate, bounded recall route. Select it for questions such as "what worked
before?", "what failed?", "what should I avoid?", procedural tasks, and known
failure-pattern matches. Do not inject it into every ordinary fact query.

Results must show whether they are observed experience, validated lesson,
candidate lesson, or raw evidence. A failure-prevention match is advisory: it
warns and provides evidence; it does not block the user or autonomously change
code/configuration.

Keep experience ranking separate from wiki/memory ranking. This task may add
intent routing and per-layer thresholds, but it must not introduce an outcome
boost until TASK-220 has measured that policy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Experience recall has explicit intent and confidence gates with documented routing rules
- [x] #2 Results are bounded, diverse, provenance-labelled, and include applicability scope and outcome state
- [x] #3 A known failed approach can produce an advisory warning with its source evidence and confidence
- [x] #4 Candidate and unknown experiences cannot be presented as validated facts
- [x] #5 Ordinary wiki/memory queries retain current results and latency when experience recall is not selected
- [x] #6 No autonomous code/configuration change, memory overwrite, deletion, or skill creation is triggered
- [x] #7 Tests cover success recall, failure recall, unrelated queries, conflicting experiences, stale experiences, and no-evidence cases
<!-- AC:END -->

## Evidence

- `scripts/kb-experience-recall.py` keeps explicit intent gates and labels
  validated results as either `validated_experience` or `failure_advisory`,
  including evidence-bound confidence metadata.
- Failure warnings remain advisory and the gateway never writes memories,
  code, configuration, or skills.
- Focused evidence: 10 gateway/experience-recall tests pass; the broader
  experience regression selection passed 24 tests.

The reviewed projection measured hybrid hit@3 0.90 versus lexical 0.80,
failure hit@3 0.864, evidence precision 1.00, candidate leakage 0, and explicit
query p95 105.6 ms. The off-route benchmark measured approximately 0.0008 ms
p50/p95 overhead over a no-op baseline.

Implementation acceptance is complete, but rollout is rejected: 2 of 10
abstention probes produced a failure warning (0.20 versus the 0.10 maximum).
The gateway also had a real retrieval bug—labelling `hits` before assignment—
which is now covered by an end-to-end projection test. Threshold calibration
must use a separate development set; this holdout may not be tuned against.

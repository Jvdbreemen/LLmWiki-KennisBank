---
id: TASK-219
title: Add gated experience recall and advisory failure prevention
status: To Do
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-25 00:00'
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
- [ ] #1 Experience recall has explicit intent and confidence gates with documented routing rules
- [ ] #2 Results are bounded, diverse, provenance-labelled, and include applicability scope and outcome state
- [ ] #3 A known failed approach can produce an advisory warning with its source evidence and confidence
- [ ] #4 Candidate and unknown experiences cannot be presented as validated facts
- [ ] #5 Ordinary wiki/memory queries retain current results and latency when experience recall is not selected
- [ ] #6 No autonomous code/configuration change, memory overwrite, deletion, or skill creation is triggered
- [ ] #7 Tests cover success recall, failure recall, unrelated queries, conflicting experiences, stale experiences, and no-evidence cases
<!-- AC:END -->


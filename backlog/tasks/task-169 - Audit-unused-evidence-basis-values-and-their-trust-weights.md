---
id: TASK-169
title: Audit unused evidence_basis values and their trust weights
status: To Do
assignee: []
created_date: '2026-08-15 11:00'
updated_date: '2026-08-15 11:00'
labels: []
dependencies: []
ordinal: 103000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the field review (docs/research/agent-memory-field-review-and-strategy.md).
A small removal task, paired with TASK-163.

`_memory.EVIDENCE_BASES` has six members: getypt, cc-sessie, audio, import,
autoresearch, agent. Each feeds `_rank.trust_factor()`, so each carries live
ranking weight. If some are never produced in practice, they are dead schema
holding a live multiplier — and dead enum members invite future code to handle
cases that cannot occur, plus tests that pin behaviour nothing exercises.

Count the distribution across the real vault. Delete what is never written, or
document why it is retained (a value reserved for a capture route that is
genuinely planned is a different thing from one nobody remembers adding).

Note the interaction with TASK-161: if `observer` lands, part of what
`evidence_basis` is doing today — distinguishing which route produced a fragment
— moves to a field that answers it properly. Worth deciding both together rather
than trimming this enum twice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Distribution of evidence_basis values across the real vault, counted and recorded
- [ ] #2 Every value with zero occurrences is either deleted or documented with the route that will produce it
- [ ] #3 trust_factor and its tests updated to match whatever survives
- [ ] #4 Decided together with TASK-161 so the enum is not trimmed twice
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->

---
id: TASK-150
title: 'A superseded memory surfaces nowhere: no human ever sees what was closed'
status: To Do
assignee: []
created_date: '2026-08-12 20:42'
labels:
  - memory
  - review
  - safety
dependencies: []
references:
  - commands/kennisbank/review.md
  - scripts/_memory.py
  - scripts/_maintenance.py
  - docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md
priority: high
ordinal: 144700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Blocks TASK-147 (lowering the supersede threshold) and any move toward automatic self-correction.

The design of the memory layer rests on the claim that superseding is safe because nothing is deleted: the file stays on disk with `superseded_by` and `valid_until`, so a wrong decision is reversible. The first half is true. The second is not, in practice:

- Recall filters on `status: current` (`kb-recall.py`), so a closed memory is never injected again.
- `/kennisbank:review` walks the **unverified** queue only. Its own description says so: "Loop de wachtrij van unverified memories door". A superseded memory appears in no queue.
- Nothing else lists recent supersessions. The sweep heartbeat carries a count (`superseded: n`), not the identities.

So a wrongly closed memory is reversible in theory and invisible in every path a human actually uses. That is functionally the same as deletion, and it is the reason the threshold in TASK-147 should not drop from 0.85 to 0.75 until this exists: a lower threshold means more automatic closures, each one unreviewable.

This gap was asserted the other way round in the first draft of `docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md` ("the review queue is the safety net"), and corrected after an adversarial review of that document.

Two shapes worth weighing, cheapest first:

- The audit or the heartbeat reports supersessions since the last run, with both stems and the reason the judge gave, so a glance is enough to spot a bad one.
- `/kennisbank:review` gains a second queue for recently superseded memories, with reopen as the action (status back to `current`, drop `superseded_by` and `valid_until`).

The first is enough to unblock TASK-147. The second is the real ingress, and matches how the unverified queue already works: the system shows, the user decides.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Supersessions since the previous run are visible to a human without reading the filesystem, including both stems and the judge's stated reason
- [ ] #2 Reopening a wrongly superseded memory is possible through a documented path, and restores it to the recall set
- [ ] #3 The claim that superseding is reversible is either true end to end, or the docs stop making it
- [ ] #4 python -m pytest tests -q is green
<!-- AC:END -->

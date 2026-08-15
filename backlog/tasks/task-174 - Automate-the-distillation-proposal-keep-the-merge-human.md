---
id: TASK-174
title: Automate the distillation proposal, keep the merge human
status: To Do
assignee: []
created_date: '2026-08-15 11:00'
updated_date: '2026-08-15 11:00'
labels: []
dependencies: []
ordinal: 102800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the field review (docs/research/agent-memory-field-review-and-strategy.md).

PRINCIPLES.md #3: what requires manual discipline does not happen in practice.
Distillation from the raw memory layer to the curated wiki is triggered by a
human running `/destilleer`. `distill-notify.py` counts what is pending and
mentions it at session start — a notification, not an action. By the repo's own
principle, that pipeline stalls, and the pending count grows quietly.

The field's answer is the Generative Agents reflection pattern: periodically
cluster related records and synthesise higher-level insight, automatically.

Adopt half of it. Auto-merging into the wiki is the wrong half — it would take
away editor-in-chief control, which is a differentiator rather than an
inconvenience, and it would put LLM output into the curated layer without a human
in the loop. The right half is to automate the *proposal*: an off-hours job
clusters the memory layer, finds clusters dense enough to be worth an article,
and drafts the proposal. The human still merges.

That is automation of the discipline, not of the judgement — the same split the
vault already uses for quarantined memories (`status: unverified` proposes, the
human decides).

Constraints: off the hot path (idle or scheduled, never session start); local
model only; and the proposal must be visible where the human already looks, not
in a file that itself needs discipline to check.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An off-hours job clusters the memory layer and identifies clusters worth an article, with the density threshold stated and tunable
- [ ] #2 A proposal is drafted per qualifying cluster; nothing is written into the curated wiki without a human merge
- [ ] #3 Proposals surface where the human already looks; no new habit is required to find them
- [ ] #4 Nothing runs on the hot path; session start is unchanged
- [ ] #5 Off by default or on by default is an explicit, documented decision, consistent with how the memory subsystem's other toggles are set
- [ ] #6 A run over a real vault shows the proposals are ones a human would plausibly accept — measured, not assumed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->

---
id: TASK-195
title: 'Autonomous memory review: retire the human gate'
status: In Progress
assignee: []
created_date: '2026-08-16 08:01'
labels: []
dependencies: []
ordinal: 164700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Design: `docs/superpowers/specs/2026-08-16-autonomous-memory-review-design.md`, written on request before any code. Owner's stated goal: the memory layer runs without human intervention — safety from evidence and reversibility, not from a person approving things.

The problem in one line: `recall_hits` filters on `status=current`, so the 993 unverified memories are not a review queue, they are invisible — and the designated human exit (`/kennisbank:review`) has one log line ever.

The design is three traps built on this session's measurements: (1) grounded promotion by the local model against the memory's own source chunk — `supported` never fabricated in 210 checks, 58% of the quarantine already carries an exact `source_chunk` stamp; (2) client-LLM whole-transcript adjudication for what trap 1 cannot support — the protocol that survived adversarial review 67/67 times today; (3) retraction only on double agreement between the two independent methods plus a failed refutation, capped, logged with both verdicts, reversible via `reopen()`.

Privacy: trap 1 is local-only. Traps 2/3 reach the client LLM (cloud), so they sit behind a new `auto_review_llm` toggle, default OFF in the shipped repo — this vault's owner consented explicitly; every other deployment stays local unless its owner flips it.

Gates G0–G3 are named in the design and get their numbers pre-registered before building: measure the quarantine's composition first (stratified 60-case exhaustive adjudication), promotion precision ≥0.95, zero false retractions on the sample, and no regression on the 1224-question and freshness evals after the backlog run. TASK-145/162 precedent: a failed gate stops the line and gets reported.

Build order is in the design; each step lands separately. `/kennisbank:review` ends as an audit view with per-line undo, not a work queue.

## Progress (2026-08-16)

Build steps 1-3 of the design are shipped and measured: G0 (PR #129/#130
docs), Trap 1 (PR #130), the backlog drain and G3 (PR #131). 993 judged, 859
promoted (86.5% against G0's predicted 86.7%), 134 escalated to Trap 2. G3:
recall@1 +0.035 and MRR +0.026 on the 1224-question set, recall@5 -0.006 to
displacement, freshness slices stable within one question.

Remaining: Trap 2/3 behind `auto_review_llm` (default OFF) and the
/kennisbank:review audit view — build steps 4-6. Note for the next session:
Trap 1's sweep pass reaches the vault only with the next release+upgrade; the
backlog itself is already drained from the checkout.
<!-- SECTION:DESCRIPTION:END -->
## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 G0 runs before any product code: a stratified 60-case quarantine sample, exhaustively adjudicated, with the base rates written down
- [x] #2 Gates G1-G3 are committed with their thresholds before the gated code produces its first measurement
- [x] #3 Trap 1 (grounded promotion) is local-only, runs as a sweep pass, and promotes nothing below the registered precision bar
- [ ] #4 Traps 2 and 3 sit behind auto_review_llm, default OFF in the shipped repo
- [ ] #5 A retraction requires two independent methods plus a failed refutation, is capped per run, logs both verdicts, and reverses with one reopen()
- [ ] #6 /kennisbank:review becomes an audit view with per-line undo; no step in the pipeline waits for a human
- [ ] #7 python -m pytest tests -q is green
<!-- AC:END -->


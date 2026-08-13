---
id: TASK-156
title: >-
  The supersede judge agrees with 30% of the vault's own supersessions, by
  design
status: To Do
assignee: []
created_date: '2026-08-13 18:41'
labels:
  - memory
  - llm
  - prompt
  - measurement
dependencies: []
priority: high
ordinal: 150700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured 2026-08-13 on the 149 real `superseded_by` pairs in the vault, qwen3.5:4b, asking `judge_supersede(newer, older)` where the vault already recorded a supersession:

    0.70-0.90 (the band that matters)   29/97 = 30%
    0.90-0.95                            2/7  = 29%
    above 0.95 (near-identical)          0/43 =  0%

The 0% above 0.95 is the contamination TASK-147 predicted: those pairs are almost the same text, the model answers "these are identical, so nothing is being replaced", and that is a defensible answer scored as wrong. Any future evaluation must exclude that band.

The 30% is the real number, and it is not obviously a defect. `SUPERSEDE_SYSTEM` ends with "Bij twijfel: false" and "Retract ALLEEN als het aantoonbaar slecht is" — a deliberate fail-safe bias, chosen when a wrong closure was unrecoverable. The measurement puts a price on that choice: seven out of ten real supersessions are not made automatically.

Two readings, and this measurement cannot separate them:

1. The judge is too conservative for the job.
2. Some of the recorded supersessions were themselves wrong — many were made by `supersede_pass` at 0.85 with the older prompt, so the ground truth is partly this same mechanism's earlier output.

Separating them needs labels: take a sample from the 0.70-0.90 band, decide by hand whether each is a genuine replacement, and score the judge against that instead of against its own history.

What changed underneath the original trade-off: since TASK-150 a closure is recorded and reversible (`memory-doctor.py closed` / `reopen`), so a wrong supersession costs a line in a log and one command, not a lost memory. The conservative bias was priced against permanent loss. It deserves re-pricing now — after TASK-144's reordering is applied to this prompt too, which has not been done: only `RECONCILE_SYSTEM` was reworded.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A hand-labelled sample from the 0.70-0.90 band separates 'judge too conservative' from 'historical supersession was wrong'
- [ ] #2 SUPERSEDE_SYSTEM gets the same explicit decision ordering as RECONCILE_SYSTEM, and the agreement rate is measured before and after
- [ ] #3 Any change to the fail-safe bias is argued against the cost of a wrong closure as it stands TODAY, not as it stood before the closure log existed
- [ ] #4 The above-0.95 band is excluded from scoring, with the reason stated in the report
- [ ] #5 python -m pytest tests -q is green
<!-- AC:END -->

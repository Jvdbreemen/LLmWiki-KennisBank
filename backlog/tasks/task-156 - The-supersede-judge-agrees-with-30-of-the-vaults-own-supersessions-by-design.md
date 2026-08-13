---
id: TASK-156
title: >-
  The supersede judge agrees with 30% of the vault's own supersessions, by
  design
status: Done
assignee: []
created_date: '2026-08-13 18:41'
updated_date: '2026-08-13 20:58'
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
- [x] #1 A hand-labelled sample from the 0.70-0.90 band separates 'judge too conservative' from 'historical supersession was wrong'
- [x] #2 SUPERSEDE_SYSTEM gets the same explicit decision ordering as RECONCILE_SYSTEM, and the agreement rate is measured before and after
- [x] #3 Any change to the fail-safe bias is argued against the cost of a wrong closure as it stands TODAY, not as it stood before the closure log existed
- [x] #4 The above-0.95 band is excluded from scoring, with the reason stated in the report
- [x] #5 python -m pytest tests -q is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## AC#2 measured, 2026-08-13, qwen3.5:4b, the same 97 pairs in the 0.70-0.90 band

    old prompt   29/97 = 30% recognised   (260s)
    new prompt   53/97 = 55% recognised   (203s)

Both prompts against the SAME pairs in one run. Recognition nearly doubles, and
the new prompt is also faster — the same effect the reconcile reordering had,
presumably because a model that is given a procedure stops writing an essay
about the definition.

The change is the treatment RECONCILE_SYSTEM got in TASK-144: the order of the
questions made explicit, "is this even about the same thing?" first, and the
kinds of replacement spelled out instead of implied. The old prompt gave a
definition and one example and left the model to work out whether "replaces"
also covers a value that was adjusted or a problem that was solved. Now it says
so.

"Bij twijfel: false" stays. The fail-safe was never the problem; what preceded
it was.

## Still open

AC#1 (hand-labelling a sample to separate "the judge is too conservative" from
"that supersession was itself wrong") and AC#3 (re-pricing the fail-safe bias
now that closures are reversible) are untouched. The 55% is agreement with the
vault's own history, which is partly this same mechanism's earlier output, so it
still cannot tell those two apart. The pairs are dumped and ready to read.

## Bookkeeping note

The prompt change itself landed in commit 8efd6a0, whose message is about the
PR #117 review fixes and does not mention it: `git add -A` swept it in. Recorded
here rather than rewritten, because the commit is already pushed and CI-green,
and a misleading message is better corrected in the open than quietly amended.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Answered by reading the disagreements rather than counting them. Full report: docs/research/supersede-judge-labelled-2026-08-13.md.

Reordering the prompt (the TASK-144 treatment) took agreement from 30% to 55% on the same 97 pairs. Hand-labelling the first 22 of the 44 remaining disagreements then answered what the rest is:

    the judge was right, no real supersession    19 of 22  (86%)
    the judge was wrong, a real one missed        3 of 22  (14%)

So the conservatism is largely not conservatism. Almost every "miss" is the same memory captured twice, weeks apart, in slightly different words — several times once in Dutch and once in English. Closing one of those is housekeeping, not a supersession, and scoring the judge as wrong for saying so measures the wrong thing.

The history is demonstrably unreliable in this band: two ADR memories supersede each OTHER, in both directions. And in one case superseding lost information — the older memory said "scan for placeholders and fix what you find", its successor says only "scan".

**AC#3 answered in the negative, which is the opposite of what this task assumed.** Do not loosen the fail-safe bias. Measured, "Bij twijfel: false" costs 3 missed replacements in 97 pairs — about 3% — while the 44 refusals are 86% correct. Loosening it would buy a few genuine closures and pay by closing duplicates automatically, which nothing here shows to be wanted. The bias was priced against permanent loss and TASK-150 changed that price, but the measurement says the price was never the problem.

Two things a future evaluation must carry: `superseded_by` links are not ground truth for this question, because they record housekeeping as often as contradiction; and 19 of 22 disagreements exist because the same knowledge was captured twice with neither capture aware of the other, which is a write-time dedup question, not a supersede question.
<!-- SECTION:FINAL_SUMMARY:END -->

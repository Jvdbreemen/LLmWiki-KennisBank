---
id: TASK-147
title: 'Retune the supersede window: 0.85 to 0.75, TOP_K 2 to 3'
status: In Progress
assignee: []
created_date: '2026-08-12 20:32'
updated_date: '2026-08-13 18:56'
labels:
  - memory
  - retrieval
  - performance
dependencies: []
references:
  - scripts/_reconcile.py
  - scripts/_maintenance.py
  - scripts/judge-model-sweep.py
  - docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md
priority: medium
ordinal: 141700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured on 101 of the vault's 107 real `superseded_by` pairs (P1, no LLM calls; the closed memory re-embedded through `doc_text` + `kind="doc"`, the successor read from `kb-index.db`).

**P1a — cosine between a closed memory and its successor**

```
p10=0.757  p25=0.824  p50=0.897  p75=1.000  p100=1.000

above 0.95:  41/101 =  41%
above 0.85:  71/101 =  70%   <- supersede_pass's window
above 0.75:  94/101 =  93%   <- reconcile's window
```

**P1b — rank of the successor among all 1531 current memories**

```
top-1: 58%   top-2: 95%   top-5: 100%   median 1   worst 5

visible to reconcile      (top-2 AND cos>0.75):  92%
visible to supersede_pass (cos>0.85):            70%
```

Two conclusions, both against the intuition that the candidate set was too narrow:

1. **Search is not the bottleneck.** 92% of real pairs already fall inside reconcile's window at a median rank of 1. The mechanism looks straight at the successor and decides wrongly.
2. **The window is aimed at the wrong band.** The three lowest cosines are the substantive cases — including *"The Rescan button lacks visual feedback"* -> *"De Rescan-knop toont nu een 'Scanning...' status"* at cos 0.704, the canonical problem-solved state change, which sits below BOTH thresholds. Meanwhile the two highest pairs are byte-identical (cos 1.000) and should never have reached a judge at all.

So 41% of the judge's work is striking out duplicates while the valuable cases fall outside the window.

Changes:

- Run `exact_duplicate_pass` plus a near-duplicate step (cosine above ~0.95) BEFORE any judge call, so that 41% costs no model call and contributes no label noise.
- `_maintenance.supersede_pass`: threshold 0.85 -> 0.75. More judge calls, spent where they pay.
- `_reconcile.TOP_K`: 2 -> 3. Lifts pair visibility from 95% to 97% at negligible cost; top-5 reaches 100% if the measurement justifies it.

Note for future evaluation: the 107 labels are contaminated for this purpose. With 41% of pairs near-identical, three independent models (local 4b, local 9b, Haiku) all answered "the texts are identical" and chose NOOP — a defensible answer. Score future arms on the 0.70-0.90 band only.

Design context: `docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md`, step 3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 supersede_pass runs at 0.75 with the extra call volume measured against the previous run
- [x] #2 TOP_K is raised and the change in pair visibility is reported against P1's 95% baseline
- [x] #3 A wrongly superseded memory has somewhere to surface before the threshold is lowered (see the review-queue task); otherwise the lower threshold stays off
- [x] #4 A re-run of judge-model-sweep.py scores only the 0.70-0.90 band and states why
- [x] #5 python -m pytest tests -q is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Adversarial review, 2026-08-12. P1 measured recall and never precision. Measured over all 1,171,215 pairs among the 1531 current memories:

  pairs above 0.95:      1
  pairs above 0.90:      4
  pairs above 0.85:     11     <- supersede_pass's entire workload
  pairs above 0.80:     51
  pairs above 0.75:    163
  neighbours per memory above 0.85: median 0, p95 0, max 1

Two consequences.

DEDUP BEFORE THE JUDGE IS DROPPED from this task. The 41% above 0.95 sits in the historical pairs; the living corpus holds exactly one. Superseded memories leave the index, so a closed pair leaves the candidate space with it. There is nothing to save.

SUPERSEDE_PASS IS NOT THE SELF-CORRECTING MECHANISM. Eleven pairs in the whole vault means a perfect judge would close at most eleven things. The weight belongs on reconcile at write time, which only ever sees what intake delivered (TASK-145).

The threshold change survives and is cheaper than feared: 11 -> 163 candidate pairs, roughly three minutes of judge time for the entire corpus.

New gate: lowering the threshold increases automatic supersessions, and nothing today shows a closed memory to a human -- /kennisbank:review walks the unverified queue only, and recall filters on current. The earlier claim that superseding is safe because the review queue catches it was wrong.

## Done, 2026-08-13. Full report: docs/research/supersede-window-2026-08-13.md

**AC#3's gate is satisfied.** TASK-150 landed first: every closure is recorded in `memory-closed-log.jsonl` with what replaced it and why, and `memory-doctor.py reopen <stem>` puts it back. A wrong supersession now costs a log line and one command.

**AC#1 — threshold 0.85 -> 0.75.** Re-measured on 149 real pairs (P1 had 101):

    above 0.95   43/149 = 29%
    above 0.85   87/149 = 58%
    above 0.75  141/149 = 95%

So 0.85 saw 58% of real supersessions and 0.75 sees 95% — a stronger case than P1's 70%/93%. Call volume: 10 candidate pairs become 163, about three minutes of judge time for the whole vault.

**AC#2 — TOP_K 2 -> 3, and 3 is complete rather than a compromise.** Successor rank among all 1595 current memories: top-1 83.2%, top-2 96.6%, top-3 98.0%, top-5 100%. Raising it beyond 3 buys nothing, measured rather than argued: across all 1,271,215 pairs, no memory has more than three neighbours above 0.75 (median 0, p99 2, max 3; only 6 memories exceed 2). With TOP_K=3 the judge sees every neighbour that exists.

Worth keeping straight: the top-5 figure is rank among ALL memories, while `similar_existing` filters by threshold first and takes top-k second. A successor at rank 4 below 0.75 is invisible at any k. The threshold binds, not k.

**AC#4 — scored only on 0.70-0.90, and here is why.** Agreement with the vault's own recorded supersessions, qwen3.5:4b:

    0.70-0.90   29/97 = 30%    the band that matters
    0.90-0.95    2/7  = 29%
    above 0.95   0/43 =  0%    near-identical, defensibly answered "no change"

The 0% confirms the contamination this task predicted; that band must never be scored.

## The finding that reframes the task

**Two measurements say the window is not where the problem is.**

First, the judge recognises 30% of real supersessions in the band that matters. At a median rank of 1, the mechanism looks straight at the successor and says no. Lowering the threshold triples what it is shown and cannot hurt — you cannot judge what you never see — but it does not by itself produce more supersessions. That is not obviously a defect either: `SUPERSEDE_SYSTEM` says "Bij twijfel: false" on purpose. The measurement prices that choice, and the price was set when a wrong closure was unrecoverable, which TASK-150 changed. Re-pricing is TASK-156.

Second, and more concretely: on today's corpus the threshold change is **entirely** inert, not merely small. Measured with volatility applied:

    above 0.75   163 pairs,   0 reach the judge
    above 0.85    10 pairs,   0 reach the judge

1572 of 1595 memories carry no volatility label and therefore default to event, and the guard skips any pair with an event on either side. `supersede_pass` will report zero on this corpus at any threshold until new captures arrive carrying labels. That is the designed trade, recorded here so a zero in the heartbeat is not later mistaken for a broken guard.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Threshold 0.85 → 0.75 and TOP_K 2 → 3, both justified by measurement on 149 real supersede pairs rather than by intuition. 0.85 saw 58% of real supersessions; 0.75 sees 95%. TOP_K=3 is complete rather than a compromise: no memory in this vault has more than three neighbours above the threshold, so the judge now sees every neighbour that exists.

The gate on AC#3 was real and is satisfied: TASK-150 landed first, so a wrong closure costs a log line and one `memory-doctor.py reopen`.

Two findings reframe what this change can achieve, and both are written into the code so a later zero is not misread. The judge recognises only 30% of real supersessions in the 0.70-0.90 band — at a median rank of 1 it looks straight at the successor and says no, so search was never the bottleneck. And on today's corpus the change is entirely inert: 163 candidate pairs above 0.75, of which 0 reach the judge, because 1572 of 1595 memories default to event.

Scoring above 0.95 is excluded permanently: 0/43 there, because those pairs are near-identical and "nothing is being replaced" is a defensible answer that scores as wrong.

Report: docs/research/supersede-window-2026-08-13.md. Follow-up: TASK-156.
<!-- SECTION:FINAL_SUMMARY:END -->

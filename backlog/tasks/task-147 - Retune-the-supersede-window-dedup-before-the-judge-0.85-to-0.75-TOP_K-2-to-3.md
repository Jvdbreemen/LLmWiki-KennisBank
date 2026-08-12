---
id: TASK-147
title: 'Retune the supersede window: 0.85 to 0.75, TOP_K 2 to 3'
status: To Do
assignee: []
created_date: '2026-08-12 20:32'
updated_date: '2026-08-12 20:41'
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
- [ ] #1 supersede_pass runs at 0.75 with the extra call volume measured against the previous run
- [ ] #2 TOP_K is raised and the change in pair visibility is reported against P1's 95% baseline
- [ ] #3 A wrongly superseded memory has somewhere to surface before the threshold is lowered (see the review-queue task); otherwise the lower threshold stays off
- [ ] #4 A re-run of judge-model-sweep.py scores only the 0.70-0.90 band and states why
- [ ] #5 python -m pytest tests -q is green
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
<!-- SECTION:NOTES:END -->

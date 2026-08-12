---
id: TASK-145
title: 'Intake truncation: the extractor reads 6 chunks of a 58-chunk session'
status: To Do
assignee: []
created_date: '2026-08-12 20:31'
updated_date: '2026-08-12 20:41'
labels:
  - memory
  - capture
  - bug
dependencies: []
references:
  - scripts/memory-sweep.py
  - scripts/_extract.py
  - scripts/_sweeputil.py
  - docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md
priority: high
ordinal: 139700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`run_sweep(max_chunks=6)` hands `_extract` only the first six chunks of a transcript. Measured on four transcripts that contain the fact "the vault defaults to qwen3-embedding:4b":

| transcript | chunks | read | coverage | fact in chunk |
| --- | --- | --- | --- | --- |
| 2026-08-01-llmwiki-kennisbank | 24 | 6 | 25% | — |
| 2026-08-06-llmwiki-kennisbank | 14 | 6 | 43% | — |
| 2026-08-07-adr-kit | 31 | 6 | 19% | — |
| 2026-08-06-adr-kit | 58 | 6 | 10% | **17** |

24 of 127 chunks read. The fact sat in chunk 17 of 58 and was therefore never shown to the extractor.

Consequence, verified across the whole vault:

```
transcripts containing "qwen3-embedding:4b":  13   (10 swept, 3 pending)
session logs:                                  2
wiki articles:                                 3
memories:                                      0     <- the layer the recall hook injects
```

Those ten swept transcripts produced 99 memories between them, none about the embedding model. The four stale memories asserting `qwen3-embedding:8b` were never superseded because nothing exists to supersede them WITH. No judge and no structure repairs a fact that was never captured.

The cap exists for cost: with a reasoning model a chunk took 30-56 s, so 58 chunks meant 30-54 minutes per transcript. After TASK-143 (`think: false`) a call takes 1.6-4 s, so the same transcript costs 2-4 minutes in a detached background sweep. Full coverage is affordable for the first time.

Do not simply remove the cap. Measure first: what does each extra chunk yield in new (non-duplicate) memories, and what does the corpus size do? Going from 19% to 100% could multiply the memory count several times over, and dedup, judge and reconcile have to carry it — reconcile being the weak link (TASK-144).

Design context: `docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md`, step 1. This is the step that fixes the observed problem; everything else in that spec keeps case five from happening.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Yield per chunk position is measured on a sample of long transcripts: new memories, duplicates, and cost per extra chunk
- [ ] #2 max_chunks is raised or removed on the basis of that measurement, with the chosen value and its reason recorded
- [ ] #3 A full sweep over a long transcript completes within the detached background budget, with the wall-clock time recorded before and after
- [ ] #4 P2 holds: after a re-sweep a memory asserting qwen3-embedding:4b exists in 09-memory
- [ ] #5 python -m pytest tests -q is green
- [ ] #6 transcript_text() returns content for every transcript format in 01-raw/transcripts, or reports which formats it cannot read; today four of ten sampled transcripts yield zero chunks
- [ ] #7 P5 holds: kb-eval on the existing question sets shows recall is no worse after the corpus grows than before
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Adversarial review, 2026-08-12. Two changes to this task.

1. The cause is bigger than max_chunks. Checked across every swept transcript containing the fact: 0 of 10 had it within the first six chunks, and FOUR of those ten yield zero chunks at all while the raw file demonstrably contains the text.

  2026-08-06-adr-kit         58 chunks   fact in chunk 17
  2026-08-09-wt-otgw-1xx    106 chunks   fact in chunks 36, 81, 86
  2026-08-04-adr-kit          0 chunks   <- transcript_text() returns NOTHING
  2026-08-04-oralhistoryagent 0 chunks   <- same
  2026-08-04-rvdb             0 chunks   <- same
  2026-08-04-adr-kit          0 chunks   <- same

Most likely a different message shape (Copilot or Codex transcripts). Raising max_chunks does not fix that half, and it should be fixed first: reading more of a transcript the parser cannot read at all buys nothing. Until it is understood, the true size of the intake gap is unknown -- it may be much larger than 19%.

2. Yield and cost are not enough. retrieve_top_n is 3, so multiplying the corpus multiplies the competition for three slots. A fact that is captured but ranks fourth is exactly as invisible as one never captured. This task is now gated on an eval run (P5) over the existing question sets, before and after.
<!-- SECTION:NOTES:END -->

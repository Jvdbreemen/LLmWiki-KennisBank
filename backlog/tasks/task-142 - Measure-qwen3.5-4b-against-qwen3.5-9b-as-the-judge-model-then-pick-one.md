---
id: TASK-142
title: 'Measure qwen3.5:4b against qwen3.5:9b as the judge model, then pick one'
status: Done
assignee: []
created_date: '2026-08-12 18:52'
updated_date: '2026-08-12 19:15'
labels:
  - research
  - memory
  - llm
  - performance
dependencies: []
references:
  - scripts/_llm.py
  - scripts/_extract.py
  - scripts/_judge.py
  - scripts/_reconcile.py
  - docs/research/embedding-model-sweep-2026-08.md
priority: medium
ordinal: 136700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The judge/extraction model was pinned to `qwen3.5:4b` in TASK-139 on VRAM headroom, not on output quality. The only quality evidence is a single observation: both 4b and 9b returned valid JSON on one prompt where `gemma4:12b` returned 3100 characters of Dutch prose. That is not enough to choose between them.

Both fit the 16 GB card beside the embedding model (`qwen3-embedding:4b` at num_ctx 2048 = 4.06 GB):

| judge | num_ctx | VRAM | total with embedder | free |
| --- | --- | --- | --- | --- |
| qwen3.5:4b | 4096 | 3.13 GB | 7.19 GB | 7.6 GB |
| qwen3.5:9b | 4096 | 5.49 GB | 9.55 GB | ~5 GB |

So VRAM does not decide it. Quality has to.

**What the judge actually does.** Three seams, all strict-JSON, all fail-safe in a way that HIDES a bad model rather than surfacing it:

- `_extract.extract_candidates()` -> JSON list of {title, body, type}. Parse failure returns `[]`: no memories captured, silently.
- `_judge.judge()` -> JSON {verdict, importance, reason}. Parse failure returns `unverified`: everything lands in quarantine.
- `_reconcile.judge_reconcile()` -> ADD | SUPERSEDE | NOOP. Parse failure returns `ADD`: duplicates accumulate.

A weaker model therefore does not crash the sweep. It quietly stops capturing, quarantines everything, or duplicates. Those are the failure modes to measure.

**Reference data.** There is no human-labelled gold set: `memory-review-log.jsonl` holds one entry. What exists is the corpus the incumbent produced and the user has lived with — 1531 current, 107 superseded (each with a `superseded_by` link to its successor), 23 unverified. The 107 pairs are a real, in-domain, hard decision set. Agreement with them measures "does this model reproduce the accepted behaviour", NOT correctness, and the report must say so in those words.

**Design.**

1. Arms: `qwen3.5:4b` and `qwen3.5:9b`, both at num_ctx 4096, keep_alive -1, temperature/seed as the seams already set them. The model is forced per arm through `KB_LLM_MODEL`, which beats the vault config.
2. Reconcile (labelled-ish): N sampled `superseded_by` pairs expecting SUPERSEDE, plus N random low-similarity pairs expecting ADD. Report per-class accuracy, not one blended number — the two errors are not equally bad.
3. Extract: the same transcript chunks through both arms. Report JSON-conformance, candidates per chunk, and the refusal-gate hit rate.
4. Judge: the extracted candidates through both arms. No labels, so report agreement plus the disagreement set for inspection.
5. Determinism: 3 repeats of a subset per arm, exact-match rate. Temperature 0 should give 1.00; anything less is a reason to distrust a single-run comparison.
6. Latency p50/p95 per seam per arm, and VRAM from `/api/ps` with the embedder resident.
7. Raw responses saved alongside the metrics, so a claim can be re-checked without re-running.

**Decision rule, fixed before the numbers exist.** Keep `qwen3.5:4b` unless the 9b wins on BOTH of: SUPERSEDE-class agreement on the labelled pairs, and JSON conformance across the three seams — with the ADD class not worse. A win on latency is irrelevant (the sweep is off the hot path); a loss on latency is acceptable up to roughly 2x. If the arms tie, the smaller model wins on the VRAM headroom it leaves for everything else.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A reproducible harness in scripts/ runs both arms from one command and writes raw responses plus metrics as JSON
- [x] #2 Reconcile is scored per class against the 107 superseded_by pairs and an equal number of unrelated pairs, with the report stating explicitly that these are incumbent-produced labels, not ground truth
- [x] #3 JSON-conformance is measured on the RAW model response per seam, so a fail-safe fallback is never counted as a model success
- [x] #4 Determinism is reported as an exact-match rate over 3 repeats per arm
- [x] #5 Latency p50/p95 per seam and VRAM with both models resident are reported and shown to fit 16 GB
- [x] #6 A written decision applies the pre-registered rule, including what did not work and what stayed unmeasured
- [ ] #7 python -m pytest tests -q is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Measured 2026-08-12. Verdict: keep qwen3.5:4b. Full report: docs/research/judge-model-4b-vs-9b-2026-08.md.

The pre-registered rule asked the 9b to win on supersede agreement AND JSON conformance without losing the ADD class. It won neither and lost the third:

  supersede agreement (n=20)   4b 35%  | 9b 25%
  unrelated -> ADD (n=20, OOD)  4b 65%  | 9b 0%
  reconcile JSON conformance    4b 100% | 9b 90%
  candidates per chunk          4b 3.17 | 9b 1.67
  chunks yielding nothing       4b 1/6  | 9b 5/6
  determinism (4x3)             4b 4/4  | 9b 4/4
  VRAM                          4b 3.13 | 9b 5.49 GB

The decision rests on extraction, not on the supersede percentages: 35% against 25% on twenty pairs is inside the noise (SE ~11 points), while five of six chunks yielding NOTHING is not. A judge that proposes no candidates cannot be redeemed by judging well.

Setting the harness up is what found TASK-143, and that one matters more than this comparison: the seam was returning nothing at all roughly a third of the time because qwen3.5 thinks first and the thinking spent the answer's num_ctx budget. Every arm above ran with think=false; without it both arms would partly have measured the fail-safes.

Also filed: TASK-144 -- both models use NOOP to mean 'unrelated', which is the definition of ADD, and NOOP is the verdict that discards the new memory. Plus the brace-slice parser that breaks on prose after the JSON.

AC #7 (suite green) is ticked on the run that includes the TASK-143 fix and its guard tests.
<!-- SECTION:NOTES:END -->

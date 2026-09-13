# Source-recall and experience-memory reviewed evidence packet

Date: 2026-08-29
Branch: `codex/source-recall-experience-evidence`
Policy: both routes remain opt-in; outcome-aware ranking remains disabled.

## Decision

| layer | measured result | decision |
|---|---|---|
| source recall | independent dev: sparse-first hit@5 0.25 versus BM25 0.75; specificity 0.90; warm p95 8.33 s | **reject sparse-first vector reranking; retain labelled lexical evidence search only** |
| experience recall | hybrid hit@3 is 0.90 versus lexical 0.80; blinded action correctness is 43/60 versus 19/60 baseline (delta +0.40, 95% CI +0.20 to +0.5833), but false warnings are 2 of 10 | **value proven, reject this advisory design for rollout** |
| outcome-aware ranking | no longitudinal exposed/control evidence | **reject** |

These decisions distinguish a useful mechanism from a justified product
feature. Experience retrieval shows a real ten-point retrieval gain, passes
its failure-recall and advisory-precision gates, and materially improves
blinded action selection. It still fails the false-warning safety gate. Source
grounding has a complete reviewed oracle,
but the proposed full vector projection has not earned its storage and ingest
cost.

## Reviewed datasets

The private evaluation boundary contains 120 human-reviewed cases:

- source: 50 positive, 9 `unknown`, and 1 `not_found` case over 28 expected
  source documents;
- experience: 60 positive evidence-bound cases;
- advisory abstention: 10 additional cross-layer probes derived only from the
  already reviewed source negatives.

All 50 positive source hashes and windows still resolve, so the source oracle
ceiling is 1.00. The owner subsequently reviewed all 60 experience outcomes
using separate attempt, resolution, and final-state axes. The evaluator-facing
final states contain 38 success, 18 partial, 1 mixed, and 3 failure episodes.
The attempt axis preserves 29 failures, 3 mixed, 5 partial, and 23 successes;
resolution records 23 validated fixes, 13 proposed fixes, 6 diagnoses, 2
unresolved cases, 1 correction with cost, and 15 cases where recovery was not
applicable. This avoids erasing a failed approach merely because its later fix
succeeded. The subsequent 60-pair owner review measures action-selection value
without exposing the hidden arm mapping during judgment.

Private prompts, answers, source coordinates, and generated databases live
under `06-claude/evaluations/source-experience-2026-08-27` in the configured
vault. They are deliberately not part of this packet.

## Source evidence and attack on the full-vector proposal

The approved raw-source corpus currently contains 16,271 UTF-8 documents and
781,127,644 bytes. A disposable full-document FTS5 index is 1,105,334,272 bytes
and took 247.455 seconds to build. It produced:

| metric | result |
|---|---:|
| hit@1 | 0.46 |
| hit@5 | 0.66 |
| MRR | 0.531 |
| negative no-hit precision | 0.00 |
| query p50 | 51.6 ms |
| query p95 | 184.8 ms |

The expected documents alone contain 66,733,469 characters and would produce
37,085 chunks at the current 2,000/200 chunking policy. That is only 28 of the
16,271 approved documents. Pre-embedding the complete raw corpus is therefore
not a modest “third vector database”; it is a large new ingest, invalidation,
storage, and rebuild obligation.

Lexical candidate coverage rises to 0.76 at 20 documents, 0.84 at 50, and 0.88
at 100. This supports a cheaper next experiment: FTS/BM25 candidate generation,
then on-demand passage extraction and vector reranking with a persistent cache.
It does not support embedding every raw chunk in advance. The initial source
vector arm and paired answer benchmark were still unmeasured at this
checkpoint, so source recall remained a hold pending the bounded sparse-first
experiment described below.

### Independent sparse-first development result

The owner subsequently reviewed a separate 30-case source development set: 20
positives over unique documents and 10 hard negatives, with no id, normalized
query, or expected-source overlap with the frozen 60-case holdout. Exact source
hashes, reviewed windows, and FTS snapshots were validated before the run.

All 18 preregistered sparse-first configurations failed. The best available
point (`candidate_docs=100`, `max_passages=40`, `min_cos=0.70`) measured
document hit@5 0.25, passage hit@5 0.15, citation precision 0.40, provenance
precision 1.00, no-hit specificity 0.90, and warm p95 8.33 seconds. Its shared
content-addressed cache was 33.9 MB. Pure BM25 on the identical dev cases
measured hit@5 0.75 and p95 50.4 ms, although it returned a hit for every
negative.

This is a development pre-reject: the vector reranker loses 0.50 recall while
still missing the abstention and latency gates. The frozen holdout remains
unspent and the paired 50-case answer benchmark was not generated for a route
already disqualified by three upstream gates. Details are in
`docs/research/source-sparse-development-result-2026-08-31.md`.

## Experience evidence: historical pre-correction run

The real SQLite FTS/vector projection used `ollama:qwen3-embedding:4b` over the
60 reviewed records and 70 queries:

| metric | hybrid | lexical |
|---|---:|---:|
| hit@1 | 0.817 | 0.750 |
| hit@3 | 0.900 | 0.800 |
| MRR | 0.858 | 0.775 |
| validated failure hit@3 | 0.667 | 0.667 |
| outcome calibration | 0.900 | 0.800 |

Hybrid therefore meets the preregistered absolute and relative overall
retrieval thresholds. Evidence precision is 1.00, candidate leakage is zero,
and no unsupported lesson was returned. Explicit experience query latency was
97.5 ms p50 and 133.0 ms p95.

The failure-advisory route returned three warnings, two of which matched the
expected final-failure experience. E-038 was missed, and abstention probe
XP-S-005 incorrectly received the E-010 warning. Advisory precision is 0.667,
and 1 of 10 negative probes received a warning, so false-warning rate 0.10
meets its boundary exactly. Failure hit@3 and advisory precision still miss
their preregistered thresholds, making the rollout decision **reject**.
Changing the threshold on this holdout would be test-set tuning; calibration
requires a separate development set followed by one untouched rerun.

All 29 failure-attempt episodes survived as evidence-bound lessons in the
dead-end report (survival 1.00), including episodes whose validated fix makes
their final state success. This check is based on the curated records that
seeded the projection, so it proves lossless projection, not independent
extraction quality. Consolidation proposed zero shared lessons and performed
no mutation.

### Protocol correction before further calibration

The recorded 0.667 failure hit@3 and advisory precision used final `failure` as
the warning target. The completed two-axis review shows that this is the wrong
unit: a failed attempt remains a valid dead-end warning when a later fix makes
the overall episode successful. Otherwise the evaluator punishes the layer for
returning its most actionable lessons.

Before selecting any new threshold or rerunning the frozen holdout, the durable
record and evaluator were therefore extended with separate `attempt_state` and
`resolution_state` fields. Failure hit@3 and advisory correctness now use the
attempt axis; outcome calibration still uses the final state. Existing records
without an attempt label retain a narrow final-failure fallback. This is a
protocol correction driven by the human label model, not a threshold selected
on holdout scores. The table above remains the historical pre-correction
baseline until the independent development set is labelled and frozen.

### Final attempt-aware one-shot holdout

An independent 21-case development set selected the unchanged 0.50 cosine
floor. The threshold and one-shot evaluator were committed before scoring.
The frozen 70-case holdout was then run exactly once using the attempt axis for
failed-approach recall and the final state only for outcome calibration.

| metric | hybrid | lexical |
|---|---:|---:|
| hit@1 | 0.817 | 0.750 |
| hit@3 | 0.900 | 0.800 |
| MRR | 0.858 | 0.775 |
| validated failure-attempt hit@3 | 0.931 | 0.828 |
| evidence precision | 1.000 | 1.000 |
| candidate leakage | 0 | 0 |
| explicit-route p50 / p95 | 99.0 / 129.3 ms | not timed separately |

The hybrid gain is real and not explained by lexical retrieval. The advisory
route returned 29 warnings: 27 correct warnings for 29 failure attempts and 2
incorrect warnings on the 10 unrelated probes. Advisory precision therefore
passes at 0.931, but false-warning rate fails at 0.20 against the maximum 0.10.
The aggregate rollout gate remains **reject**.

The private aggregate report is bound to SHA-256
`0f5881ee6181fe8d9df94ea2779a1404ab71403dca61c7b29fccd443e36208be`.
This holdout is spent: there will be no rerun or threshold tuning from its
scores.

## Downstream action value

The preregistered blinded comparison used all 60 positive experience cases.
Both arms used local `qwen3.5:4b`, temperature zero, and identical top-four
production wiki/memory context. The experience arm additionally received the
actual top-three validated retrieval hits, including misses and imperfect
ordering.

Experience context produced 43/60 correct and actionable candidates versus
19/60 for the strongest baseline. The paired delta is +0.40, with a
deterministic 10,000-resample 95% bootstrap interval from +0.20 to +0.5833.
The A/B presentation was balanced 30/30. This passes the preregistered value
gate of n >= 60 and delta >= +0.10.

The result proves downstream value worth preserving as a research path. It
does not reverse the false-warning failure and does not authorize advisory
rollout, ranking changes, or skill promotion. Aggregate details are in
`docs/research/experience-paired-action-result-2026-08-30.md`.

## Regression evidence

With both routes off, 5,000 calls per gateway measured approximately 0.0008 ms
p50 and p95 overhead above the no-op baseline. The normal wiki/memory path is
therefore structurally unchanged by routing.

No paired downstream source-answer labels were collected. Source answer
correctness therefore remains unproven by design: the sparse candidate failed
independent development recall, abstention, and latency before it could spend
the frozen holdout or justify a 50-case answer-generation review. Experience
action selection is measured as described above, while an already measured
safety failure still takes precedence over downstream value for rollout.

The final complete repository suite passed **1,886 tests with 3 skips in
683.99 seconds** using Python 3.12 and a writable `--basetemp` outside the Git
worktree. An earlier run in this final verification cycle deliberately disabled
usage telemetry globally and thereby invalidated 13 telemetry-write tests; it
also exposed one real product-surface naming regression, which was fixed. The
clean rerun used isolated test vaults with their intended telemetry contracts
and had zero failures.

## Recommended next work

1. Do not build the naive full raw-source vector index and do not run the
   rejected sparse-first reranker on the frozen holdout. If source retrieval is
   revisited, start with a new candidate-generation/ranking design and a new
   independent development set; preserve the current frozen set.
2. Do not tune or rerun the spent experience holdout. Any future advisory
   design must start with a new development set and a newly frozen holdout; the
   current rollout remains rejected on false-warning safety.
3. Keep the completed two-axis outcome labels and paired action judgments
   frozen. Any follow-up safety design needs a new development set and newly
   frozen holdout rather than reuse of these cases.
4. Keep source recall explicit and experience recall experimental. Do not
   enable outcome-aware ranking or automatic skill promotion.

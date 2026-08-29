# Source-recall and experience-memory reviewed evidence packet

Date: 2026-08-29
Branch: `codex/source-recall-experience-evidence`
Policy: both routes remain opt-in; outcome-aware ranking remains disabled.

## Decision

| layer | measured result | decision |
|---|---|---|
| source recall | reviewed oracle is complete, but the full vector arm was not built; full-corpus lexical hit@5 is 0.66 and returns a hit for every negative probe | **hold; reject naive full-corpus pre-embedding as the next step** |
| experience recall | hybrid hit@3 is 0.90 versus lexical 0.80; after two-axis human outcome review, false warnings are 1 of 10 but failure hit@3 and advisory precision are both 0.667 | **reject for rollout; retain as an experiment** |
| outcome-aware ranking | no longitudinal exposed/control evidence | **reject** |

These decisions distinguish a useful mechanism from a justified product
feature. Experience retrieval shows a real ten-point retrieval gain. It still
fails its failure-recall and advisory-precision gates. Source grounding has a
complete reviewed oracle, but the proposed full vector projection has not
earned its storage and ingest cost.

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
succeeded. Paired answer/action claims remain unmeasured.

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
It does not support embedding every raw chunk in advance. The current source
vector arm and paired answer benchmark remain unmeasured, so source recall is a
hold rather than a rollout approval.

## Experience evidence

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

## Regression and missing value evidence

With both routes off, 5,000 calls per gateway measured approximately 0.0008 ms
p50 and p95 overhead above the no-op baseline. The normal wiki/memory path is
therefore structurally unchanged by routing.

No paired downstream answer or action labels have been collected yet. The gate
now records their sample counts explicitly; absence produces `hold`, while an
already measured safety failure still produces `reject`. No claim is made that
either layer improves answer correctness, action selection, repeated-failure
rate, or future task completion.

The complete repository suite passed **1,833 tests with 3 skips in 627.92
seconds** using Python 3.12 and a writable `--basetemp` outside the Git
worktree. An earlier Python 3.14 invocation stopped during collection because
that interpreter lacked the Atlas `fastapi` dependency; no tests ran in that
invalid attempt.

## Recommended next work

1. Do not build the naive full raw-source vector index. Prototype sparse-first
   candidate generation plus cached on-demand passage embeddings and compare it
   against the frozen private source holdout.
2. Create a separate advisory calibration set. Adjust the failure-warning gate
   there, freeze it, then rerun these 10 untouched negatives once. The current
   rerun reaches the false-warning boundary but still fails failure hit@3 and
   advisory precision.
3. Keep the completed two-axis outcome labels frozen and collect paired
   baseline-versus-layer answer/action judgments.
4. Keep source recall explicit and experience recall experimental. Do not
   enable outcome-aware ranking or automatic skill promotion.

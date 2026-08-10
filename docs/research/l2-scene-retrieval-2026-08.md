# L2 scene retrieval: measured, and not adopted

**Date:** 2026-08-11
**Task:** TASK-134
**Design:** `docs/superpowers/specs/2026-08-05-l2-scene-retrieval-design.md`
**Verdict:** no arm met the winner rule. `scene_retrieval` stays off.

## What was tested

A scenario tier (L2) between atomic memories and curated wiki articles, modelled
on TencentDB Agent Memory's L0-L3 pyramid. Scenes are derived rows in
`kb-scene.db`, built off the hot path from vectors that already live in
`kb-index.db`. They are never returned as retrieval hits. At query time the best
scene acts as a prior over its members: admitted at a lower similarity floor
(`scene_floor`), and/or given a score bonus (`scene_boost`).

Three clusterers were to be compared. Only one produced a scene index on this
vault; the reasons for the other two are themselves results and are recorded
below.

## Corpus and controls

| Property | Value |
| --- | --- |
| Indexed documents | 1707 (1508 memory, 199 wiki) |
| Memory eval set | 1224 questions, split 70/30 with seed 42 |
| Dev split used for every arm | 856 questions |
| Holdout / v2 confirmation sets | never run — no candidate qualified |
| Embedding backend | `ollama:qwen3-embedding:4b`, 2560 dims |
| Query vectors | embedded once, cached, reused by every arm |

Two identical baseline runs bracket the arm sequence. They returned **identical
numbers and zero flips**, which is what makes the per-arm deltas below
attributable: within one index state on one day, the pipeline is deterministic.
That control also rules out usage-telemetry drift across the sequence —
`_rank.rerank` multiplies by `usage_factor(last_used, today)` and no
`--usage-snapshot` was pinned, so a moving usage signal would have shown up as
baseline A ≠ baseline B.

Absolute numbers are **not** comparable across an index rebuild or a date
boundary. `_rank.rerank` multiplies the similarity score by
`recency_factor(age_days(ref, today), memory_type)`, which is day-granular, so
crossing midnight reorders near-ties. Measured directly: 146 of 856 questions
changed order, every one of them with an identical document set, 64 improving
and 6 worsening. That observation crossed the date boundary *and* an index
rebuild in one step and cannot now be attributed to either alone — the
pre-rebuild index no longer exists. It is reported as the reason absolute
numbers do not travel, not as an isolated measurement of the recency mechanism.
Every comparison in this report is within one index state on one day.

## Clusterer 1: community — the only one that produced scenes

Built from `kb-graph.db` communities.

| Diagnostic | Value |
| --- | --- |
| Scenes | 245 |
| Median size | 3 |
| p95 size | 20 |
| Largest | 48 |
| Coverage | 1495 of 1508 indexed memories (99.1%) |
| Singletons | 51 |

Healthy shape: no blob scene acting as a disguised global floor change.

### Oracle ceiling

Of the questions the baseline misses at k=5, how many have their gold memory in
the same scene as a memory the baseline *did* retrieve? That is the upper bound
on what any prior setting can recover.

```
questions 856   misses 209   reachable 47   ceiling +0.055 recall@5 (0.756 -> 0.811)
```

The winner rule needs +0.02, i.e. 18 of those 209 misses. The ceiling clears
that threshold by a wide margin, so the arms were worth running.

## Arm results (dev split, 856 questions, one index state)

| Arm (floor / boost) | recall@1 | recall@3 | recall@5 | MRR | p50 ms | gained | lost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline A | 0.334 | 0.658 | 0.756 | 0.499 | 95 | – | – |
| baseline B | 0.334 | 0.658 | 0.756 | 0.499 | 98 | 0 | 0 |
| 0.35 / 0.00 | 0.328 | 0.657 | 0.756 | 0.496 | 160 | 1 | 1 |
| 0.30 / 0.00 | 0.328 | 0.657 | 0.756 | 0.496 | 164 | 1 | 1 |
| 0.45 / 0.05 | 0.259 | 0.609 | 0.741 | 0.443 | 159 | 4 | 17 |
| 0.35 / 0.05 | 0.186 | 0.564 | 0.734 | 0.389 | 177 | 8 | 27 |
| 0.25 / 0.10 | 0.186 | 0.564 | 0.734 | 0.388 | 170 | 8 | 27 |

recall@5 by memory type:

| Arm | beslissing | feit | procedure | voorkeur |
| --- | --- | --- | --- | --- |
| baseline | 0.727 | 0.782 | 0.760 | 0.583 |
| 0.35 / 0.00 | 0.727 | 0.782 | 0.756 | 0.625 |
| 0.45 / 0.05 | 0.722 | 0.753 | 0.749 | 0.625 |
| 0.35 / 0.05 | 0.722 | 0.738 | 0.742 | 0.667 |

## What works, and what does not

**The prior fires.** At the neutral setting 134 of 856 questions get a different
hit list, and not one of them is a reordering of the same documents — these are
genuinely new documents entering the top 5. The mechanism is wired correctly;
the parity test and the `--no-prior` control confirm the off state is baseline.

**The floor knob does almost nothing.** 0.35 and 0.30 produce identical numbers.
Lowering the admission threshold lets more scene members into the candidate set
but does not change their score, so they rarely reach the top 5.

**The boost knob does everything, and all of it is harmful.** Every arm with
`boost > 0` costs 7 to 15 points of recall@1. A flat additive bonus is applied
without reference to the spread of the underlying scores, so it lifts scene
members over hits that are substantively better.

**The exchange rate is the real finding.** Tracking what happens to the 47
reachable misses:

| Arm | reachable misses recovered | other questions broken |
| --- | --- | --- |
| 0.35 / 0.00 | 1 of 47 | 1 |
| 0.45 / 0.05 | 4 of 47 | 17 |
| 0.35 / 0.05 | 8 of 47 | 27 |

A stronger prior does recover more of what the ceiling promised — and destroys
more than it recovers, in every setting tested. The ceiling assumes an admitted
gold memory lands in the top 5, but admission costs a slot, and the displaced
baseline hit is right more often than the admitted scene member. That is a
property of the mechanism, not of the knob values: no point on this grid, and by
the monotone trend no point between them, trades favourably.

### Flip examples

Questions are keyed by a hash of their text; question text and gold document
titles are withheld because the eval set is private. `rank 0` means the gold
memory was not in the top 5.

Neutral arm (0.35 / 0.00), both directions complete:

| Question | Type | Rank before | Rank after |
| --- | --- | --- | --- |
| Q-fdd02df4 | voorkeur | 0 | 4 |
| Q-b5e6c5f3 | procedure | 5 | 0 |

Strongest arm (0.35 / 0.05), all 8 gains and 20 of the 27 losses:

| Gained | Type | Before | After | | Lost | Type | Before | After |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q-ede836ea | feit | 0 | 2 | | Q-9cbb3a81 | feit | 1 | 0 |
| Q-ea6c4f47 | voorkeur | 0 | 1 | | Q-041fbc57 | feit | 2 | 0 |
| Q-fdd02df4 | voorkeur | 0 | 3 | | Q-f6cd4602 | feit | 5 | 0 |
| Q-f75f7ae5 | beslissing | 0 | 1 | | Q-a013be9c | feit | 4 | 0 |
| Q-2d603451 | procedure | 0 | 1 | | Q-f49de9d7 | feit | 3 | 0 |
| Q-28c65216 | feit | 0 | 1 | | Q-e12bac07 | feit | 4 | 0 |
| Q-3f504e4d | procedure | 0 | 1 | | Q-336b7ccc | procedure | 5 | 0 |
| Q-c2523541 | feit | 0 | 2 | | Q-3a63c387 | feit | 5 | 0 |
| | | | | | Q-8719a949 | procedure | 5 | 0 |
| | | | | | Q-e4a0f752 | beslissing | 1 | 0 |
| | | | | | Q-b5e6c5f3 | procedure | 5 | 0 |
| | | | | | Q-957add17 | feit | 2 | 0 |
| | | | | | Q-b74ed0d4 | beslissing | 5 | 0 |
| | | | | | Q-6cb98a83 | procedure | 4 | 0 |
| | | | | | Q-321b043a | procedure | 5 | 0 |
| | | | | | Q-2e871e1e | feit | 2 | 0 |
| | | | | | Q-d9038753 | procedure | 2 | 0 |
| | | | | | Q-9dc3535d | feit | 5 | 0 |
| | | | | | Q-4f1e1a82 | feit | 2 | 0 |
| | | | | | Q-77f90faa | procedure | 2 | 0 |

Read the loss column carefully: `Q-9cbb3a81` and `Q-e4a0f752` were at **rank 1**
before the prior, and `Q-041fbc57`, `Q-957add17`, `Q-2e871e1e`, `Q-d9038753`,
`Q-4f1e1a82` at rank 2. The prior does not merely fail to promote weak answers,
it evicts answers that were already the top hit. Gains, by contrast, mostly
arrive at rank 1-3 — the prior is decisive when it fires, in both directions.

**Latency.** The prior costs roughly 65 ms p50 (95 ms to 160 ms) on a warm query
cache. The design's "+<5 ms" criterion is not meaningfully testable at this
baseline; the honest statement is that the prior adds two thirds to the memory
recall path for no gain.

## Clusterer 2: tags — not measurable on this vault

```
memory files 1620   with a non-empty tags field: 0
```

`cluster_tags` groups by the rarest shared tag within a rolling window and drops
untagged notes, so it produces zero scenes here. This is a data fact, not a code
fault: the memory writer does not populate `tags`. The arm was not run.

## Clusterer 3: llm — the model does not perform the task

Fixed first: `build-scene-index.py` called `_llm.complete`, which does not
exist (`_llm` exposes `generate`). That was an `AttributeError`, not a fail-open
path, so the arm would have crashed rather than degraded.

With that corrected, on `gemma4:12b` via Ollama:

| Run | Wall time | Answer | Parsed scenes |
| --- | --- | --- | --- |
| `generate`, 120 s timeout, cold model | 70.1 s | none | 0 |
| `generate`, 900 s timeout, cold model | 42.1 s | none | 0 |
| `generate`, 300 s timeout, warm model | 39.8 s | 3100 chars | 0 |

The prompt lists all 1508 notes: 128772 characters, roughly 32k tokens, and the
model is asked to assign every id to exactly one of at most 15 scenes. The warm
run does answer — with Dutch prose and markdown headings summarising the corpus,
containing no `{` at all. `cluster_llm` finds no JSON, returns `{}`, and the
builder writes zero scenes. Fail-open works as designed; the clusterer produces
nothing.

3100 characters of output against ~1508 ids that must be echoed is about 5% of
the required volume. The model summarises instead of assigning, which is the
expected behaviour when the task does not fit the effective context window. The
conclusion is not "the LLM approach is wrong" but "a single-shot, full-corpus
prompt is not feasible at this corpus size with a local 12B model". A chunked
formulation was deliberately not built: this task measures three clusterers, it
does not build a fourth.

Note also the capacity arithmetic: 15 scenes over 1508 memories is ~100 members
per scene, against community's median of 3. Even a perfectly obedient model
would produce scenes that act as a global floor change in disguise.

## Winner rule

All four conditions were required on dev. The best arm (0.35 / 0.00):

| Criterion | Required | Measured | Met |
| --- | --- | --- | --- |
| recall@5 | >= +0.02 | +0.000 | no |
| recall@1 | not lower | -0.006 | no |
| p50 latency | +<5 ms | +65 ms | no |
| gain in >= 2 of 4 memory_type groups | yes | 1 of 4 (voorkeur only) | no |

No arm qualified. Per the protocol the holdout split and
`kb-memory-eval-set-v2.json` were **not** run: they exist to confirm a winner,
and spending them on a null result would burn them for later work.

## Decision

`scene_retrieval` stays off by default. The scene layer is left in the tree
behind its toggle: the store, the three clusterers, the diagnostics and the
experiment driver are all reusable, and the oracle-ceiling tooling is the cheap
gate that should precede any future retrieval idea.

If this is revisited, the evidence points at one thing: the problem is not
*finding* related memories — the ceiling says 47 recoverable misses are sitting
right there — but *admitting* them without evicting something better. That is a
question about the ranking function, not about clustering. A prior that reorders
within an unchanged candidate set, or that expands k rather than substituting
members, is the shape worth testing next.

## Reproduction

Raw per-arm JSON is **not** committed: it contains per-question results derived
from the private memory eval set (see `tests/test_eval_privacy.py`). The flip
tables above therefore withhold question text and gold document titles, and key
each question by a hash of its text instead; rank changes and memory types carry
no vault content. The raw files live outside the repo alongside the eval sets.

```bash
python3 scripts/build-scene-index.py --clusterer community --json
python3 scripts/scene-report.py --total 1508 --baseline arm-off.json --json
python3 scripts/scene-experiment.py --set dev.json --out arm-off.json --no-prior --cache q.json
python3 scripts/scene-experiment.py --set dev.json --out arm.json \
    --clusterer community --floor 0.35 --boost 0.00 --cache q.json
```

## Method notes worth carrying forward

1. **Two baselines around the arm sequence.** The first run of this experiment
   showed a "+0.004 gain" that turned out to be the corpus growing between runs.
   A second baseline after the arms costs one run and converts that class of
   illusion into a measured zero.
2. **A cold embedding model looks like a broken feature.** Two arms returned
   "embedding backend unreachable" and would have silently measured baseline had
   the driver not failed loudly.
3. **Pausing background automation destroyed the index.** Turning off
   `embed_index` and `memory_capture` made `build-kb-index.py::_collect()` return
   nothing, and `prune(keep_paths=set())` deleted all 1707 documents. Three arms
   ran against an empty index and produced plausible-looking negative numbers
   (0.016, 0.000, 0.000) before the cause was found. Filed as TASK-136; the index
   was rebuilt from the embedding cache with zero model calls.

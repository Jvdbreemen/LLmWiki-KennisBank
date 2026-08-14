# Which factor costs the recall: recency, mostly

**2026-08-14 — 856-question dev split, 1740 current memories, `ollama:qwen3-embedding:4b`**

TASK-138 established that discarding `_rank.rerank` entirely more than doubles
recall@1 (0.264 → 0.557, McNemar 272 gained / 21 lost). This decomposes that
loss by neutralising one factor at a time and re-running the production path.

Nothing is reimplemented. An arm is `_rank.<factor>` patched to return 1.0, so
every number comes from the code that actually runs.

## Results

| arm | recall@1 | recall@5 | gained@1 | lost@1 | p |
| --- | --- | --- | --- | --- | --- |
| production | 0.2640 | 0.7243 | — | — | — |
| **no recency** | **0.4112** | 0.7652 | 146 | 20 | < 1e-6 |
| no importance | 0.3178 | 0.7593 | 71 | 25 | 3e-6 |
| no trust | 0.2640 | 0.7243 | **0** | **0** | 1.0 |
| no usage | 0.2605 | 0.7266 | 10 | 13 | 0.68 |
| no noise | 0.2640 | 0.7243 | **0** | **0** | 1.0 |
| only recency | 0.3201 | 0.7593 | 78 | 30 | 4e-6 |
| **all neutral** | **0.5572** | 0.7734 | 272 | 21 | < 1e-6 |

**The control passed.** Neutralising every factor reproduces the raw-cosine
ordering on all 856 questions — zero differences. So nothing outside these
factors reorders, and the decomposition is complete rather than merely
plausible.

## Recency carries half of it

Removing recency alone recovers **+0.147** of the total **+0.293**, or 50%.
Importance is second at +0.054 (18%). Usage is indistinguishable from noise
(10 gained against 13 lost, p = 0.68).

`recency_factor` is exponential decay with a 365-day half-life for most types,
floored at 0.6. So a memory from a year ago is multiplied by 0.5 and one from
today by 1.0 — a 40% swing.

## Why a 40% swing is enough to overwrite the ranking

RRF scores rank *r* at `1/(60+r)`. Rank 1 and rank 2 therefore differ by 1.6%,
rank 1 and rank 10 by 13%. The factors span:

| factor | range | |
| --- | --- | --- |
| recency | 0.6 – 1.0 | 40% |
| importance | 0.9 – 1.1 | 20% |
| trust | 0.95 – 1.05 | 10% |
| usage | 1.0 – 1.1 | 10% |

Every one of them is larger than the gap between adjacent ranks. These are not
tie-breakers applied to a ranking; they are large enough to replace it. A
document at rank 8 with a 1.0 recency beats one at rank 1 with 0.6.

The case from TASK-138 measured concretely: the gold memory had a cosine 0.245
higher and still lost, on a 3.4% relative swing against a 1.6% rank gap.

## Two factors do literally nothing, for a structural reason

`no trust` and `no noise` produce byte-identical results to production — zero
flips, at both k=1 and k=5. That is not because they are neutral. It is because
they are **uniform**:

    evidence_basis of all 1732 current memories: {"agent": 1732}

`trust_factor` returns 0.95 for every memory in the vault, and a constant
multiplier cannot reorder anything. It is dead weight until the vault contains
human-typed or imported memories, at which point it starts working without
warning. The same holds for `noise_factor`: nothing is marked noisy, so it is 1.0
everywhere.

Worth knowing before anyone tunes them: measuring `trust_factor` on this corpus
would report "no effect" forever, and that reading would be wrong the moment a
`getypt` memory appears.

## The factors compound

Individual removals do not add up to the joint removal:

    no recency        +0.147
    only recency      +0.056   (i.e. removing everything else)
    ------------------------
    sum               +0.203
    all neutral       +0.293
    ------------------------
    interaction       +0.090

The factors multiply, so their distortions compound. Nearly a third of the
total loss exists only when they are combined, which means tuning them one at a
time will under-measure what removing them together is worth.

## What this does not settle

The eval set is generated one question per document, so questions are
paraphrases of their gold memory. That structurally favours similarity and
structurally penalises recency — which exists precisely to prefer a fresher
memory over a better-worded older one. **This measurement cannot see the case
recency was built for.**

So: recency is unambiguously what costs recall *on this metric*, and this
metric is the one that would say so even if recency were working perfectly.

## What to do

1. **Do not neutralise recency on this evidence.** The finding is strong and the
   metric has picked a side.
2. **Build a set that can see freshness.** Questions where the correct answer is
   the *newest* of several matching memories. Until one exists, no ranking
   decision here is decidable.
3. **Consider the floor rather than the factor.** `RECENCY_FLOOR = 0.6` allows a
   40% swing against RRF gaps of 1.6%. Raising the floor to, say, 0.9 would keep
   the preference for fresh knowledge while stopping it from overwriting the
   ranking outright. That is a tuning question a freshness-aware set could
   actually answer.
4. **Leave trust and noise alone**, and record that they are inert here — a
   future measurement will otherwise "discover" the same non-effect.

## Reproducing

```bash
python3 scripts/rank-factors.py \
    --set <vault>/06-claude/kb-memory-eval-set.json \
    --cache q.json --out factors.json
```

Each arm is one retrieval pass over the cached query vectors, roughly two
minutes. Absolute numbers do not travel across an index rebuild or a date
boundary — `_rank` is day-granular — so every comparison here is within one
index state on one day.

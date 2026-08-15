# The reranker is already there, and it is losing

**2026-08-14 — 856-question dev split, 1740 current memories, `ollama:qwen3-embedding:4b`**

TASK-138 asked for the ceiling of reranking the top-20 memory candidates before
building anything. The ceiling is worth having. It is not the headline.

The headline is that re-sorting the *existing* candidate pool by raw cosine —
discarding the recency, importance and usage re-weighting that production
applies — more than doubles recall@1 and beats recall@5, at zero cost.

| dev split, 856 questions | recall@1 | recall@5 |
| --- | --- | --- |
| production ranking | 0.264 | 0.724 |
| **same pool, sorted by cosine** | **0.557** | **0.773** |
| perfect reranking of the pool (ceiling) | 0.844 | 0.844 |

McNemar, exact, paired per question:

| | gained | lost | p |
| --- | --- | --- | --- |
| hit@1 | **272** | 21 | < 1e-6 |
| hit@5 | 52 | 10 | < 1e-6 |

272 questions against 21 is not a tie that averaging hid. It is a rout.

## Where the loss comes from, attributed rather than guessed

The memory layer has **no lexical arm** — `_kbindex.search` documents that
choice and the measurement behind it. So RRF fuses a single ranking, and
reciprocal-rank fusion over one ranking is order-preserving: `1/(60+rank)` is
monotone in rank. **The RRF order and the cosine order are therefore the same
order.**

Everything that separates the production result from the cosine result is
`_rank.rerank`, which multiplies the score by recency × importance × usage.
Nothing else can be responsible, because nothing else differs.

A single case makes the mechanism concrete. For *"Waarom is een push-hook
betrouwbaarder dan een pull-mechanisme?"*:

    rank 1   cos 0.460   "Hook-schrijven op het hete pad"        (2026-08-07)
    rank 2   cos 0.705   "Pull vs Push mechanismen"              (2026-07-02)  <- gold

The gold answer has a cosine 0.245 higher and still ranks second, because the
other memory is five weeks newer.

## The ceiling, since it was asked for

Computed on the pool production actually retrieves — same floor, same layer
filter. A perfect reranker puts gold at rank 1 whenever gold is in the pool, so
ceiling@1 and ceiling@5 are the same number.

| pool | ceiling | |
| --- | --- | --- |
| top-5 | 0.724 | equals baseline recall@5 by construction |
| top-20 | **0.844** | |
| top-50 | 0.858 | barely above top-20 |

Cosine-only sorting already captures **51% of the available headroom at k=1**
and 41% at k=5, for nothing.

**Rank when gold is found: median 2, p90 7.** A reranker does not have to be
excellent here. It has to be better than a factor that actively demotes the
right answer.

## The floor is the binding constraint on the pool, not the top-k

Asking for 50 candidates returns a median of **13**. Only 60 of 856 questions
got a full 50. `MEMORY_MIN_COS = 0.45` cuts the pool long before the top-k does,
which means "a top-20 reranker" is in practice a top-13 reranker, and top-50 is
nearly the same measurement as top-20.

Running the same measurement with the floor removed separates the two effects:

| | production floor 0.45 | no floor |
| --- | --- | --- |
| pool size, median | 13 | 50 |
| gold absent from pool | 122 | **59** |
| ceiling, top-20 | 0.844 | 0.886 |
| baseline recall@5 | **0.724** | 0.715 |

The floor is doing two opposite things at once. It costs 63 questions of
reachability — gold memories that exist in the index but sit below 0.45 — and
it *improves* the top-5 result, because dropping weak candidates changes what
the fusion promotes. Any change to it has to be measured on both effects, not
one.

## Latency

Measured over 200 dev questions with a warm query-vector cache, so the
embedding cost is excluded — it is identical for both arms and would swamp the
difference.

| | p50 | p95 |
| --- | --- | --- |
| retrieval (identical for both arms) | 140.7 ms | 199.0 ms |
| the cosine re-sort itself | 12.6 µs | 28.9 µs |

The arm adds 0.015 ms to a 145 ms path — four orders of magnitude below the
thing it changes. It is a sort key over a median of thirteen items, not a
component, which is also why it has no failure mode to fail open from.

Run-to-run spread is not stated per arm, because both arms share one retrieval
and the difference between them is below measurement noise. What does move
between runs is the retrieval itself, and the earlier scene work established
why: `_rank` is day-granular, so absolute numbers do not travel across a date
boundary or an index rebuild.

## Threat to this conclusion, stated plainly

**The eval set is generated one question per document.** Each question was
written from the memory it is expected to retrieve, so questions are close
paraphrases of their gold document. That structurally favours pure semantic
similarity and structurally penalises recency and importance, which exist to
serve a different goal: when a user asks something, the freshest and most
important memory is often the one they want, even when an older one matches the
words better.

This measurement cannot see that goal at all. It can only see "find the
document this question was written from".

So the finding is strong and the metric is biased toward it. That is not a
reason to dismiss the result — a factor that costs 272 questions against 21 on
any reasonable metric deserves scrutiny — but it is a reason not to flip the
default on this evidence alone.

## Decision

**Do not build a reranker yet.** The gate this task set was "measure the ceiling
before building", and the measurement says the first problem is not a missing
component but an existing one that hurts.

Three steps, cheapest first:

1. **Decompose `_rank.rerank`.** Recency, importance and usage are three
   factors; measure them separately on this same cached pool. It is minutes of
   work now that the query vectors are cached, and it turns "the re-weighting
   loses" into "this factor loses".
2. **Build an eval that can see what recency is for.** Questions generated from
   a document cannot measure whether the newest memory was the right answer.
   Until such a set exists, every ranking decision is being made on a metric
   that has already picked a side.
3. **Only then consider an LLM reranker.** The remaining headroom after cosine
   sorting is 0.287 at k=1 — real, but the cheap fix captures half of it at no
   latency, and the hot path has a sub-second budget.

What did not work, recorded because it is part of the answer: nothing was
built, so nothing failed. The measurement cost about ten minutes of model time
and replaced a planned implementation with a smaller and better-targeted one.

## Reproducing

```bash
python3 scripts/rerank-ceiling.py \
    --set <vault>/06-claude/kb-memory-eval-set.json \
    --split dev --pool 50 --out ceiling.json --cache q.json
# and, to separate the floor from the ranking:
python3 scripts/rerank-ceiling.py --set ... --min-cos 0.0 --cache q.json
```

Query vectors are cached and keyed by embedding-model identity, so the second
run costs no embedding time and a model change discards the cache rather than
mixing vector spaces. Absolute numbers do not travel across an index rebuild or
a date boundary — `_rank` is day-granular — so every comparison here is within
one index state on one day.

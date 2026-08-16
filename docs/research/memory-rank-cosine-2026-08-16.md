# Ordering memory recall by cosine — pre-registration

**2026-08-16 — TASK-162 (ranking half). Committed before the changed code is
measured; the Results section is empty on purpose.**

## Why now

Three independent measurements, three instruments, one direction:

1. **TASK-138** (1224-question set): re-sorting the production pool by raw
   cosine more than doubles recall@1 (0.264 → 0.557; paired +272 −21,
   p < 1e-6). Caveat then: the set's questions paraphrase their answers, which
   structurally favours similarity.
2. **TASK-161, newest-wins** (the slice recency exists for): production 0.286
   recall@1 against cosine 0.357, paired 2−1, p=1.0. On its own home ground the
   recency weighting does not win.
3. **TASK-169, oldest-wins** (after healing): with correct older answers
   finally in the pool, production buries them — 0.333 against cosine 0.600 at
   recall@5, paired at rank 1 cosine gains 2, loses 0.

The first measurement alone was "strong result, biased metric". The bias
objection has now been tested on the set built to embody it, and did not
survive.

## The change

`_rank.rerank` currently multiplies a memory hit's RRF score by recency,
importance and trust factors. RRF gaps between adjacent ranks are 1.6%; the
recency factor alone swings 40% (floor 0.6). The factors do not nudge the
order, they own it — and all three measurements say they own it wrongly.

New behaviour, shipping exactly the arm that was measured:

- **Memory hits are ordered among themselves by raw cosine.** No recency,
  importance, trust, usage or noise multipliers in the memory ordering.
- **Their score values keep the layer's existing multiset** (the ordered RRF
  scores are reassigned to the cosine order), so mixed-layer callers
  (`kb-mcp`, `kb-ask`, `kb-presearch`) see the same interleaving positions for
  the memory layer as before — only *which* memory occupies them changes.
- **Wiki hits are untouched**, including their usage boost and coupling.
- The similarity floor, the status filter and everything upstream stay as
  they are.

The factor functions stay in `_rank` — they carry telemetry value and the
measurement harnesses reference them — but they no longer shape the memory
order.

## The rule, fixed before any number

Gate A — the 1224-question memory set (baseline measured 2026-08-16:
recall@1 0.234, @3 0.590, @5 0.758):

- recall@1 must improve by **at least +0.15 absolute**, and
- recall@5 must not drop below **0.758**.

Gate B — the freshness dev half (baselines: newest-wins r@5 0.643 production;
oldest-wins r@5 0.333 production):

- oldest-wins recall@5 must reach **at least 0.500**, and
- newest-wins recall@5 may lose **at most one question** (≥ 0.571).

Gate C — the holdout, which has never been run, is run **once**, after A and B
pass, with both arms paired in that single run:

- the new ordering's recall@5 must be **≥ the old production ordering's** on
  both slices, and **strictly better on at least one**.

Fail any gate and the change does not ship, and this document says so with the
numbers. TASK-145's pre-registered rule failed and was reported; that is the
precedent and the promise.

## Results

**Gate C failed. The change does not ship.**

| gate | requirement | measured | verdict |
| --- | --- | --- | --- |
| A — 1224-question set | @1 ≥ +0.15; @5 ≥ 0.758 | @1 **+0.313** (0.234 → 0.547); @5 0.758 → 0.758 | PASS |
| B — freshness dev | oldest r@5 ≥ 0.500; newest r@5 ≥ 0.571 | oldest **0.600**; newest **0.571** (exactly the boundary) | PASS |
| C — holdout, one shot | new r@5 ≥ old on BOTH slices | oldest 0.500 → 0.618 (**+0.118**); newest 0.364 → **0.273** (−0.091) | **FAIL** |

On the holdout's eleven newest-wins questions the cosine ordering loses one
question at rank 5 that the old production ordering kept. Four questions are
gained on oldest-wins; the net over 45 questions is +3. The rule did not ask
about the net — it required no loss on either slice, precisely so that a gain
on one side could not buy a loss on the other. It was set with the sample
sizes known. It fails, so the code is reverted, and this section records that
instead of adjusting the rule to fit.

### What the failed run still bought

- The holdout also measured the *old* ordering for the first time on questions
  it never tuned on: newest-wins r@5 0.364, oldest-wins 0.500. The production
  ranking is weak on its own favourite slice out of sample.
- The one-question loss sits in an 11-question slice. That is not an argument
  against the rule — it is the reason the next attempt needs a larger
  newest-wins pool before it can register a distinguishable gate. REPLACED
  pairs accrue naturally as v3-era supersessions accumulate.
- **This holdout is spent.** It has been seen; it can never again serve as an
  untouched gate. A future attempt must build a fresh one.

### Reconstruction note

The "old" arm was reconstructed offline from the same retrieved pool: the
memory layer has no lexical arm, so its RRF base order is the cosine order,
and the old ordering is base × recency × importance × trust from live
frontmatter. The usage boost and coupling bonus were not reconstructed;
TASK-160 measured the usage factor's contribution as near zero and the others
as inert. Rows in `holdout_results.json` beside the scratch harness.

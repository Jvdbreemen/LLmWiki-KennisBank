# Growing the memory corpus cost recall, and the pre-registered rule caught it

**2026-08-14 — after the first sweep under the raised caps (TASK-145)**

The rule was fixed before the numbers moved, in
`recall-baseline-2026-08-13.md`: **memory recall@5 must not fall below 0.778,
and wiki recall@5 must stay at 1.000.** recall@1 was allowed to give a little,
because the hook injects three memories rather than one.

Measured after the sweep:

| memory layer | baseline | after | delta |
| --- | --- | --- | --- |
| recall@1 | 0.322 | 0.266 | **−0.056** |
| recall@3 | 0.662 | 0.619 | −0.043 |
| **recall@5** | **0.778** | **0.768** | **−0.010** |
| MRR | 0.498 | 0.454 | −0.044 |

| wiki layer | baseline | after | delta |
| --- | --- | --- | --- |
| recall@1 | 0.842 | 0.854 | +0.012 |
| recall@3 | 0.997 | 1.000 | +0.003 |
| **recall@5** | **1.000** | **1.000** | held |
| MRR | 0.917 | 0.924 | +0.007 |

Same 1224 memory questions and 329 wiki questions as the baseline.

**The wiki half passes. The memory half does not.** recall@5 is 0.768 against a
floor of 0.778. The gate fails, and it fails by a margin worth twelve questions.
The recall@1 drop is much larger — 69 questions — and is far outside anything
that could be called noise.

## What grew

    current memories   1531  ->  1740   (+209, +14%)
    memory files       1907  ->  2389   (+482, measured before and after the run)
    transcripts read      7 of 89 pending

Only 209 of those 482 entered the recall set. The rest sit in `unverified`
quarantine and are not indexed, which is why the index holds 1946 documents
(206 wiki + 1740 current) while the folder holds 2389 files. So a 14% larger
haystack came from a run that read seven transcripts out of eighty-nine.

A note on how this was counted, because a first draft of this report said 617.
That figure came from counting memories with `created: 2026-08-13`, which spans
the whole day — including earlier sweeps — rather than this run. The run's own
output is the difference in file count measured immediately before and after it:
482. Counting by date answers a different question than the one asked.

## Why it dropped, and what the number does not say

The eval set is fixed. It asks 1224 questions about memories that existed
before this sweep, and the sweep added 209 competitors without adding a single
question they could answer. Retrieval has more candidates for the same slots, so
some right answers get pushed past k. That is dilution, and it is precisely the
mechanism TASK-145 was gated on: *"retrieve_top_n is 3, so multiplying the corpus
multiplies the competition for three slots. A fact that is captured but ranks
fourth is exactly as invisible as one never captured."*

So the measurement is **one-sided by construction**. It prices the cost of a
bigger corpus and not the benefit, because the new knowledge is not in the
question set. A memory captured today that answers a question nobody asked in
the eval scores nothing here while being exactly what the sweep is for.

That does not rescue the number. The rule was set in advance for a reason, and
it was set on this eval set. Reporting it as passed because the metric is
imperfect would be choosing the interpretation after seeing the result.

## What follows

**Do not raise the caps further until ranking is addressed.** The intake fix
works — 482 memories from seven transcripts, against 99 from ten transcripts
before it — and that is the problem: the thing it fixed now presses on the next
constraint. Eighty-two transcripts remain pending, and each one makes the
haystack bigger at the current ranking quality.

**TASK-138 is the remedy and is already filed**: measure the ceiling for
reranking the top-20 memory candidates. Reranking restores precision at small k
without shrinking the corpus, which is the only direction that lets both
capture and recall improve at once. It moves from "worth doing" to "blocking".

**A better eval set is the second half.** The set cannot answer whether new
captures are useful, only whether they crowd. Questions generated from memories
written after the baseline would measure the other side of the trade, and until
that exists every corpus-growth decision is being made on half the evidence.

# Where the supersede window should sit, and what it will not fix

**2026-08-13 — 149 real `superseded_by` pairs, 1595 current memories, qwen3.5:4b**

The supersede window was set at cosine 0.85. This measures where the vault's own
supersessions actually sit, what the window costs at 0.75, and — the part that
changes the conclusion — how often the judge recognises a supersession once it
is inside the window.

Method: every memory with a `superseded_by` link, paired with its successor.
Vectors come from `kb-index.db` where available; closed memories are absent from
the index by construction and were embedded through the cache. Read-only
throughout. Ground truth is the vault's own recorded decisions, which is a
limitation, addressed at the end.

## Where the pairs sit

| | |
| --- | --- |
| pairs with both vectors | 149 |
| p10 | 0.759 |
| p25 | 0.804 |
| p50 | 0.864 |
| p75 | 0.999 |

Coverage by threshold:

| threshold | pairs inside | share |
| --- | --- | --- |
| above 0.95 | 43 | 29% |
| above 0.85 | 87 | 58% |
| above 0.75 | 141 | 95% |

**0.85 sees 58% of real supersessions; 0.75 sees 95%.** That is the case for
lowering it, and it is stronger than the earlier P1 measurement (70% / 93% on
101 pairs) suggested.

## Rank of the successor

Among all 1595 current memories, ranked by cosine to the closed memory:

| | |
| --- | --- |
| top-1 | 83.2% |
| top-2 | 96.6% |
| **top-3** | **98.0%** |
| top-5 | 100.0% |

`TOP_K` moves from 2 to 3: 96.6% to 98.0%.

Raising it further would buy nothing, and that is measurable rather than a
judgement call. Over all 1,271,215 pairs among the 1595 current memories,
neighbours above the 0.75 threshold are almost absent:

| | |
| --- | --- |
| median neighbours above 0.75 | 0 |
| p90 | 1 |
| p99 | 2 |
| **max** | **3** |
| memories with more than 2 | 6 (0.38%) |
| memories with more than 3 | 0 |

No memory in this vault has more than three neighbours above the threshold, so
`TOP_K = 3` shows the judge every neighbour there is. `TOP_K = 5` would be
indistinguishable from 3 on this corpus.

Note that the top-5 figure above answers a different question. It is the rank of
the successor among ALL memories; `similar_existing` filters by threshold first
and takes top-k second, so a successor at rank 4 that sits below 0.75 is
invisible at any `k`. The binding constraint is the threshold, not `k` — which
is the same conclusion the coverage table reaches from the other side.

## What the window does not fix

Inside the window, the judge is asked whether the newer memory replaces the
older. On pairs the vault already recorded as supersessions, it agrees:

| band | agreement | note |
| --- | --- | --- |
| 0.70–0.90 | 29/97 = **30%** | the band that matters |
| 0.90–0.95 | 2/7 = 29% | |
| above 0.95 | 0/43 = **0%** | near-identical; see below |

The 0% above 0.95 is exactly the contamination predicted before this ran. Those
pairs are almost the same text, the model answers "these are identical, so
nothing is being replaced", and that defensible answer scores as wrong. **No
future evaluation should score that band.**

The 30% is the real number, and it reframes the whole task. Search was never the
bottleneck: at a median rank of 1, the mechanism looks straight at the successor
and says no. Lowering the threshold triples what the judge is shown and cannot
make things worse — you cannot judge what you never see — but it will not
produce many more supersessions on its own.

Nor is 30% obviously a defect. `SUPERSEDE_SYSTEM` ends with "Bij twijfel: false",
a deliberate fail-safe chosen when a wrong closure was unrecoverable. This
measurement prices that choice: seven of ten real supersessions are left to a
human. What has changed underneath it is that a closure is now recorded and
reversible (`memory-doctor.py closed` / `reopen`, TASK-150), so the bias was
priced against a cost that no longer applies. Re-pricing it is TASK-156.

## Two limitations, stated rather than buried

**The ground truth is partly this mechanism's own output.** Many of the 149
supersessions were made by `supersede_pass` at 0.85 with the older prompt. So
"30% agreement" mixes disagreement-with-a-human and disagreement-with-an-earlier
version of itself, and this measurement cannot separate them. Only hand-labelling
a sample can.

**On the current corpus the threshold change is entirely inert, and that is
measured, not estimated.** Counting every pair with its volatility:

| threshold | candidate pairs | reaching the judge |
| --- | --- | --- |
| above 0.75 | 163 | **0** |
| above 0.80 | 50 | 0 |
| above 0.85 | 10 | 0 |
| above 0.90 | 3 | 0 |
| above 0.95 | 1 | 0 |

The volatility axis (TASK-146) skips any pair where either side is an event, and
1572 of the 1595 memories carry no label and therefore default to event. Not
"mostly skipped": every single pair, at every threshold. `supersede_pass` will
report zero on this corpus whatever the threshold is, until memories start
carrying labels — which happens as new captures come in, not retroactively.

That is the designed trade, and worth stating plainly so a zero in the heartbeat
is not later read as a broken guard. It also means the "163 candidate pairs,
roughly three minutes of judge time" figure describes what the threshold admits,
not what actually runs.

Both of those say the same thing in different words: this window is not the
self-correcting mechanism. Write-time reconcile is, and it only ever sees what
intake delivered.

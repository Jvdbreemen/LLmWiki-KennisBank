# Closing a memory now requires covering it — and 64 wrongly closed ones are back

**2026-08-16 — TASK-169. Prompt v3 for both closing judges, 64 adjudicated
NARROWED closures reopened, three validation arms.**

TASK-161's labelling put a number on an assumption nobody had tested: the
supersede machinery treats "newer statement about the same subject" as
"complete replacement", and of 237 historic closures only 11% actually replaced
substance while 27% NARROWED — the successor dropped facts whose only carrier
was the memory it closed. `recall_hits` filters on `status=current`, so those
facts were not ranked lower; they were unreachable.

Two changes, each with its own measurement.

## Change 1 — full coverage is now a condition of closing

Both judges that can close a memory — the write-time reconcile
(`RECONCILE_SYSTEM`) and the maintenance pass (`SUPERSEDE_SYSTEM`) — get the
same amendment to their question 2: a different value alone no longer closes
the old memory. Closing requires that the new one carries everything of lasting
value; partial coverage routes to ADD / `supersede: false`. Both prompts moved
to version 3, so every future closure in the closed-log is traceable to the
prompt that caused it.

**Validation: replay both prompt versions on all 209 adjudicated pairs** (the
64 NARROWED, where ground truth is *keep open*, and the 145 DUPLICATE, where
closing was fine). Historic behaviour is 100% closed by definition — these
pairs are in the set because they were closed.

| population | v2 closes | v3 closes | |
| --- | --- | --- | --- |
| NARROWED (64) — should stay open | 57.8% | **37.5%** | −20.3 points of knowledge loss |
| DUPLICATE (145) — may close | 34.5% | 26.2% | judge closes slightly fewer |

Read honestly: v3 is an improvement, not a solution — it still closes 37.5% of
the pairs a careful reader says it should keep. The asymmetry that makes this
acceptable: a wrong *keep* costs a duplicate in the pool, which dedup and the
exact-duplicate pass already handle without an LLM; a wrong *close* costs
knowledge. The duplicate-cleanup pressure never rested on this judge — the
write-time cosine dedup (0.92) and `exact_duplicate_pass` do that work — so the
26.2% is not the vault's duplicate defence weakening.

Also worth stating: v2 replayed at 57.8% on pairs it historically closed at
100%. The difference is the rest of the machinery — thresholds, windows,
dedup — closing what the judge alone would not. The judge was never the only
closer, which is why the prompt fix alone could never have been the whole
repair.

## Change 2 — the 64 wrongly closed memories are reopened

Reopen, not merge-forward, and the choice is an argument: NARROWED means the
successor dropped facts but did not contradict them (a contradicting pair was
labelled REPLACED and stays closed). The old memory is not wrong, it is more
complete, so `_memory.reopen()` (TASK-150) restores it losslessly and logs the
action. Merging forward would have an LLM rewrite the successor — the same
class of operation whose failure rate this task repairs, used as the repair.

Result: 64 of 64 reopened, 0 failed, exactly 64 files re-indexed. The 145
DUPLICATE closures were never touched.

**Validation arm 2 — the pre-registered gate.** The oldest-wins half of the
freshness set scores zero by construction until narrowed-away knowledge is
reachable again:

| oldest-wins (dev, n=30) | r@1 | r@3 | r@5 |
| --- | --- | --- | --- |
| before healing (both arms) | 0.000 | 0.000 | 0.000 |
| after — production | 0.100 | 0.233 | 0.333 |
| after — same pool, raw cosine | 0.167 | 0.500 | **0.600** |

The gate opened. And in opening, it measured the thing it was originally built
for: with the old memories finally *in* the pool, production's recency
weighting buries them — 0.333 against cosine's 0.600 at rank 5, paired at rank
1 cosine gains 2, loses 0. The brake question is answerable for the first time,
and the answer is that the recency factor overshoots exactly where a correct
older answer exists. That number belongs to TASK-162's file, and now it exists.

**Validation arm 3 — no regression.** The full 1224-question memory eval,
before and after healing: recall@1 +0.000, @3 +0.002, @5 +0.001, MRR +0.001.
Sixty-four reopened memories changed nothing for the questions that were
already answerable — they only added answers where there were none.

## What still protects the healed 64

The maintenance pass never re-closes them regardless of prompt: they predate
the volatility axis, an unlabelled memory counts as an event, and events are
never closed (v0.30.0's designed trade). The exposure is write-time reconcile
against a *future* candidate, at v3's measured 37.5% miss rate — and any such
closure lands in the closed-log with `promptversie 3` stamped in the reason,
which is what makes the rate auditable instead of silent.

## Suite

1436 passed, 2 skipped, including six new tests pinning the coverage condition,
the version bumps, the wire values, and TASK-144's question order surviving the
amendment.

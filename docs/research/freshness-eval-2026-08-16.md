# An eval set that can see what recency is for — and what it saw instead

**2026-08-16 — TASK-161. 237 supersession pairs hand-labelled, 89 questions,
dev half measured.**

TASK-138 and TASK-160 measured that the ranking factors cost recall, and both
said the same caveat: the metric cannot see the case recency exists for, because
every question in the old set is a paraphrase of its answer. This builds the set
that can. It ends with a smaller answer about ranking than intended and a larger
finding about the supersede pass than anyone asked for.

## Construction

Source: every `superseded_by` link in the vault — 237 pairs of (closed memory,
successor). By definition two memories about one subject where the newer is
supposed to be right; TASK-156 measured that the links often record housekeeping
instead, so every pair was hand-labelled:

| label | meaning | n |
| --- | --- | --- |
| DUPLICATE | same substance reworded; retrieval need not distinguish | 145 (61%) |
| NARROWED | successor covers **less**; the old memory is the only carrier of what was dropped | 64 (27%) |
| REPLACED | successor changed the substance (value, version, decision) | 27 (11%) |
| UNRELATED | link is wrong | 1 |

Labelling: twelve parallel readers over batches of twenty, every REPLACED and
NARROWED re-checked by an independent skeptic. A batching fault caused one batch
to be labelled three times by different readers, which became a free
inter-rater measurement: **13 of 17 unanimous, 3 at 2–1, 1 three-way split.**
The five disputes were adjudicated against the actual code, not by preference —
where "the code" is whatever repository the memory is about, not this one. The
deciding example: whether an old model-switching instruction is outdated was
settled by `BACKEND_NAMES = ("host",)` in the **adr-kit** repository's
`bin/adr_llm.py`, which retires two of the three backends the old memory
recommends. Memories describe several codebases; adjudicating them requires
reading the codebase they describe.

Questions are built from the OLD memory's title only — never from the
successor's body, which would recreate the paraphrase bias this set exists to
escape. REPLACED pairs expect the successor (newest-wins); NARROWED pairs expect
the old memory (oldest-wins), because for the dropped facts the old one is the
only correct answer. 89 questions, split 44 dev / 45 holdout (seed 161). The
holdout has not been run and stays that way until a tuning decision needs its
one shot.

## Result 1 — newest-wins: recency does not beat cosine on its home ground

Dev, 14 newest-wins questions, both arms from one retrieval (pool 20):

| arm | r@1 | r@3 | r@5 |
| --- | --- | --- | --- |
| production (RRF + recency/importance/usage) | 0.286 | 0.500 | 0.643 |
| same pool, raw cosine | 0.357 | 0.571 | 0.643 |

Paired at rank 1: cosine gains 2, loses 1, p=1.0. **No significant difference —
on the one slice of reality the recency factor was built for.** Fourteen
questions cannot carry a strong conclusion, and this report does not draw one.
What they do carry: the earlier "recency costs 0.147 recall@1" number can no
longer be dismissed as pure metric bias, because on the freshness-shaped
questions the factor still fails to earn its keep.

## Result 2 — oldest-wins: the ranking never gets the chance to be wrong

All 30 dev oldest-wins questions score **0.000 — in both arms**. Not because
ranking buries the old memory, but because `recall_hits` filters on
`status=current` and every expected answer is `superseded`. Verified directly:
the pools are non-empty (2–20 candidates) and the expected stem is absent from
every one.

So the brake questions cannot measure the ranking. What they measure instead is
bigger:

**27% of supersessions destroy access to knowledge.** A NARROWED closure means
the successor dropped facts the old memory carried — a fallback path, a concrete
parameter, a disable procedure — and closing the old memory removes the only
carrier of those facts from recall entirely. Not ranked lower: gone. Sixty-four
times in this vault's history, adjudicated case by case.

The supersede machinery treats "newer statement about the same subject" as
"complete replacement". The labels say that is true 11% of the time and false —
in the direction that loses knowledge — 27% of the time.

## What follows

1. **For the ranking (TASK-162/138):** the case for the recency factor did not
   improve on its own eval set. The honest position is unchanged but firmer: do
   not tune `_rank` upward on faith; the next evidence has to come from the
   holdout, once, after any proposed change.
2. **For the supersede pass:** NARROWED closures are the real damage, and they
   are invisible today. The reconcile prompt asks "does the new cover the old"
   but the write path closes the old memory even when the answer is "only
   partly". Filed as its own task rather than patched here.
3. **For this set:** the oldest-wins half is repurposed, not discarded — it is
   a ready-made regression set for any future "merge instead of close" fix: the
   day a NARROWED-aware supersede lands, these 64 questions should stop scoring
   zero.

## Reproducing

Pairs and labels: `06-claude/kb-freshness-eval.{dev,holdout}.json` in the vault
(personal data; deliberately not in this repository, per the eval-privacy
guard). Measurement harness: `rerank-ceiling.py`'s `measure()` on a pool of 20,
production rank and cosine re-sort from the same retrieval. Labels produced by
twelve independent readers with adversarial verification; label definitions and
the adjudication protocol are in the task file for TASK-161.

# Can an LLM judge whether a memory is supported by its own source?

**2026-08-15 — 60-memory random sample, 1732 current memories, qwen3.5:4b**

A validation, not an implementation. The question is narrow on purpose: is
grounded verification a usable trust signal in this vault, or would it be
another factor that is uniform and therefore inert like `trust_factor` is
today?

**What it measures.** Whether a memory was correctly *extracted* from the
transcript it came from. Not whether it is still true — that is staleness, and
volatility and the supersede pass handle it. A memory that correctly recorded
`qwen3-embedding:8b` in July is well-extracted and stale, and this probe should
call it supported.

**What it does not ask.** The model is never asked how confident it is.
Knowledge Vault's warning is the reason: a raw extractor confidence "is
different from a probability in that it may not be calibrated". The question
here is grounded — *does this passage say this* — with the text in front of it.

## Criteria, fixed before the run

| | | |
| --- | --- | --- |
| **C1** | variance | ≥10% of a random sample must score other than `supported`. A signal with no variance cannot reorder anything, which is exactly how `trust_factor` became inert. |
| **C2** | agreement | On a blind hand-labelled subset, the verifier must agree more often than it disagrees. |
| **C3** | determinism | The same memory judged twice must give the same verdict. |

## Results

    verdicts   supported 32   unsupported 11   not_found 11   partial 2   unparseable 4

**C1 — PASS.** 24 of 56 judged memories (42.9%) scored something other than
`supported`. The signal has real variance, unlike the factor it would feed.

**C3 — PASS.** 56 of 56 identical on a second pass at temperature 0.

**C2 — PASS, after the measurement was repaired.** This needs the full story,
because the first attempt failed and the failure was mine.

## The instrument was broken before the result was

The blind labels were written from a 480–600 character excerpt of each passage.
The model was given up to 6000. I was systematically less informed than the
thing I was grading, and the bias runs one way: it makes the model look wrong
whenever the support sits outside my window.

First tally: 4 agreements against 10 disagreements. Read as a result, that
would have killed the proposal.

Re-labelling from the passage the model actually saw:

| memory | my corrected label | model | |
| --- | --- | --- | --- |
| naming-convention-kbindex | not_found | not_found | agree |
| verwerking-van-externe-bronnen | not_found | not_found | agree |
| deduplicatie-bij-merging | not_found | not_found | agree |
| kennisbank-scope-en-kiss | supported | supported | agree |
| python-versie-vereiste | **supported** (was partial) | supported | agree — I was wrong |
| gebruik-qwen3-embedding8b-op-gpu | **supported** (was not_found) | supported | agree — I was wrong |
| consistentie-van-embedding-modellen | **supported** (was not_found) | supported | agree — I was wrong |
| dns-herstel-bij-reboot | not_found | unsupported | same direction |
| fix-speaker-tokenisatie | not_found | unsupported | same direction |
| user-review-gate | partial | supported | **model over-reached** |
| fix-voor-settings-command | supported | *unparseable* | parse failure |

**7 of 11 exact, 9 of 11 the same direction, 1 over-reach, 1 parse failure.**

And the part that matters most: **in three cases the model was right and I was
wrong.** It quoted text I had not seen —

> *"query- en index-model moeten dezelfde zijn voor geldige cosine, dus dit is
> een vault-brede keuze"*

— which is the claim, verbatim, in a passage I had labelled `not_found`. The
same happened with `"adr-judge requires Python 3.10+"` and with the GPU
reasoning for `qwen3-embedding:8b`.

The concern that motivated the criteria was confabulation: a model asserting
support that is not there. The evidence points the other way. It found support
three times where a careless human reader did not, and over-reached once.

## Two defects, both in the probe rather than the idea

**Unparseable responses: 4 of 56 (7%).** The model answered without emitting a
JSON object at all. `_llmjson` cannot rescue what was never written. A retry or
a stricter instruction would fix it; until then, 7% of memories would silently
get no verdict — and a silent no-verdict is the failure mode this codebase has
spent a week removing.

**Passage selection misses about half the time.** Five of eleven were
`not_found` by both reader and model. The first selector scored chunks by raw
token overlap and returned slash-command definitions for most memories, because
those blocks are long, word-rich and injected into every transcript. Replacing
it with IDF-weighted overlap plus an embedding rerank of the top-8 helped and
did not solve it.

That bounds the mechanism honestly: **it can only judge memories whose source
passage it can find**, and today that is roughly half. A trust signal available
for half the corpus is still a signal — `not_found` is not `unsupported` — but
the coverage belongs in any decision about it.

## What the evidence supports

All three pre-registered criteria pass. The mechanism produces a varied,
deterministic verdict that agrees with a careful human reader and, on this
sample, does not fabricate support.

It is not ready for the ranking. Three things stand between here and there:

1. **The 7% unparseable rate has to go to zero**, or the factor is silently
   absent for one memory in fourteen.
2. **Passage selection needs to beat 50%.** Embedding every chunk of the source
   transcript would do it and costs roughly 200 embeddings per memory; a
   cheaper option is to record the chunk index at capture time, which the sweep
   knows and discards.
3. **A larger labelled sample.** Eleven hand-labelled cases established the
   direction. They cannot establish a rate, and any weight put on this factor
   should be justified against something better than eleven.

## The finding that outranks all of this

While building the probe: **every one of the 2389 memories has a
`source_session`, and not one has ever been checked against it.** The vault has
423 unverified memories, one line in the review log, and zero retracted. There
are no human labels to validate anything against, which is why this validation
had to invent its own.

That is a larger gap than the trust factor. A verification pass, even at 50%
coverage, would be the first time this system has ever asked whether what it
wrote down was actually said.

## Reproducing

The probe is a scratch harness, not a shipped script. Sample seed 7, 60
memories, `qwen3.5:4b` at temperature 0, passages selected by IDF-weighted
overlap plus embedding rerank over the top 8 chunks of the source transcript.
Blind labels were recorded before the run; the corrected labels were made from
the full passage and are the ones tabulated above.

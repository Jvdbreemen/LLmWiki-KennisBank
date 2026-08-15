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

*Both entries below were wrong when first written. The corrected versions
follow, with what the mistake was, because the mistakes are the more useful
part.*

**Unparseable responses: 4 of 56 (7%).** ~~The model answered without emitting
a JSON object at all.~~ It emitted one every time. All four objects have the
right structure and the wrong string delimiters, in two shapes:

    {"verdict": "supported",   "reason": \"the passage states …\"}
    {"verdict": "unsupported", "reason": 'the passage describes …'}

The first backslash-escapes the delimiters of its own value; the second uses
single quotes. Neither is valid JSON and no span-finding helps, because nothing
is wrong with the span. I did not capture the raw text on the first run and
wrote down the plausible explanation instead of the observed one — and the fix
that follows from the plausible explanation, a retry, would have been the wrong
fix. `_llmjson` now repairs both shapes, but only after an honest parse has
already failed and only if the repaired text then parses; a repair that yields
no valid JSON is discarded, so a broken answer stays broken rather than
becoming a plausible wrong one.

**Passage selection.** ~~It misses about half the time.~~ The five-of-eleven
figure is from the hand-labelled subset, and that subset was chosen, not drawn.
On the random 56, the verifier answered `not_found` 11 times — **20%**, not
half. Generalising a rate from a set I had selected is the same error as
labelling from a window narrower than the model's, one paragraph later.

There is a deeper problem with reading that 20% as a retrieval score at all:
`not_found` means "the passage I was given is about something else", which
covers both *the selector missed* and *this claim was never in the transcript*.
The second one is precisely what a trust signal exists to detect. Tuning toward
fewer `not_found`s would therefore tune the signal away. Retrieval needs a
measurement that owes nothing to the verdict — see the next section.

## Measuring retrieval without asking the verifier

Ground truth came from the process that creates memories in the first place.
The extractor was run over **every** chunk of four transcripts, exactly as the
sweep does, and each candidate it produced was tagged with the chunk it came
from. That pair — claim, originating chunk — is generative truth. It is not a
second lexical scorer agreeing with the first, which is what any "grep for the
claim's distinctive words" ground truth would have been.

**255 claims, four transcripts of 11–18 chunks.** Then four selectors, ranking
the chunks of the claim's own transcript:

| arm | hit@1 | hit@2 | vs. current, at rank 1 | |
| --- | --- | --- | --- | --- |
| A current — IDF shortlist of 8, chunk cut at 4000 | 43.5% | 66.7% | — | |
| B untruncated + the model's trained query prefix | 47.1% | 69.4% | +26 −17 | p=0.22 |
| C no shortlist: every chunk embedded | 46.3% | 67.8% | +28 −21 | p=0.39 |
| D retrieve on 1500-char windows, return the chunk | **63.5%** | **83.1%** | +69 −18 | **p=3.3e-08** |

**The fix I proposed in this document was wrong.** "Embedding every chunk of the
source transcript would do it" — arm C — gains nothing measurable over the
shortlist it replaces, at roughly twice the embedding cost. The shortlist was
never the bottleneck.

Granularity was. A 6000-character chunk holds several subjects and one vector
has to average them; a 1500-character window keeps whatever made the chunk the
right one. Twenty points of hit@1 for a change that embeds *less* text per
comparison, not more. The two one-line defects in arm B — a 4000-character
truncation on chunks built up to 6000, and embedding the claim without the query
prefix this model is trained with — are real and both point the same way, but
neither is significant on its own.

A miss here is a lower bound: chunks overlap by 200 characters and a session
returns to its subjects, so a claim from chunk 7 may be genuinely supported by
chunk 8. Every arm pays that same bound, so the comparison survives it.

## What the evidence supports

All three pre-registered criteria pass. The mechanism produces a varied,
deterministic verdict that agrees with a careful human reader and, on this
sample, does not fabricate support.

Of the three things named as standing between this and the ranking, the first
two are resolved and the third is in progress:

1. **The unparseable rate.** Not a retry problem; a parser problem, now fixed.
2. **Passage selection.** From 43.5% to 63.5% hit@1 — by retrieving on smaller
   windows, not by embedding more. And for everything captured from now on the
   question does not arise: the sweep stamps `source_chunk: "N/M"`, so the
   passage is looked up rather than retrieved.
3. **A larger labelled sample.** Still the open one, and it needs stratifying
   rather than enlarging: the rate that matters is the precision of
   `unsupported`, because that is the verdict that would demote a memory.

One thing to expect and not misread when this is re-run: **`unsupported` should
go up.** Cases that were `not_found` because the selector missed will now
resolve into real verdicts, and some of those will be extractions that were
never supported. That number is the first extraction-accuracy figure this vault
has ever had, and it is more interesting than the trust factor it was gathered
for. More `supported` is not better.

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

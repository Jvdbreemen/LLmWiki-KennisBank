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

### `hit@2` was flattering every arm

The verifier caps its prompt at 6000 characters and a chunk runs to 6000, so
"the top two chunks" reaches the judge as the first chunk and a stump of the
second. Most rank-2 hits were never actually seen. The question is not which
ranking is best but: **given 6000 characters of passage, which selection is most
likely to contain the text the claim came from?** A window arm can spend that
budget in four places; a chunk arm spends all of it in one.

| selection, at a 6000-character budget | contains the source | vs. one chunk | |
| --- | --- | --- | --- |
| one chunk — the shape the probe actually used | 62.7% | — | |
| **best windows, 4 × 1500, wherever they fall** | **90.2%** | +70 −0 | p=1.7e-21 |
| IDF shortlist of 8 first, then windows | 87.8% | +70 −6 | p=6.3e-15 |

Strictly dominant: the window arm wins seventy cases and loses none. Coverage
goes from roughly three cases in five to nine in ten, at the same prompt cost,
because the budget stops being spent on one long stretch of mostly-irrelevant
transcript.

The shortlist is worth keeping despite being 2.4 points behind. It bounds the
work at about 40 embeddings per memory instead of ~990 on a 198-chunk
transcript, and on this machine the embedding round-trip *is* the cost. Two and
a half points for a twentyfold reduction is not a close call.

(The two runs share one arm — "one chunk" here is arm D at rank 1 — and it
reproduced within 2 of 255. Close, not identical; the arms were measured in
separate processes and nothing here rests on the difference.)

## Run 2: same memories, working parser, better passages

| | run 1 | run 2 |
| --- | --- | --- |
| supported | 32 | **49** |
| unsupported | 11 | 8 |
| not_found | 11 | **1** |
| partial | 2 | 1 |
| unparseable | 4 | 1 |

Paired over the 60 memories: 34 unchanged, and of the eleven run-1 `not_found`
cases seven became `supported` and three `unsupported`.

**The prediction in the section above was wrong.** `unsupported` did not go up;
it went down, from 11 to 8, and C1 variance fell from 42.9% to **16.9%**. Still
past the pre-registered 10%, with much less room. A large part of the original
distrust was the instrument, not the memories — which is the same lesson as the
four unparseables and the five-of-eleven, for the third time in one document.

The one remaining unparseable is a third delimiter shape: escaped delimiters
*and* a doubled closing quote *and* invalid `\'` escapes inside. `_llmjson` was
not extended to cover it. Two repairs grounded in observed data are worth
having; a third, chasing one case in sixty, is where a repair pass starts
inventing. It is counted as `unparseable` and reported, which is what the seam
is for.

## The two verdicts are not equally trustworthy

**`supported` does not fabricate.** The prompt asks the model to quote the
passage, and a quote is checkable, so all sixty verdicts were checked
mechanically rather than by hand. Thirty-one quotes are not verbatim — the
model reformats, joins lines, normalises whitespace — and for **every one of
them the quoted substance is in the passage**. Zero absent. It quotes loosely
and never invents.

**`unsupported` is wrong half the time.** All eight were adjudicated against
the *whole* transcript, not the passage. Four are correct. Four are memories
that are stated in the source, verbatim:

| memory | in the transcript |
| --- | --- |
| firmware-versieconsistentie | *"reports alpha.284 while HEAD is alpha.285. For honest receipts (device version == pushed code), I'll rebuild at current HEAD first, then flash"* |
| contextbeheer-via-bestanden | *"Everything you paste into a dispatch prompt … stays resident in your context for the rest of the session and is re-read on every later turn. Hand artifacts over as files"* |
| deduplicatie-bij-merging | the merge loop itself: `seen = set()` … `if n['id'] not in seen` |
| risico-op-informatielekkage | *"Gedistilleerde 'lessen' kunnen gevoelige bedrijfsinhoud bevatten zónder één pad of symbool"* |

**R1 = 4/8 = 50%**, Wilson 95% interval **22–79%**. Eight cases cannot pin a
rate, and the interval says so; but even its optimistic end means one demotion
in five is wrong.

### Why this is structural, not a tuning problem

The prompt offers `not_found` for "the passage is about something else
entirely". When the selector misses but lands on a *topically related* passage —
same transcript, same project, same afternoon — that description does not fit,
so the model correctly reaches for `unsupported` instead. **A retrieval miss and
a false claim are indistinguishable from inside the passage.** Only an
exhaustive search of the transcript separates them, and that is exactly what the
verifier does not do.

Three of the four false demotions are that. The fourth is a different mismatch:
for `risico-op-informatielekkage` the passage *states* the claim while giving no
argument for it, and the model judged whether the passage **justified** the
claim rather than whether it **said** it. For verifying extraction, said is
enough.

### What follows: raise trust, never lower it

The mechanism should feed the ranking in one direction only. `supported`
confirms a memory; every other verdict changes nothing. That is not a
compromise, it is what the evidence supports: the positive verdict is backed by
checkable quotes and no fabrication in sixty cases, and the negative verdict
cannot tell a retrieval failure from a false memory.

It also lands where this vault already stands — the human is the authority for
negative signals, and there is now a measured reason rather than a principle.

## What the evidence supports

All three pre-registered criteria pass, and the three blockers named in the
first version are answered:

1. **The unparseable rate.** Not a retry problem; a parser problem. 4 of 56 →
   1 of 60, and the survivor is counted rather than swallowed.
2. **Passage selection.** At the budget the judge actually gets, 62.7% → 87.8%
   coverage — by retrieving on *smaller* windows, not by embedding more. For
   everything captured from now on the question does not arise: the sweep
   stamps `source_chunk: "N/M"` and the passage is looked up. No memory carries
   that stamp yet; it applies to new captures, and backfilling would mean
   re-running the extractor over every transcript.
3. **A larger labelled sample.** Stratified rather than enlarged. The eight
   `unsupported` verdicts — the ones that would act — were adjudicated against
   the whole transcript, and all sixty verdicts were quote-checked
   mechanically.

**The recommendation is to use it, in one direction.** `supported` raises
trust. Nothing lowers it.

That is narrower than the factor this was gathered for, and it is the part the
evidence actually carries. `supported` is backed by quotes that check out, with
no fabrication in sixty cases. `unsupported` is right about half the time, and
its errors are not noise to be tuned away: a retrieval miss and a false memory
look identical from inside a passage, so the verdict cannot separate them at
any coverage short of exhaustive. For a system whose first duty is not to lose
what it correctly wrote down, a one-in-two — or even a one-in-five — false
demotion is not a rate to design around.

### The vault's first extraction-accuracy figure

Two of the sixty memories say something their source does not:

- **`hybride-dataverwerkingscyclus`** claims captures are merged *monthly*. The
  word appears nowhere in its transcript; the source says a daily pass.
- **`capaciteit-van-capture-mode`** claims a capacity of a million log lines.
  Neither "miljoen" nor "logberichten" nor "geheugen" occurs anywhere in its
  491k-character source.

**2 of 60 = 3.3%**, Wilson 95% interval **0.9–11.4%**. Wide, and worth stating
as a rate anyway, because it is the number that decides whether a verification
pass is worth running at all. One memory in thirty carrying a fact nobody said
is a real defect, and nothing in this system was looking for it before today.

Against that, `supported` was returned 49 times with **zero fabricated quotes**
(0/60, upper bound 6.0%). The verifier is more reliable than the extractor it
is checking, which is the condition under which checking is worth doing.

### A third of the corpus is a Dutch summary of an English source

The settings-watcher memory says *"de watcher monitort alleen mappen"* while
its source says *"it only watches directories that had a settings file when
this session started"*. Lexical overlap cannot bridge that — by construction,
not by tuning — and the IDF stage kept for cost is the lexical one.

Measured on the same 255 claims, by the language of the claim and of its true
source chunk:

| claim → source | n | one chunk | windows | IDF prefilter + windows |
| --- | --- | --- | --- | --- |
| nl → nl | 133 | 62.4% | 91.7% | **93.2%** |
| **nl → en** | **87** | 59.8% | **86.2%** | **78.2%** |
| en → en | 25 | 64.0% | 96.0% | 96.0% |

**34% of claims are Dutch from an English source.** The multilingual embedding
model handles them; the prefilter does not. So the cost-driven choice made two
sections above is not neutral: it **gains 1.5 points on same-language retrieval
and loses 8 on cross-language**. The 2.4-point average concealed a group.

That is worth stating plainly, because I chose the prefilter on the average and
would have kept choosing it. Filed as TASK-165, with the retrieval fix (route
around the prefilter on a language mismatch) separated from the question of
what language the extractor should write in at all — the second is a product
decision, not a retrieval one.

Language here is a stopword ratio, not a classifier, and the cross-language
bucket is 87 claims from four transcripts.

## The finding that outranks all of this

While building the probe: **every one of the 2389 memories has a
`source_session`, and not one has ever been checked against it.** The vault has
423 unverified memories, one line in the review log, and zero retracted. There
are no human labels to validate anything against, which is why this validation
had to invent its own.

That is a larger gap than the trust factor. A verification pass would be the
first time this system has ever asked whether what it wrote down was actually
said — and on this sample it would confirm about eight memories in ten and
correctly catch a handful of inventions, while demoting nothing.

## Reproducing

Scratch harnesses, not shipped scripts. `qwen3.5:4b` at temperature 0
throughout, `qwen3-embedding:4b` for retrieval.

| what | how |
| --- | --- |
| run 1 | 60 memories, seed 7; IDF top-8 chunks, embedding rerank, top 2 joined and cut at 6000 |
| run 2 | the same 60; IDF top-8, then 1500-character windows inside them, best 4 by cosine, joined in reading order |
| retrieval ground truth | the extractor over every chunk of 4 transcripts (11–18 chunks), seed 42 — 255 claims with a known originating chunk |
| labels | all 8 `unsupported`, adjudicated against the whole transcript by exhaustive search, not against the passage |
| quote check | all 60 verdicts, mechanically: every quoted span located in the passage the model was given |

Three claims in the first version of this document were wrong and are corrected
above rather than quietly edited: the unparseable answers did contain JSON,
passage selection did not miss half the time, and embedding every chunk does not
fix retrieval. Each was a plausible explanation written down instead of an
observed one.

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

Both were then measured properly, on 27 cases across two samples, each
adjudicated against the WHOLE transcript by an independent reader and each
judgement put to a second reader whose instruction was to refute it.

**`supported` does not fabricate.** The prompt asks the model to quote the
passage, and a quote is checkable, so every verdict in both runs was checked
mechanically rather than by hand — 210 of them. Non-verbatim quotes are common
(the model reformats, joins lines, normalises whitespace) and for **every one
the quoted substance is in the passage**.

    fabricated quotes    0 / 210    95% CI  0.0% - 1.8%

**`unsupported` is essentially never right.** Every `unsupported`, `partial` and
`not_found` verdict from both runs — 27 cases — went through the adjudication.
The result is one-sided:

    adjudicated labels   supported 25   partial 2   unsupported 0   absent 0
    refuted by the second reader                    0 of 27

Restricted to the verdict that would actually demote a memory:

    unsupported verdicts confirmed as unsupported   0 / 20    95% CI 0.0% - 16.1%
    ... or at least partial (lenient reading)       2 / 20    95% CI 2.8% - 30.1%

Every one of the twenty was stated in its source. Four examples:

| memory | in the transcript |
| --- | --- |
| firmware-versieconsistentie | *"reports alpha.284 while HEAD is alpha.285. For honest receipts (device version == pushed code), I'll rebuild at current HEAD first, then flash"* |
| contextbeheer-via-bestanden | *"Everything you paste into a dispatch prompt … stays resident in your context … and is re-read on every later turn. Hand artifacts over as files"* |
| deduplicatie-bij-merging | the merge loop itself: `seen = {n['id'] for n in ast['nodes']}` … `if n['id'] not in seen` |
| v2-feature-parity | *"`.39` runs the full feature set (each task flashed + Chromium-verified, 0 console errors)"* |

### Two failure modes, and the second is worse

**Retrieval missed.** In 10 of 17 run-3 cases the support was elsewhere in the
transcript. The prompt reserves `not_found` for a passage "about something else
entirely", so a miss landing on a *topically related* passage — same session,
same project, same afternoon — does not fit that description and the model
reaches for `unsupported` instead. From inside a passage, a retrieval miss and a
false memory are indistinguishable. Only exhaustive search separates them, and
the verifier does not search.

**The model rejected evidence it was holding.** In **7 of 17** the support was
inside the passage it was given, and it still declined. That is not a retrieval
problem at any coverage. `risico-op-informatielekkage` shows the mechanism: the
passage *states* the claim and gives no argument for it, and the model judged
whether the passage **justified** the claim rather than whether it **said** it.
For verifying extraction, said is enough.

A better prompt might narrow the second. It cannot touch the first.

### What follows: raise trust, never lower it

`supported` may confirm a memory. Nothing may demote one. The positive verdict
is backed by checkable quotes with no fabrication in 210 cases; the negative one
was right zero times in twenty.

That is where this vault already stands — the human is the authority for
negative signals — now with a measured reason instead of a principle.

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

### The extraction-invention rate I reported does not exist

An earlier version of this section said two of sixty memories stated something
their source does not — a 3.3% invention rate — and called it the vault's first
extraction-accuracy figure. **Both cases were my own search failures, and the
rate is zero.**

- **`capaciteit-van-capture-mode`** claims "up to 1 million log lines in
  memory". I searched for `miljoen`, `logberichten` and `geheugen`, found none
  of them in 491k characters, and concluded invention. The transcript says, at
  line 4489: `{"name":"Capture mode toggle", … "desc":"Checkbox to enable
  high-capacity capture mode (up to 1M lines in memory)"}`.
- **`hybride-dataverwerkingscyclus`** claims captures are merged monthly. I
  grepped `maandelijk|monthly`, got zero hits, and concluded invention. Line
  509 reads: *"Hybride gekozen: atomair capture → maand-merge."*

One failed on language, the other on morphology — and I had already written,
two sections above, that a Dutch claim against an English source defeats lexical
search. I diagnosed the trap and then walked into it, using the same instrument
I had just shown to be inadequate.

    extraction inventions confirmed    0 / 60    95% CI 0.0% - 6.0%

The corrected figure is the more interesting one. Across 27 acting-class cases
adjudicated exhaustively, **not one memory was found to state something its
source does not.** The extractor's accuracy was the premise of this whole
investigation — a trust factor exists to catch bad extractions — and on this
evidence there are very few to catch.

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

## Was it worth it? The numbers, and a verdict against the thing it was for

**The trust factor should not be built on this.** Not because the mechanism is
bad — it is better than expected — but because of what its output distribution
turns out to be.

    verdict = supported            133 / 150  =  88.7%   (82.6% - 92.8%)
    anything else                   17 / 150  =  11.3%   ( 7.2% - 17.4%)
    of those, correct                0 /  20  =   0.0%   ( 0.0% - 16.1%)

Read those three lines together. The factor is **uniform exactly where it is
reliable, and unreliable exactly where it varies.** Nine memories in ten get the
same verdict, which is the same defect as `evidence_basis: agent` sitting at
100% and making `trust_factor` inert — the defect this work set out to fix. The
one memory in ten that would be scored differently is the one where the verdict
was wrong every time it was checked.

This investigation began because two of five ranking factors were measured to do
nothing. It ends by measuring that the proposed replacement would do nearly
nothing, for a different reason, and would be wrong in the remainder. That is a
worse outcome for the factor and a better one for the vault, because the factor
would have been believed.

### What the work did buy, with numbers

| | before | after |
| --- | --- | --- |
| Answers silently lost to a parse failure | 4/56 = **7.1%** (2.8–17.0%) | 0/150 = **0%** (0–2.5%) |
| Passage contains the claim's real source | **62.7%** | **87.8%** (90.2% without the lexical prefilter) |
| Verifying a memory against its source | retrieve, and hope | a stamped lookup, for every future capture |

- **The parser fix protects five seams**, not just this probe. `extract`,
  `judge`, `reconcile`, `supersede` and the verifier all read model JSON through
  `_llmjson`, and all five fail *silently* — to `[]`, to `unverified`, to `ADD`.
  A 7% silent-failure rate across that surface was real and is now zero on 150
  calls.
- **The retrieval finding transfers**, and that is where its value actually is.
  Granularity, not shortlisting, was the whole problem — and `doc_text` caps
  every wiki document at 4000 characters, leaving **23.1% of all wiki text
  unembedded and unreachable** (TASK-164). That is a live defect in the hot
  path, found sideways by this work, and worth more than the factor it was
  chasing.
- **The extractor is trustworthy.** 27 acting-class cases, adjudicated
  exhaustively against whole transcripts, adversarially verified: zero
  inventions. The premise of the trust project — that agent-written memories
  need policing — is not supported on this corpus.

### What it cost

Roughly 1.5 GPU-hours of local inference across four measurement runs, and 3.25M
subagent tokens for the 27-case adjudication with its refutation pass. The
adjudication is what produced the decisive number (0 of 20) and it could not
have been done by hand at that rigour in the time.

### The honest caveats

- The adversarial pass **refuted nothing, 0 of 27**. A check that never fires
  has not been shown capable of firing. Its value here was in verifying that
  each quoted piece of evidence actually greps clean in the transcript, which it
  did, case by case.
- One corpus, one model (`qwen3.5:4b`), one embedding model. None of this
  generalises past this vault without re-measuring.
- The 88.7% `supported` rate is measured on memories that already survived
  capture-time dedup, reconcile and the judge. It is not the extractor's raw
  accuracy; it is the accuracy of what got written down.

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

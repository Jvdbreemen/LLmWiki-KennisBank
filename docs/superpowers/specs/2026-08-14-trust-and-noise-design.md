# Giving trust and noise something to read

**Design document. No implementation. 2026-08-14.**

`_rank.rerank` multiplies a memory's score by five factors. Two of them —
`trust_factor` and `noise_factor` — have been measured to do exactly nothing,
and for two different reasons. This document says what could feed them and what the field does about the
same problem.

Its conclusion changed while it was being written. The first draft treated
trust as a badly-designed factor and blocked every proposal behind an eval set.
The research says the opposite: provenance is the strongest trust signal
anyone has weighed, this repo already implements exactly that, and the vouching
that would feed it is already being collected and discarded. That part needs no
measurement to justify — only a decision about what to call it.

## 1. What is broken, measured

From `docs/research/rank-factors-2026-08-14.md`, 856-question dev split:

| arm | recall@1 | flips vs production | p |
| --- | --- | --- | --- |
| no trust | 0.2640 | **0 gained, 0 lost** | 1.0 |
| no noise | 0.2640 | **0 gained, 0 lost** | 1.0 |

Byte-identical to production. Neither factor has ever changed an ordering on
this vault.

**Trust asks the right question and gets no answer.** `trust_factor(evidence_basis)`
maps a provenance label to 0.95 / 1.00 / 1.05. Measured over the whole corpus:

    evidence_basis of all 1732 current memories: {"agent": 1732}

Every memory scores 0.95. A uniform multiplier cannot reorder anything, by
arithmetic. The factor is not neutral — it is *constant*, which is worse,
because it looks like a working signal in the code and in every future
measurement that does not check the distribution. It will also start working
without warning the first time a `getypt` or `import` memory appears.

**A first draft of this document said the factor "reads the wrong field". That
was wrong, and the correction is the most useful thing the research produced.**
Provenance is not a poor proxy for trust; in the one study that learned weights
over competing factors it is the strongest signal there is (§2). The field is
right. The vault simply contains no memory that a human has vouched for — and,
as §3.1 shows, that is not because none exists but because the system discards
the vouching.

**Noise is not broken; it is unused.** `noise_factor` reads a human marking
made with `kb-noise.py <stem>`, deliberately gated on a person rather than a
judge (see `02-wiki/usage-noise-signaal-mens-gated.md`). The mechanism is
sound, the penalty is bounded at 0.8, and it is exactly 1.0 without markings.
Nobody has ever made one.

Those are different problems and they need different answers. Trust needs a
signal. Noise needs an occasion.

## 2. What the field does

**Provenance is the strongest factor anyone has weighed, and recency the
weakest.** An ablation over seven cognitively grounded factors ([arXiv
2606.12945][a]) learns weights by stochastic hill-climb over
`V(m) = Σ wᵢ fᵢ(m)` and reports 0.770 gold-evidence retention against **recency
alone at 0.368**. The learned weights:

    reliability          0.64      <- highest
    emotional intensity  0.55
    self/user relevance  0.23
    goal relevance       0.00

And its definition of reliability is, verbatim, a **"provenance heuristic
(user-stated >> model-stated)"**.

That is worth sitting with. The factor this repo already has, expressed exactly
the way this repo expresses it, is the one that carried the most weight when a
model was allowed to learn what mattered. `trust_factor` is not a weak idea
poorly implemented; it is the strongest idea, starved of input.

Two caveats, because the paper states them itself: three of its seven factors
(value alignment, task utility, usage history) were held at zero for lack of a
value profile, an LLM judge and access logs, so it calls its own result "a
conservative, four-factor, API-free estimate". And a weight of 0.64 within four
factors is not a claim about this vault.

It is also an independent confirmation of what this repo measured from the
other direction: recency carries 50% of a 0.293 recall loss, and the factor
that should be carrying weight is the one that currently reads a constant.

**Confidence from extractors is not a probability.** Knowledge Vault fuses
extractions by learning a per-extractor reliability and combining it with
agreement across independent extractors, and warns that a raw extractor
confidence "is different from a probability in that it may not be calibrated" —
some extractors correlate confidence with accuracy, some do not, some are
actively bad at it ([Knowledge Vault][f]).

This is the strongest available argument against the obvious shortcut of asking
the judge how sure it is, and it arrives from a different direction than
TASK-156 did.

**Corroboration is how trust is established without source diversity.**
Open-domain knowledge extraction scores a candidate fact by how many
independent evidence sources assert the same value, consolidating with a
"Corroborator" step that weighs extractor confidence and *frequency of the
extracted value across sources* ([ODKE+][b]). Multi-agent fact-checking scores
credibility from agreement across agents with distinct sources ([Scientific
Reports][c]).

The relevant move: when every memory comes from the same kind of producer,
*who said it* carries no information, but *how many independent occasions said
it* still does.

**Contradiction is a trust signal, not only a supersede trigger.** Mem0
resolves conflicts at write time with an LLM comparison (ADD / UPDATE / DELETE
/ NOOP); Zep closes a validity window and keeps both versions with time ranges
([Hindsight][d]). Either way a contradicted claim is marked, not merely
replaced.

**Usage should work in both directions.** Mem0 boosts recently accessed
memories up to 1.5x and damps unused ones toward **0.3x** at search time
([Mem0][e]). KennisBank's `usage_factor` floors at 1.0 — boost-only — which is
precisely why the measurement found it has no effect (10 gained, 13 lost,
p = 0.68).

## 3. Design

### 3.1 The vouching already happens and is thrown away

**This is the proposal the research changed.**

The literature's strongest trust signal is "user-stated over model-stated". This
vault has no user-stated memories — and it is not for want of users stating
things. `/kennisbank:review` exists precisely so a human reads an `unverified`
memory and decides. `_memory.decide()` then does this:

```python
current = read_status(target)          # must be unverified
new_status = DECISIONS[decision]
set_status(target, new_status)         # -> current, or retracted
```

Status, and nothing else. A person who read a memory, judged it true and
approved it has personally vouched for its content — the exact act the
literature weighs highest — and the system records the outcome while discarding
the provenance of the outcome. The memory remains `evidence_basis: agent`,
indistinguishable from one no human has ever seen.

The fix is small and it is not a new signal: **human approval should promote
provenance, not only status.** An approved memory has a human in its evidence
chain and should say so.

What it needs decided rather than assumed:

- Which value. `getypt` means the human typed the text and is not true here.
  The honest label is a new one — the human confirmed a model's claim, which
  sits between `agent` and `getypt` and is not currently expressible.
- Whether a rejection should mark the *producer* too. A human retracting a
  memory is evidence about the extraction chain that produced it, and
  `model_id` and `prompt_version` are already stamped on every memory. That is
  Knowledge Vault's per-extractor reliability, computable here the moment
  enough decisions exist.
- Whether promotion is retroactive. Approvals already made are in the review
  log; the memories they approved are not marked.

It is sparse today, and sparse in the right way: it grows exactly as fast as a
human invests attention, which is the only honest exchange rate for trust.

### 3.2 Corroboration, for what no human will ever read

Approval does not scale to 1740 memories. For the rest, count independent
assertions instead of asking who produced them.

**The signal already exists and is thrown away.** In `memory-sweep.py`, a
candidate that is a near-duplicate of an existing memory is discarded:

```python
if _dup_skip(vec, valid_from, existing):
    s["duplicates"] += 1
    continue
```

That branch is the moment a second, independent observation of the same fact
arrives. Today it increments a counter and vanishes. It should instead
increment a counter *on the existing memory*.

Sketch:

    corroborations: N        # frontmatter, default 0
    trust_factor = min(CAP, 1 + K * log(1 + corroborations))

**Only distinct sessions count.** A transcript is chunked into dozens of
pieces and the same fact often appears in several of them. Counting those
would measure verbosity, not corroboration. The counter increments only when
the candidate's `source_session` differs from every session already recorded
on that memory, which means storing the session ids rather than a bare count.

**Bounded, per the yesmem lesson already in this repo.** The noise factor is
capped at -20% for the same reason: an unbounded signal becomes the ranking.
Any corroboration bonus needs a hard cap, and the cap belongs in the design,
not in tuning.

#### The problem this design has, stated before it is built

**At the current threshold the signal is nearly absent.** `_dup_skip` fires at
cosine > 0.92, and TASK-145 measured duplicates at **4 of 466 candidates —
0.9%**. A corroboration counter fed from that branch would stay at zero for
almost every memory, and a factor that is zero everywhere is the failure this
document exists to fix.

So corroboration needs a *lower* threshold than deduplication: something like
"corroborates above 0.85, deduplicates above 0.92". That is a second threshold
to justify, and justifying it needs the pair-labelling work of TASK-161 —
because "these two memories assert the same thing" is exactly the judgement
that task is building labels for.

**It correlates with age.** A memory written a year ago has had a year to
accumulate corroborations; one written yesterday has had none. Corroboration
therefore favours old memories, which is the opposite bias to recency. That
may partially cancel the recency distortion, or it may simply replace one
age-correlated distortion with another. It cannot be told apart without a set
that measures both directions — TASK-161 again.

### 3.3 Noise needs an occasion, not a redesign

The human-gated design stays. What is missing is a moment where marking is the
obvious next action.

The data to select candidates already exists in `kb-usage.db`: injected count,
used count, last used. The vault's own numbers, measured 2026-07-14: **293 of
313 injected memory stems were never used**, nearly all `importance: 4`.

Proposal: `/kennisbank:review` gains a second queue beside the unverified one —
memories injected N times and used zero times, oldest first — where the action
is "mark as noise" rather than approve/reject. Same shape as the existing
queue: the system proposes, the human decides.

This adds no new signal and no new factor. It connects an existing input to an
existing mechanism.

### 3.4 Contradiction with the authority as a negative signal

`kb-state-audit.py` already finds memories that contradict the configuration —
four on this vault, every one asserting a superseded embedding model. They are
`status: current`, so the recall hook injects them at full strength.

The audit is deterministic and needs no model. Feeding its CONTRADICTED pile
into the ranking as a bounded penalty is the smallest change proposed here, and
the only one whose input set is already known to be correct.

It is narrow by construction: it can only speak about claims that name
something an authority pins — a model, a threshold, a toggle, a path. That is a
small slice of the corpus and exactly the slice that goes stale.

## 4. Rejected

**An LLM confidence score at capture.** TASK-156 measured that the judge's own
supersede labels agree with the vault's history 55% of the time, and that
hand-labelling reverses the reading of the disagreements. Adding another
self-assessment by the same class of model is more of the signal that was just
shown to be unreliable. The arXiv ablation points the same way: query-time
model judgement is *down-weighted* by the learned model.

**Autonomous noise marking.** The repo's stated principle is that the human is
the authority for negative signals. A judge that can silently demote knowledge
is the mechanism TASK-150 was written to make visible, pointed the other way.

**Tuning `RECENCY_FLOOR` now.** It is the obvious lever — 0.6 permits a 40%
swing against RRF gaps of 1.6% — and it is not tunable on a metric that
penalises recency by construction.

## 5. What has to happen first

Every proposal above is a new factor or a new input to a factor, and this repo
has just measured that it cannot currently tell whether its factors help or
hurt:

> The eval set is generated one question per document, so it structurally
> penalises recency — the very thing recency exists to do. This metric would
> report recency as harmful even if it were working perfectly.

Building trust and noise inputs before that set exists would add two more
factors that cannot be evaluated, on top of two that cannot be evaluated. The
sequence is therefore:

1. **§3.1, approval promotes provenance** — needs no eval set at all. It does
   not change a weight; it fills a field that is currently empty, and the
   factor reading it is already in production and already bounded. The only
   decisions are naming and retroactivity.
2. **TASK-161** — an eval set with questions whose right answer is the newest
   of several matching memories, and questions where it is an older one.
3. **§3.4, contradiction penalty** — smallest ranking change, known-correct
   input set, measurable on the existing metric because it is about factual
   staleness rather than freshness preference.
4. **§3.2, corroboration** — needs the corroboration threshold, which needs
   TASK-161's pair labels.
5. **§3.3, noise queue** — independent of the others; a user-interface change
   rather than a ranking change, and can go at any point.

Note what moved. In the first draft, corroboration was the headline and every
proposal was blocked behind an eval set. The research reordered it: the
strongest signal in the literature is one this system already collects and
throws away, and restoring it needs no measurement to justify — only a decision
about what to call it.

## 6. Open questions

- What is an approved memory's `evidence_basis`? `getypt` is untrue (the human
  did not write it) and `agent` is now untrue too. A third value has to be
  named, and every consumer of that field has to keep working.
- Should a human retraction be recorded against the producing `model_id` and
  `prompt_version`? Knowledge Vault learns per-extractor reliability that way,
  and both fields are already stamped.
- What cosine threshold means "corroborates"? Not 0.92, or the signal is
  0.9% sparse. TASK-161's labelled pairs are the evidence for choosing it.
- Should corroboration count distinct sessions, or distinct *days*? A session
  is the cheaper key; a day is closer to "independent occasion".
- Does corroboration-favours-old cancel recency-favours-new, or compound into
  a different distortion? Only a two-directional set can say.
- What happens to `trust_factor` when the first `getypt` memory arrives? Today
  it silently starts reordering. Should the producer label remain a factor at
  all once corroboration exists, or is it subsumed?
- Should the noise queue be capped so a single review session cannot demote a
  large fraction of the corpus?

---

[a]: https://arxiv.org/abs/2606.12945 "Learning What to Remember: A Cognitively Grounded Multi-Factor Value Model for Agentic Memory"
[b]: https://arxiv.org/pdf/2509.04696 "ODKE+: Ontology-Guided Open-Domain Knowledge Extraction with LLMs"
[c]: https://www.nature.com/articles/s41598-026-41862-z "Multi-agent systems and credibility-based advanced scoring mechanism in fact-checking"
[d]: https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation "The Consolidation Problem in Agent Memory"
[e]: https://mem0.ai/blog/memory-eviction-and-forgetting-in-ai-agents "Memory eviction and forgetting in AI agents"
[f]: https://www.cs.ubc.ca/~murphyk/papers/kv-kdd14.pdf "Knowledge Vault: A Web-Scale Approach to Probabilistic Knowledge Fusion"

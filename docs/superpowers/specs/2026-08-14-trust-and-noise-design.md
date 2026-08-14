# Giving trust and noise something to read

**Design document. No implementation. 2026-08-14.**

`_rank.rerank` multiplies a memory's score by five factors. Two of them —
`trust_factor` and `noise_factor` — have been measured to do exactly nothing,
and for two different reasons. This document says what could feed them, what
the field does about the same problem, and why none of it should be built
before the measurement gap in TASK-161 is closed.

## 1. What is broken, measured

From `docs/research/rank-factors-2026-08-14.md`, 856-question dev split:

| arm | recall@1 | flips vs production | p |
| --- | --- | --- | --- |
| no trust | 0.2640 | **0 gained, 0 lost** | 1.0 |
| no noise | 0.2640 | **0 gained, 0 lost** | 1.0 |

Byte-identical to production. Neither factor has ever changed an ordering on
this vault.

**Trust is broken.** `trust_factor(evidence_basis)` maps a provenance label to
0.95 / 1.00 / 1.05. Measured over the whole corpus:

    evidence_basis of all 1732 current memories: {"agent": 1732}

Every memory scores 0.95. A uniform multiplier cannot reorder anything, by
arithmetic. The factor is not neutral — it is *constant*, which is worse,
because it looks like a working signal in the code and in every future
measurement that does not check the distribution.

It will also start working without warning the first time a `getypt` or
`import` memory appears, changing rankings for a reason nobody is watching.

**Noise is not broken; it is unused.** `noise_factor` reads a human marking
made with `kb-noise.py <stem>`, deliberately gated on a person rather than a
judge (see `02-wiki/usage-noise-signaal-mens-gated.md`). The mechanism is
sound, the penalty is bounded at 0.8, and it is exactly 1.0 without markings.
Nobody has ever made one.

Those are different problems and they need different answers. Trust needs a
signal. Noise needs an occasion.

## 2. What the field does

**Reliability dominates; recency is the weakest factor.** An ablation over
seven cognitively grounded factors ([arXiv 2606.12945][a]) reports learned
multi-factor weighting at 0.770 gold-evidence retention against **recency alone
at 0.368**, and finds that "reliability, emotional intensity and self/user
relevance dominate, while query-time goal similarity is correctly
down-weighted".

That is an independent confirmation of what this repo measured from the other
direction: recency carries 50% of a 0.293 recall loss, and the factor that
should be carrying weight is the one that currently reads a constant.

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

### 3.1 Trust from corroboration

Replace the producer label with a count of independent assertions.

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

### 3.2 Noise needs an occasion, not a redesign

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

### 3.3 Contradiction with the authority as a negative signal

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

1. **TASK-161** — an eval set with questions whose right answer is the newest
   of several matching memories, and questions where it is an older one.
2. **§3.3, contradiction penalty** — smallest change, known-correct input set,
   measurable on the existing metric because it is about factual staleness
   rather than freshness preference.
3. **§3.1, corroboration trust** — needs the corroboration threshold, which
   needs TASK-161's pair labels.
4. **§3.2, noise queue** — independent of the others; it is a user-interface
   change, not a ranking change, and can go at any point.

## 6. Open questions

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

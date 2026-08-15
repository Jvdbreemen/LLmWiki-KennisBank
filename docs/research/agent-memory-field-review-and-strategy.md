# Agent memory: field review and strategy for KennisBank

Status: research and strategic direction
Date: 2026-08-15
Baseline: the v0.31.1 line, including the full August research series through
`rerank-ceiling-2026-08-14`, `rank-factors-2026-08-14`,
`llm-trust-verification-2026-08-15` and `wiki-embed-cap-2026-08-15`, and the
open tasks TASK-160, TASK-161, TASK-162
Sources: [TsinghuaC3I/Awesome-Memory-for-Agents](https://github.com/TsinghuaC3I/Awesome-Memory-for-Agents)
(~300 papers, 2020–2026), [vectorize.io — best AI agent memory
systems](https://vectorize.io/articles/best-ai-agent-memory-systems) (eight
production frameworks), [plastic-labs/honcho](https://github.com/plastic-labs/honcho)
(reviewed separately in `honcho-memory-architecture.md`)
Scope: where KennisBank sits in the field, what remains worth doing, what to
deliberately not do

## A note on this document's own history

This is the third derivation. The first was written against v0.27.0 and missed
two releases; the second against v0.30.0 and was overtaken within a day by the
rerank and factor measurements. Each revision deleted recommendations the
project had already executed. That is worth recording rather than smoothing
over, for two reasons: it shows the project's own measurement loop is faster
than an external review cycle, and it demonstrates the sharp limit of advice
derived from a repository snapshot. What survives three derivations is more
likely to be structural than incidental — and what survives is the outcome
loop, the capture-side audits, and the consolidation automation. Everything
retrieval-side that this review recommended was independently done, in flight,
or measured obsolete on the same days it was being written.

## The one-sentence finding

KennisBank's retrieval loop now measures and corrects itself faster than
outside review can track it — and the system still cannot tell whether
remembering *helped*, which is the field's harder problem, the purpose named in
PRINCIPLES.md #5, and the one gap all three derivations of this document agree
on.

## The field's organising distinction

The Tsinghua list classifies long-term agent memory on one axis that matters
here:

> **Experience** — knowledge explicitly validated by task outcomes.
> **Memory** — information without reference to task outcomes.

The vectorize comparison reaches the same fork independently, calling it
*personalization memory* (preferences and conversation history) versus
*institutional memory* (lessons from experience, domain patterns, improvement
across repeated tasks), and concludes: "Pick an AI agent memory framework that
solves the harder problem." Most systems solve the first because the second is
harder and more valuable.

**By intent KennisBank is institutional.** PRINCIPLES.md #5 is "niet twee keer
dezelfde fout." `_extract.py` asks for lessons learned, bug fixes with cause and
fix, decisions, durable facts.

**By mechanism it is a personalization pipeline.** Extract atomic candidates →
embed → dedup → reconcile → judge → write with a status → retrieve → rerank →
inject. Every judgement about a fragment's worth is made *before it is ever
used*: `importance` and `status` from the judge at capture, `volatility` from
the extractor, and grounded verification (once TASK-163 lands) still judging
extraction fidelity, not usefulness. Usage telemetry — the one post-hoc signal,
and one the published field largely lacks — answers *was it referenced*, not
*did it help*.

## The gap is no longer theoretical — the project keeps hitting it

Three separate August documents ran into the same wall from three directions,
none of them naming it as the field's Experience/Memory distinction:

**`recall-after-growth-2026-08-14`**: "The set cannot answer whether new
captures are useful, only whether they crowd... every corpus-growth decision is
being made on half the evidence." The TASK-145 caps were frozen on that half.

**TASK-160**, on the factor decomposition: "Do not flip a default on the
outcome alone. The eval set is generated one question per document... That
structurally favours similarity and penalises recency and importance, which
exist to serve a goal this metric cannot see."

**TASK-161**, on what would make the recency finding actionable: "Two reports
say what the current metric measures; none says what the user needs."

Three measurements, each ending at the same sentence: *the instrument cannot
see the thing the system is for.* A freshness-aware eval set (TASK-161) fixes
one axis of that blindness. The outcome loop (TASK-173) fixes the axis under
it: not "which of two matching memories should rank first" but "did injecting
this memory change how the session went." Both are needed; neither substitutes
for the other.

## What the last 48 hours resolved that this review no longer needs to argue

Recorded so the next reader knows these are closed questions, not open ones:

- **The ranking bottleneck is not a missing cross-encoder.** The reranker "is
  already there, and it is losing": raw cosine over the production pool beats
  production ranking 0.557 to 0.264 at recall@1 (McNemar 272/21). The
  decomposition attributes half the loss to recency, a fifth to importance, and
  finds trust and noise byte-identical to production — inert because uniform.
  What remains is a *tuning-with-a-valid-instrument* problem (TASK-161), not a
  build problem.
- **The seven-factor ablation this review asked for happened** —
  `rank-factors-2026-08-14.md`, with a passing control (all-neutral reproduces
  cosine exactly, so the decomposition is complete). My queued ablation task is
  deleted as superseded.
- **The evidence_basis audit is answered**: `{"agent": 1732}`. A single-valued
  enum feeding a trust multiplier is a constant, and a constant cannot rank.
  TASK-162 takes the constructive path — contradiction penalty, corroboration
  across distinct sessions, a noise queue — rather than deletion, with a design
  doc and a verified direction rule (trust may be raised by grounded
  verification, never lowered). My audit task is deleted as superseded.
- **The memory layer's lexical arm is gone** (measured as costing ~15 points,
  then removed); the wiki embed cap is pre-registered for measurement with the
  cheap fix already ruled out (`wiki-embed-cap-2026-08-15`); the legacy one-hop
  neighbour (TASK-93) is removed; the hot-path latency question was answered by
  the embedding sweep.

## Scorecard against the field

| Dimension | Field's state of the art | KennisBank | Verdict |
| --- | --- | --- | --- |
| Temporal reasoning | Zep/Graphiti bi-temporal graph, cited best-in-class | `valid_from`/`valid_until`, supersession with a reversible closed-log, `volatility: state\|event` | **Ahead** |
| Retrieval measurement | LongMemEval/LoCoMo, vendor-reported | Pre-registered gates, McNemar-paired arms, passing controls, published null results *and* published retractions | **Ahead in method** |
| Self-correction speed | — | Rerank finding → decomposition → two follow-up tasks and a design doc, inside 48 hours | **Ahead** — and the reason external review keeps trailing |
| Grounded verification | Raw extractor confidence, uncalibrated (the Knowledge Vault warning) | Verifier validated against blind labels, asymmetry measured, direction rule fixed before use | **Ahead** |
| Write-time reasoning | Honcho's deriver, Mem0 consolidation | extract → dedup → reconcile → judge, all measured | **At parity or ahead** |
| Locality and sovereignty | Zep self-hosting deprecated, SuperMemory closed, Mem0 graph paywalled | Local SQLite, local Ollama, markdown truth, MIT | **Ahead**, structurally |
| Human editorial control | Absent across the field | Markdown, Obsidian, git, human merges; system proposes | **Ahead**, uniquely |
| Ranking quality | — | recall@1 0.264 in production against a measured 0.557 available at zero cost, pending a valid instrument to tune against | **Known, quantified, in flight** (TASK-160/161) |
| **Outcome validation** | The Learning-from-Experience branch: Reflexion, ExpeL, SWE-Exp, ReasoningBank | **None** | **Behind — the one durable gap** |
| Failure/dead-end capture | Reflexion, SWE-Exp: failures are the highest-value signal | Not a distinct type; extractor told to ignore intermediate steps | **Behind** (hypothesis, audit queued) |
| Skill/procedure induction | Memp, SkillWeaver, AWM, LEGOMem | `memory_type: procedure` stores a description, not an artifact | **Behind**, cheap to close |
| Consolidation trigger | Generative Agents: automatic periodic reflection | Distillation to wiki is human-triggered | **Behind its own principle #3** |

## What remains worth doing

These are the recommendations that survived all three derivations, now
sequenced against the work actually in flight.

### 1. Close the outcome loop — measurement only (TASK-173)

The cheap version needs no reinforcement learning: the session-end hook exists,
transcripts are archived, injected stems are logged. Missing is a weak
per-session outcome — did the session end in a commit, did the suite go green,
was an injected memory contradicted or superseded shortly after — linked back
to the stems injected into that session.

This is now also the complement TASK-161 needs. A freshness-aware eval set can
adjudicate *recency*; only an outcome signal can eventually adjudicate
*usefulness*, which is what the capture caps, the importance weights and the
noise queue are all implicitly guessing at. TASK-162's noise-queue proposal
("injected N times, used zero times") is the first consumer: it currently
defines waste as non-reference, and an outcome link is what would let it
distinguish ignored-and-harmless from read-and-misleading.

Scope discipline: land the link, report the correlation, stop. Ranking on it is
gated on an instrument that can see it — the TASK-161 requirement applies to
this signal as much as to recency.

### 2. Test whether dead ends survive extraction (TASK-172)

`_extract.py` says: capture lessons learned, bug fixes, decisions, durable
facts; ignore smalltalk, **intermediate steps**, and transient status. A dead
end is structurally an intermediate step that failed. The instruction that
filters noise may be filtering the class of experience knowledge that
Reflexion and SWE-Exp are built on, and that principle #5 names.

Cheap to settle by counting. TASK-145 showed intake truncation had silenced a
whole class of facts; a prompt that excludes a class is the same failure one
layer up. If the ratio is low, the fix is a prompt change plus a distinct type
(`valkuil`), judge-assigned, with its own half-life.

### 3. Automate the distillation proposal, keep the merge human (TASK-174)

Principle #3: what requires manual discipline does not happen. Distillation to
the wiki is human-triggered; `distill-notify.py` counts and mentions. Automate
the *proposal* — cluster the memory layer off-hours, draft articles for dense
clusters — and keep the merge human, the same split used for quarantined
memories. The wiki layer's saturation (recall@5 = 1.000) makes this about
keeping the curated layer fed, not about its retrieval. TASK-165's finding that
a third of memories are Dutch summaries of English sources is a caution for the
drafting half: proposals should carry their sources, not re-summarise them.

### 4. Observer provenance (TASK-170) — now with an empirical argument

All 1732 current memories carry `evidence_basis: agent`; the field is
single-valued and its trust factor is a constant. `observer` (which client
wrote this) is the provenance dimension that actually varies today, and
TASK-162's corroboration-across-distinct-sessions signal gets strictly stronger
when sessions can be distinguished by client. One optional frontmatter field
now; a vault-wide backfill later.

### 5. Promote proven procedures into skills (TASK-175)

Procedures are the worst-retrieved memory type (recall@1 0.277 at baseline) and
the literature's answer — Memp, SkillWeaver, Agent Workflow Memory — is to stop
retrieving them as prose and promote them to executable artifacts. The
destination (`skills/`, `commands/`) and the selection signal (usage telemetry)
exist. Gate on the telemetry distribution before building anything.

## What to deliberately not do

**Do not chase LongMemEval or LoCoMo.** Vendor-reported, and the same article
publishing the table calls them insufficient. The private sets — soon including
TASK-161's freshness set — are better instruments for this system.

**Do not add a graph database.** Wikilinks, graph tables in SQLite and the
coupling signal already cover it; the scene experiment showed graph communities
were not even good enough clustering to clear a pre-registered winner rule.

**Do not adopt a framework's memory layer.** LangMem is coupled to LangGraph,
LlamaIndex Memory to LlamaIndex, Letta requires its runtime. One local MCP
server serving four clients would not survive any of them.

**Do not touch `_rank` defaults before TASK-161's set exists.** Both
measurements say so explicitly. The 0.557-versus-0.264 result is real and it is
still not a licence to flip: the metric that produced it is structurally blind
to freshness, and the factors were built for freshness.

**Do not raise intake caps before ranking and its instrument are settled** —
standing conclusion of `recall-after-growth`, restated because the outcome loop
is what will eventually let that decision be made on full evidence.

## Sequencing

1. **TASK-160/161** (in flight, theirs): decompose confirmed → build the
   freshness-aware set → only then tune or trim `_rank`.
2. **TASK-173, outcome loop, measurement only** — parallel track; touches
   session-end, not retrieval. The one item in this document that changes the
   system's category.
3. **TASK-172, dead-end audit** — cheap, capture-side, independent.
4. **TASK-162 step 1** (theirs): the contradiction penalty, whose input set is
   already known correct.
5. **TASK-174 distillation proposals; TASK-170 observer field** alongside
   TASK-162 step 2, since corroboration and observer attribution touch the same
   sweep path.
6. **TASK-175 procedure promotion**, gated on telemetry.

## Closing judgement

Three derivations of this review each found the same thing at different
resolutions: the retrieval half of this system corrects itself faster than
outside advice can land, and the capture half still has no way to learn from
consequences. The August series closed the distance between "measured" and
"acted on" to under a day; nothing in it yet closes the distance between
"retrieved" and "mattered." That is the remaining difference between a very
well-instrumented memory and an experience system, and it is the one
recommendation this document is confident will still be standing when the next
snapshot overtakes the rest of it.

## Sources

- [TsinghuaC3I/Awesome-Memory-for-Agents](https://github.com/TsinghuaC3I/Awesome-Memory-for-Agents)
  — taxonomy, ~300 papers, benchmark index. Retrieved 2026-08-15.
- [vectorize.io, "Best AI agent memory systems"](https://vectorize.io/articles/best-ai-agent-memory-systems)
  — eight-framework comparison, benchmark and latency figures. Retrieved 2026-08-15.
- Internal: `rerank-ceiling-2026-08-14.md`, `rank-factors-2026-08-14.md`,
  `llm-trust-verification-2026-08-15.md`, `wiki-embed-cap-2026-08-15.md`,
  `recall-baseline-2026-08-13.md`, `recall-after-growth-2026-08-14.md`,
  `embedding-model-sweep-2026-08.md`, `l2-scene-retrieval-2026-08.md`;
  TASK-160, TASK-161, TASK-162, TASK-145.
- Papers referenced by name: Reflexion, ExpeL, SWE-Exp, ReasoningBank, Memp,
  SkillWeaver, Agent Workflow Memory, LEGOMem, MemGPT, Mem0, Generative Agents,
  Knowledge Vault. Benchmarks: LoCoMo, LongMemEval, MemoryAgentBench, MemBench.

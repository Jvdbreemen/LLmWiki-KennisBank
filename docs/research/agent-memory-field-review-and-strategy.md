# Agent memory: field review and strategy for KennisBank

Status: research and strategic direction
Date: 2026-08-15
Baseline: measured against the v0.30.0 line, including the August research
series (`recall-baseline`, `recall-after-growth`, `embedding-model-sweep`,
`l2-scene-retrieval`, `judge-model-4b-vs-9b`, `supersede-window`,
`supersede-judge-labelled`) and the open tasks TASK-137, TASK-138, TASK-145,
TASK-158
Sources: [TsinghuaC3I/Awesome-Memory-for-Agents](https://github.com/TsinghuaC3I/Awesome-Memory-for-Agents)
(~300 papers, 2020–2026), [vectorize.io — best AI agent memory
systems](https://vectorize.io/articles/best-ai-agent-memory-systems) (eight
production frameworks), [plastic-labs/honcho](https://github.com/plastic-labs/honcho)
(reviewed separately in `honcho-memory-architecture.md`)
Scope: where KennisBank sits in the field, what to improve, what to remove, what
to deliberately not do

## What this document does and does not add

The August research series already answers several questions an outside review
would normally raise, and answers them better than a review could: with
pre-registered gates, oracle ceilings, published null results, and at least one
report that contradicts the assumption that commissioned it. Nothing below
proposes re-measuring what those documents measured.

What a field review can add is the frame around them — which of the field's
problems this system is solving, which it is not, and whether the open roadmap
is pointed at the largest remaining gap. On that last question the answer is
mostly yes, with one exception that the project's own measurements have already
started pointing at without naming.

## The one-sentence finding

KennisBank's retrieval work is ahead of the published field in method and near
its ceiling in scope — and the system still cannot tell whether remembering
helped, which is both the field's harder problem and the blocker its own
capture-versus-recall trade-off has now run into.

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
embed → dedup → reconcile → judge → write with a status → hybrid retrieve →
rerank → inject. Every judgement about a fragment's worth is made *before it is
ever used*: `importance` and `status` from the judge at capture, `trust_factor`
from `evidence_basis`, `volatility` from the extractor. Usage telemetry, the one
post-hoc signal and one the published field largely lacks, answers *was it
referenced* — not *did it help*.

## The gap is no longer theoretical

`recall-after-growth-2026-08-14.md` reached this conclusion from the opposite
direction, without framing it as a taxonomy problem:

> The set cannot answer whether new captures are useful, only whether they
> crowd. Questions generated from memories written after the baseline would
> measure the other side of the trade, and until that exists every
> corpus-growth decision is being made on half the evidence.

That is the Experience/Memory distinction, arrived at empirically. The eval set
prices the *cost* of a bigger corpus (dilution at k) and cannot price the
*benefit* (a memory that answered something), because benefit is an outcome and
nothing records outcomes.

It is already binding. TASK-145 raised intake, the corpus grew 14%, memory
recall@5 fell from 0.778 to 0.768 and the pre-registered gate failed. The
recommendation was to stop raising caps until ranking improves — the right call
on the available evidence, and made on half of it. Every future capture-versus-
precision decision faces the same asymmetry: the cost is measurable and the
benefit is not.

**This is the highest-value open item in the memory system, and it is not on the
roadmap.**

## Where the roadmap is already right

The ranking bottleneck is identified and quantified. From TASK-138, on the
856-question dev split, of 209 questions missed at k=5 the gold memory sits in
the top 20 for 130, the top 200 for 186, with median rank 11 when found:

| Configuration | recall@5 | recall@1 |
| --- | --- | --- |
| baseline | 0.756 | 0.334 |
| L2 scene tier, perfectly clustered (rejected on measurement) | 0.796 | 0.338 |
| perfect reranking of the top 20 | 0.908 | 0.908 |

Retrieval surfaces the right memory and ranking buries it. Reranking the top 20
is worth more than every other retrieval idea measured, by a wide margin, and it
is filed as blocking. Nothing in this review displaces it.

The scene-tier work deserves separate note: an idea from the literature was
designed, measured, found not to clear its own pre-registered winner rule, and
published as a null result — with TASK-137 then catching that the oracle bound
had been computed against a routing rule the code does not use. That is better
epistemic practice than the commercial field exhibits anywhere in the vectorize
comparison, where benchmark numbers are vendor-reported on benchmarks the same
article calls insufficient.

## Scorecard against the field

| Dimension | Field's state of the art | KennisBank | Verdict |
| --- | --- | --- | --- |
| Temporal reasoning | Zep/Graphiti bi-temporal graph, cited best-in-class | `valid_from`/`valid_until`, supersession, per-type half-lives, and `volatility: state\|event` making the update rule structural | **Ahead** |
| Retrieval measurement | LongMemEval/LoCoMo, vendor-reported | Pre-registered gates, oracle ceilings, published null results, 1224+329 private questions | **Ahead in method** |
| Multi-strategy retrieval | vectorize: "retrieval strategy matters more than storage" | RRF over sqlite-vec + FTS5, graph neighbours, coupling — with the lexical half measured as *harmful* on the memory layer | **At parity**, with a known defect |
| Write-time reasoning | Honcho's deriver, Mem0 consolidation | extract → dedup → reconcile → independent judge, judge model itself measured (TASK-142/143/144) | **At parity or ahead** |
| Locality and sovereignty | Zep self-hosting deprecated, SuperMemory closed, Mem0 graph paywalled | Local SQLite, local Ollama, markdown truth, MIT | **Ahead**, structurally |
| Human editorial control | Absent across the field | Markdown, Obsidian, git; closures now logged and reversible (TASK-150/155) | **Ahead**, uniquely |
| Usage feedback | Effectively nobody | Injected stems logged, exit scan marks referenced ones, feeds ranking | **Ahead of the published field** |
| Ranking quality | — | recall@1 0.266–0.334 on the memory layer; ceiling 0.908 with perfect rerank | **Known gap, remedy filed** |
| **Outcome validation** | The whole Learning-from-Experience branch: Reflexion, ExpeL, SWE-Exp, ReasoningBank | **None** | **Behind, and now blocking** |
| Failure/dead-end capture | Reflexion, SWE-Exp: failures are the highest-value signal | Not a distinct type; extractor told to ignore intermediate steps | **Behind** (hypothesis) |
| Skill/procedure induction | Memp, SkillWeaver, AWM, LEGOMem | `memory_type: procedure` stores a description, not an artifact | **Behind**, cheap to close |
| Consolidation trigger | Generative Agents: automatic periodic reflection | Distillation to wiki is human-triggered | **Behind its own principle #3** |

## What to improve

### 1. Close the outcome loop — measurement only (TASK-166)

The one item that changes the system's category, and the one its own evidence
now demands. The cheap version needs no reinforcement learning: the session-end
hook exists, transcripts are archived, injected stems are logged. What is
missing is a weak per-session outcome — did it end in a commit, did the suite go
green, was an injected memory contradicted or superseded shortly after — linked
back to the stems injected into that session.

That also supplies the missing half of the capture-versus-recall trade: with an
outcome signal, "the corpus grew and recall@5 fell 0.010" can be weighed against
whether the new memories ever helped, instead of being the only number on the
table.

Scope discipline: land the measurement, look at the correlation, stop. Ranking on
a signal this noisy is a separate decision, and it must clear the same bar as any
other ranking factor (see below).

### 2. Sequence the factor ablation *around* the reranker, not before it (TASK-163)

`_rank.py` multiplies seven signals on the memory layer — relevance × recency ×
importance × trust × usage × noise × coupling — plus graph-neighbour expansion.
The embedding sweep already found one member of this family failing to earn its
place, and it is the biggest one: **disabling the FTS5 lexical half raises memory
recall@5 from 0.641 to 0.796**, across six of nine models. A hand-tuned signal
costing fifteen points is exactly the failure mode a seven-way product hides.

The strategic point is the interaction with TASK-138. A cross-encoder reranking
the top 20 *subsumes* most hand-tuned relevance shaping: it re-scores the
candidate set directly, and factors that exist to nudge ordering within that set
become redundant at best and contradictory at worst. Tuning seven multipliers
that a reranker will replace is wasted work; shipping a reranker on top of seven
unexamined multipliers buries the reason it under-performs.

So: **decide the reranker first, then ablate what it makes redundant** — and hold
the line that no new factor (including the outcome signal) joins the product
without measured contribution.

### 3. Test whether dead ends survive extraction (TASK-164)

`_extract.py` says: capture lessons learned, bug fixes, decisions, durable facts;
ignore smalltalk, **intermediate steps**, and transient status. A dead end is
structurally an intermediate step that failed. The instruction that filters noise
may also filter the highest-value class of experience knowledge — the one
Reflexion and SWE-Exp are built on, and the one principle #5 names.

A hypothesis, cheap to settle by counting before changing anything. TASK-145
showed intake truncation had already silenced a whole class of facts; a prompt
that excludes a class is the same failure one layer up.

### 4. Automate the distillation proposal, keep the merge human (TASK-167)

Principle #3 says what requires manual discipline does not happen. Distillation
to the wiki is human-triggered; `distill-notify.py` counts what is pending and
mentions it. Automate the *proposal* — cluster the memory layer off-hours, draft
articles for dense clusters — and keep the merge human, the same split already
used for quarantined memories. Note the wiki layer is saturated at recall@5 =
1.000, so this is about keeping the curated layer fed, not about its retrieval.

### 5. Promote proven procedures into skills (TASK-168)

Memp, SkillWeaver, AWM and LEGOMem converge: procedures learned from experience
should become executable artifacts, not prose re-derived on every recall. The
destination (`skills/`, `commands/`) and the selection signal (usage telemetry)
both exist. Gate on the telemetry distribution before building; procedure is also
the *worst-performing* memory type at recall@1 (0.277), which is its own argument
that prose retrieval is not serving it.

## What to remove

### 1. The lexical half of the memory-layer fusion — already measured, still shipping

Fifteen points of recall@5 on the layer that needs them most, identified in the
embedding sweep and filed on the v0.30.0 line. It is the clearest instance of the
general point and the removal with the largest known payoff.

### 2. The legacy one-hop neighbour — TASK-93, overdue

`_rank.one_hop_neighbor()` was to be removed one release after the graph flip.
Verified still present on the v0.30.0 line, several releases later. Dual-path
drift is a documented failure mode in this repo's own instructions.

### 3. Unused `evidence_basis` values and their trust weights (TASK-169)

Six members, each feeding `trust_factor()` and therefore carrying live ranking
weight. Count the real distribution; delete what is never written. Decide
together with TASK-161 (observer provenance), which would take over part of what
`evidence_basis` is doing today, so the enum is not trimmed twice.

## What to deliberately not do

**Do not chase LongMemEval or LoCoMo.** Vendor-reported, and the same article
that publishes the table says these benchmarks only test retrieval from chat
histories. The private eval sets are better instruments for this system than
either.

**Do not add a graph database.** Wikilinks, graph tables in SQLite and the
coupling signal already approximate what Zep/Graphiti and Cognee buy with a
second datastore — and the scene experiment showed graph communities were not
even good enough clustering to clear a winner rule.

**Do not adopt a framework's memory layer.** LangMem is coupled to LangGraph,
LlamaIndex Memory to LlamaIndex, Letta requires its whole runtime. One local MCP
server serving four clients would not survive any of them.

**Do not raise intake caps again before ranking improves** — already the standing
conclusion of `recall-after-growth`, restated here because the outcome loop is
what will eventually make that decision on full evidence rather than half.

## Sequencing

1. **TASK-138, the rerank ceiling** — already blocking, worth more than anything
   else measured, and it determines what step 2 should even look at.
2. **Ablation of what the reranker makes redundant** (TASK-163), starting with
   the lexical half already measured as harmful.
3. **Outcome loop, measurement only** (TASK-166) — independent of 1–2 and the
   thing that changes the category. Can run in parallel; it touches session-end,
   not retrieval.
4. **Dead-end audit** (TASK-164) — cheap, tests a claim in PRINCIPLES.md.
5. **Distillation proposals** (TASK-167) and **procedure promotion** (TASK-168),
   the latter gated on telemetry.

## Closing judgement

The retrieval half of this system is measured better than the commercial field
measures itself, and its remaining retrieval gap is quantified with a known
remedy. The strategic risk is not that ranking is at 0.266@1 — that is a solved
problem awaiting execution. It is that every decision about what to remember is
being made against a metric that can only see crowding, so the system optimises
what it can measure: a smaller, tidier corpus. The purpose it was built for is
the opposite, and closing the outcome loop is what lets those two stop pulling
against each other.

## Sources

- [TsinghuaC3I/Awesome-Memory-for-Agents](https://github.com/TsinghuaC3I/Awesome-Memory-for-Agents)
  — taxonomy, ~300 papers, benchmark index. Retrieved 2026-08-15.
- [vectorize.io, "Best AI agent memory systems"](https://vectorize.io/articles/best-ai-agent-memory-systems)
  — eight-framework comparison, benchmark and latency figures. Retrieved 2026-08-15.
- Internal: `docs/research/recall-baseline-2026-08-13.md`,
  `recall-after-growth-2026-08-14.md`, `embedding-model-sweep-2026-08.md`,
  `l2-scene-retrieval-2026-08.md`; TASK-137, TASK-138, TASK-145, TASK-158.
- Papers referenced by name: Reflexion, ExpeL, SWE-Exp, ReasoningBank, Memp,
  SkillWeaver, Agent Workflow Memory, LEGOMem, MemGPT, Mem0, Generative Agents.

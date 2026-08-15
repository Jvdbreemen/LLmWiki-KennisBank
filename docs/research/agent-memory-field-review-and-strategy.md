# Agent memory: field review and strategy for KennisBank

Status: research and strategic direction
Date: 2026-08-15
Sources: [TsinghuaC3I/Awesome-Memory-for-Agents](https://github.com/TsinghuaC3I/Awesome-Memory-for-Agents)
(~300 papers, 2020–2026), [vectorize.io — best AI agent memory
systems](https://vectorize.io/articles/best-ai-agent-memory-systems) (eight
production frameworks compared),
[plastic-labs/honcho](https://github.com/plastic-labs/honcho) (reviewed
separately in `honcho-memory-architecture.md`)
Scope: where KennisBank sits in the field, what to improve, what to remove, what
to deliberately not do

## The one-sentence finding

KennisBank's architecture is competitive with or ahead of the commercial field on
almost every axis the literature measures — and it is built on the *wrong half*
of the field's central distinction: it promises learning from experience and
implements retrieval of information.

Everything below elaborates that sentence.

## The field's organising distinction

The Tsinghua survey list classifies agent memory on two axes. The first is
persistence: short-term (within the context window, one task) versus long-term
(external, across tasks). The second axis applies to long-term memory only, and
it is the one that matters here:

> **Experience** — knowledge explicitly validated by task outcomes.
> **Memory** — information without reference to task outcomes.

The list then maps that onto three application scenarios, each with its own
mechanisms and its own literature:

| Scenario | What is stored | Typical mechanism |
| --- | --- | --- |
| Personalization | User profile, facts, interaction history | External pool, embed and retrieve |
| Learning from experience | Trajectories, successes, failures, skills | Reflection, failure analysis, skill induction |
| Long-horizon task | Intermediate results, reasoning traces | Summarisation, scratchpad, checkpoint |

The vectorize article reaches the same fork independently and states it more
bluntly. It splits the market into *personalization memory* (remembering user
preferences and conversation history) and *institutional memory* (extracting
lessons from experience, learning domain patterns, improving across repeated
tasks), and concludes: "Pick an AI agent memory framework that solves the harder
problem." Its judgement is that most systems solve the first because the second
is harder and more valuable.

Two independent sources, one distinction. That is the lens worth applying to
this repository.

## Where KennisBank actually sits

**By intent, squarely in institutional memory.** `PRINCIPLES.md` #5 is "Niet twee
keer dezelfde fout" — do not make the same mistake twice. The README promises
"decisions, fixes, preferences, architecture trade-offs, dead ends, and lessons
you do not want to rediscover next week." `_extract.py` asks the model for
"lessons learned, bug-fixes (cause plus fix), decisions made, durable facts."
This is the harder problem, chosen deliberately, and it is the right choice.

**By mechanism, a personalization pipeline.** Transcript → chunk → extract atomic
candidates → embed → dedup → reconcile → judge → write with a status → hybrid
retrieve → rerank → inject. That is the Mem0/MemoryBank shape, applied to
experience-flavoured content. Nothing in the loop is validated by a task outcome.

The gap is precise and it is the taxonomy's second axis: **KennisBank stores
experience-shaped content as memory-class records.** A fragment is judged at
capture time by an independent LLM opinion about whether it *looks* reusable. It
is never confirmed by whether reusing it worked.

This is not a flaw in the code. It is a missing loop.

## Scorecard against the field

| Dimension | Field's state of the art | KennisBank | Verdict |
| --- | --- | --- | --- |
| Temporal reasoning | Zep/Graphiti's bi-temporal knowledge graph, cited as best-in-class | `valid_from`/`valid_until` distinct from `created`, supersession closes the old record, per-type half-lives | **At parity.** Do not spend here |
| Multi-strategy retrieval | vectorize: "retrieval strategy matters more than storage" | RRF over sqlite-vec KNN + FTS5, graph-neighbour expansion, coupling signal | **At parity**, without a second datastore |
| Write-time reasoning | Honcho's deriver, Mem0's consolidation | Sweep with extract → dedup → reconcile (ADD/SUPERSEDE/NOOP) → independent judge | **At parity** |
| Locality and sovereignty | Zep self-hosting deprecated; SuperMemory closed; Mem0 graph behind $249/mo | Local SQLite, local Ollama, markdown source of truth, MIT | **Ahead**, structurally |
| Human editorial control | Absent across the field — conclusions live in vendor databases | Markdown, Obsidian, git, human merges and supersedes | **Ahead**, uniquely |
| Retrieval measurement | LongMemEval, LoCoMo, recall metrics | recall@k, MRR, per-layer, per-type, frozen eval runs | **At parity** at personal scale |
| Usage feedback | Effectively nobody does this | Injected stems logged, exit scan marks those referenced in tool calls, feeds a ranking boost | **Ahead of the published field** |
| **Outcome validation** | The whole "Learning from Experience" branch: Reflexion, ExpeL, SWE-Exp, Memento, ReasoningBank | **None** | **Behind, and it is the core promise** |
| Failure/dead-end capture | Reflexion, SWE-Exp, Live-SWE-agent: failures are the highest-value signal | Not a distinct type; extractor told to ignore intermediate steps | **Behind** (hypothesis, see below) |
| Skill/procedure induction | Memp, SkillWeaver, Agent Workflow Memory, LEGOMem, TokMem | `memory_type: procedure` stores a *description* of a procedure | **Behind**, but cheap to close |
| Consolidation trigger | Generative Agents' reflection: periodic automatic synthesis | Distillation to wiki is human-triggered (`/destilleer`) | **Behind its own principle #3** |

Read the column, not the rows: the deficits cluster in exactly one place.

## What to improve

### 1. Close the outcome loop — the only recommendation that changes the category

Everything the system knows about a memory's worth is assigned before that memory
is ever used: `importance` from the judge, `status` from the judge, `trust_factor`
from `evidence_basis`. The one post-hoc signal, usage telemetry, answers *was it
referenced*, not *did it help*. A memory that got injected, got read, and sent the
session down a wrong path scores identically to one that saved an hour.

This is the difference between Memory and Experience in the taxonomy, and between
personalization and institutional memory in the vectorize framing. It is the
harder problem, it is the one KennisBank claims in its own principles, and it is
open.

The cheap version does not need reinforcement learning or trajectory modelling.
The session already ends with a hook, transcripts are already archived, and
injected stems are already logged. The missing piece is a weak outcome signal
attached to that session — did it end in a commit, did the suite go green, was
the memory contradicted or superseded shortly after being injected — and a link
from that signal back to the stems injected into it. Weak, noisy, and still
strictly more information than the system has today.

Two guardrails, both from this repo's own constraints. It must stay off the hot
path (a write-time or session-end job, never a recall-time computation). And it
must not silently become a ranking input: land the measurement first, look at
whether outcome correlates with anything, and only then decide whether it earns a
factor. See the ablation recommendation below for why that order matters.

### 2. Test whether dead ends survive extraction — then fix the prompt

`_extract.py` instructs: capture lessons learned, bug fixes, decisions, durable
facts; **ignore smalltalk, intermediate steps, and transient status**. A dead end
— the approach tried for two hours that did not work — is structurally an
intermediate step that failed. The instruction that filters noise may also be
filtering the single highest-value class of experience knowledge, the one the
Reflexion/SWE-Exp line of work is built on, and the one principle #5 names.

This is a hypothesis, not a finding: an articulate dead end can present as a
"lesson learned" and survive. It is also cheap to settle — sample the existing
memory layer and count how many fragments encode what *did not* work versus what
does. If the ratio is low, the fix is a prompt change plus a distinct type
(`valkuil`/anti-pattern) so retrieval can surface "you tried this before and it
failed" as a first-class answer rather than hoping it hides inside a fact.

Bumping `EXTRACT_PROMPT_VERSION` already exists precisely so a prompt change is
attributable. The machinery for doing this safely is in place.

### 3. Propose consolidation automatically — principle #3 against the current design

`PRINCIPLES.md` #3: *what requires manual discipline does not happen in
practice.* Distillation from raw memory to curated wiki is triggered by a human
running `/destilleer`. `distill-notify.py` counts what is pending and mentions it
at session start — a notification, not an action.

By the repo's own stated principle, that pipeline stalls. The Generative Agents
reflection pattern is the field's answer: periodically cluster related records and
synthesise higher-level insight, automatically.

The full pattern is wrong here — auto-merging into the wiki would take away
editor-in-chief control, which is a differentiator, not an inconvenience. The
right half is: **automate the proposal, keep the merge human.** An off-hours job
clusters the memory layer, identifies clusters dense enough to be worth an
article, and drafts the proposal. The human still decides. That is automation of
the discipline, not of the judgement, and it is exactly the split the vault
already uses for quarantined memories.

### 4. Promote proven procedures into skills

Memp, SkillWeaver, Agent Workflow Memory and LEGOMem converge on one move:
procedures extracted from experience should become *executable artifacts*, not
descriptions retrieved as prose. `memory_type: procedure` currently stores a
description; when it is recalled, an agent reads it and re-derives the steps.

KennisBank already has the destination: `skills/` and `commands/`. The signal for
which procedures deserve promotion already exists too — usage telemetry knows
which stems get injected and referenced repeatedly. A procedure memory recalled
and used N times is a skill trying to be written.

Gate this on the data rather than building it speculatively: query usage
telemetry for procedure-typed memories by recall frequency. If a meaningful head
exists, the promotion path is worth building. If recalls are uniformly thin, it
is not.

### 5. Measure where the hot path actually spends its time

The vectorize article's latency profile: vector-only retrieval 10–50ms, graph
traversal 50–150ms, multi-strategy 100–600ms, LLM synthesis 800–3000ms.
KennisBank budgets 2.0s for the prompt hook, and the comment in `kb-retrieve.py`
attributes it to the embedding call, not the search.

If that holds, the entire retrieval architecture sits inside the noise of one
Ollama round-trip, and every future ranking refinement optimises the wrong term.
Land a measurement splitting embed time from search time from rank time. It costs
almost nothing and it determines whether the next performance work is a smaller
embed model, a prompt-embedding cache, or nothing at all.

## What to remove

The user asked what to remove, and the answer is not "nothing".

### 1. Ranking factors that have never been measured separately

`_rank.py` multiplies, on the memory layer: relevance (hybrid RRF) × recency
(per-type half-life with a floor) × importance (judge, 1–5) × trust
(`evidence_basis`) × usage (1.10/1.05 tiers) × noise (up to −20%) × coupling
(1.05/1.10 tiers) — then adds graph-neighbour expansion on top. Seven
multiplicative signals, most introduced with their own justification, all judged
by a single referee: recall@k on the eval set.

Individually each is defensible. Collectively they are unattributable. A boost of
1.05 and a penalty floor of 0.80 interact in ways nobody can reason about, a
regression cannot be traced to a factor, and every new signal makes the next one
harder to evaluate. This is precisely the "drie clevere mechanismen" that KISS
warns against, arrived at one reasonable step at a time.

**Run an ablation and delete what does not earn its place.** Turn each factor off
individually against the frozen eval set, record the delta, and remove any factor
whose contribution is indistinguishable from noise. The harness for this already
exists — TASK-86 built frozen eval runs and TASK-72 added observed rank as a
selection criterion. Expect at least one deletion; a factor worth 1.05 in a
seven-way product is likely below the measurement floor.

This also disciplines the recommendations above: outcome signal and any new
factor must pass the same bar before joining the product.

### 2. The legacy one-hop neighbour — already queued as TASK-93, now overdue

`_rank.one_hop_neighbor()` is the regex-based expansion superseded by
`_kbindex.graph_neighbors()` after the A/B gate passed in TASK-87. The task says
it stays as fallback "for exactly one release, then gets removed." Several
releases have shipped since. Dual-path drift is a documented failure mode in this
repo; the removal is written and waiting.

### 3. Unused `evidence_basis` values, and the trust weights attached to them

`EVIDENCE_BASES` has six members: `getypt`, `cc-sessie`, `audio`, `import`,
`autoresearch`, `agent`. Each feeds `trust_factor()` in ranking. If some are never
produced in practice, they are dead schema carrying live ranking weight — and
dead enum members invite future code to handle cases that cannot occur. Count the
distribution in the real vault; delete what is never written, or document why it
is retained.

## What to deliberately not do

**Do not chase LongMemEval or LoCoMo scores.** The vectorize article reports
Hindsight 94.6%, SuperMemory 81.6%, Zep 63.8%, Mem0 49.0% — and then says these
benchmarks "only test retrieval from chat histories," not whether memory improves
agent task performance. The numbers are also largely vendor-reported. KennisBank
is not a conversational memory system, and optimising against a conversational
benchmark would pull it toward the easier problem it deliberately did not choose.

**Do not add a graph database.** Neo4j-backed designs (Zep/Graphiti, Cognee) buy
entity relationships KennisBank already approximates with wikilinks, graph tables
in SQLite, and the coupling signal — without a second datastore, and without
giving up "the index is a rebuildable throwaway."

**Do not adopt a framework's memory layer.** The article's clearest warning is
lock-in: LangMem is severely coupled to LangGraph, LlamaIndex Memory to
LlamaIndex, Letta requires adopting its whole runtime. KennisBank serves four
clients (Claude Code, Codex, Copilot CLI, OpenCode) through one local MCP server.
Any of these would collapse that.

**Do not add an eighth ranking factor before the ablation.** Including the outcome
signal from recommendation 1.

## Sequencing

The order is chosen so each step produces information the next one needs, and so
that the cheap diagnostics come before the expensive builds.

1. **Ablation of the existing ranking factors** (removal, and it gates everything
   else). Nothing new joins the product until the product is understood.
2. **Dead-end capture audit** (cheap, and it tests a claim in `PRINCIPLES.md`).
3. **Hot-path latency split** (cheap, and it decides whether performance work is
   worth doing at all).
4. **Outcome loop, measurement only** — link session outcome to injected stems,
   look at the correlation, do not rank on it yet.
5. **Automated distillation proposals** (independent of 1–4; resolves the
   principle #3 tension).
6. **Procedure-to-skill promotion**, gated on what step 4's telemetry shows.

Steps 1–3 are diagnostics that could each end in "no change needed," which is a
valid and cheap outcome. Step 4 is the one that changes what kind of system this
is.

## Closing judgement

The commercial field is converging on infrastructure KennisBank does not need and
benchmarks it should not chase. On the axes the literature actually measures —
temporal reasoning, retrieval strategy, write-time consolidation — this
implementation is at parity with funded products while keeping locality, human
editorial control, and a rebuildable index that none of them offer.

The deficit is singular and it is the thing the project named as its purpose:
nothing in the loop knows whether remembering helped. Close that, and KennisBank
is doing the harder half of the problem the field says is more valuable, with an
architecture already in place to support it.

## Sources

- [TsinghuaC3I/Awesome-Memory-for-Agents](https://github.com/TsinghuaC3I/Awesome-Memory-for-Agents)
  — taxonomy, ~300 papers, benchmark index. Retrieved 2026-08-15.
- [vectorize.io, "Best AI agent memory systems"](https://vectorize.io/articles/best-ai-agent-memory-systems)
  — eight-framework comparison, benchmark and latency figures. Retrieved 2026-08-15.
- Papers referenced by name: Reflexion, ExpeL, Retroformer, SWE-Exp, Memento,
  ReasoningBank, Memp, SkillWeaver, Agent Workflow Memory, LEGOMem, TokMem,
  MemGPT, MemoryBank, Mem0, Generative Agents. Benchmarks: LoCoMo, LongMemEval,
  MemoryAgentBench, MemBench, LifelongAgentBench.

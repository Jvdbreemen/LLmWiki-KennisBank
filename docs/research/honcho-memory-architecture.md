# Honcho as a mirror for KennisBank

Status: research, with one idea adopted (TASK-193) and two queued (TASK-194, TASK-171)
Date: 2026-08-15
Subject: [plastic-labs/honcho](https://github.com/plastic-labs/honcho) — memory
infrastructure for stateful agents, AGPL-3.0
Scope: architecture comparison, ideas worth adopting, ideas deliberately rejected

## Executive conclusion

Honcho is the best-developed public example of the thesis KennisBank is built
on: reason expensively at write time, retrieve cheaply at read time. It arrives
there from the opposite direction — a hosted multi-tenant service over Postgres,
where KennisBank is a local single-owner vault over markdown — and the
convergence is worth more than the differences. Two systems designed
independently landed on the same split between a synchronous storage path and an
asynchronous reasoning worker.

Read it as a reference architecture, not a dependency. One idea closes a real gap
and has been adopted. One is cheap, narrow, and queued. One looks attractive and
should not be built until a measurement justifies it. The infrastructure itself
is the wrong answer for this project, for reasons given below that are about fit
rather than quality.

**Licence boundary, first and hard.** Honcho is AGPL-3.0; KennisBank is MIT. API
shapes, data-model ideas and design arguments transfer freely. Code does not. A
single lifted function would make KennisBank's licence a problem for everyone
downstream, so the transfer here is deliberately at the level of ideas, and the
adopted implementation was written from the description, not from their source.

## What Honcho is

A service that sits between an agent and its conversation history and answers
"what do I know about this participant?"

Data model:

| Primitive | Role |
| --- | --- |
| Workspace | Top-level isolation container |
| Peer | Any participant — human or agent — as a first-class entity |
| Session | A conversation involving multiple peers |
| Message | The atomic unit within a session |
| Collections / Documents | Vector storage keyed by an **(observer, observed)** pair |

That last row is the real novelty. Memory is not global; it is per-perspective.
What peer A believes about peer B is a separate record from what B believes about
itself. Multi-party by construction rather than retrofitted.

Two services:

- **Storage** — synchronous CRUD over the primitives above.
- **Insights** — an asynchronous *deriver* worker consuming a per-session queue,
  producing conclusions (split into deductive and inductive), peer
  representations, session summaries, and a "dream" pass.

Read paths: a Conclusions API for extracted facts, Representations as
precomputed low-latency snapshots, a token-bounded `/context` endpoint returning
a prompt-ready bundle, a `/chat` endpoint answering natural-language questions
about a peer, and hybrid BM25-plus-vector search.

Stack: Python/FastAPI, Postgres with pgvector (Turbopuffer and LanceDB also
selectable), configurable Gemini/Claude/OpenAI providers, Python and TypeScript
SDKs, an MCP server for Claude Code, Cursor, Cline and Windsurf. The project
claims to have "defined the Pareto Frontier of Agent Memory" on LongMemEval and
LoCoMo; the repository points at a blog post rather than carrying numbers, so
that claim is unverified here and should be treated as marketing until the
methodology is read.

## Where the two designs agree

The agreement is structural, not cosmetic.

**Pay at write time, retrieve fast.** Their deriver worker is KennisBank's
`distill-notify` plus the `build-*-index` family: expensive reasoning off the hot
path, so the interactive path is an index lookup. Both systems treat a slow
recall as a design failure rather than a tuning problem.

**Precomputed snapshots over on-demand reasoning.** Their Representations exist
because reasoning at query time is too slow to sit in front of a user. This is
KennisBank's "betaal vooraf, haal snel op" with different words.

**Typed knowledge that ages differently.** They separate conclusions from
summaries from representations; KennisBank separates `memory_type` into feit,
voorkeur, procedure and beslissing precisely because a decision and a preference
decay on different schedules.

**Bi-temporality.** Both distinguish when something was captured from when it
was true. KennisBank's `valid_from` / `valid_until` versus `created` is the same
insight their per-session ordering and supersession machinery encodes.

Independent convergence on four points is reasonable evidence the shared parts
are right, and it is the most useful thing this review produced.

## Adopted: a real ceiling on assembled context (TASK-193)

Honcho's `/context` endpoint takes a token bound as a request parameter and
packs to fit. KennisBank had the layering but not the bound.

`scripts/context-budget.py` is named for a budget it did not enforce. L0–L3 nest
content — identity, then active state, then search results, then full article
bodies — but nothing bounded the result. An L3 answer over three long articles is
an order of magnitude larger than one over a short article, and the caller got no
signal either way. A "budget" that only says what to include and never how much
is half a budget.

Adopted as `--max-tokens` (and `KB_CONTEXT_MAX_TOKENS`), local and
dependency-free:

- **Trim order is fixed and justified by recoverability**: `bodies` first
  (recoverable from `relevant`, which keeps path and snippet), then `relevant`
  (recoverable by searching again), then `active` (a convenience summary).
- **Lowest-ranked entry first.** `relevant` is score-ordered and `bodies` is
  built in that same order, so trimming from the tail drops the weakest match
  rather than an arbitrary one.
- **`identity` is never trimmed.** It is the vault contract the rest of the
  answer is read against; half a contract is worse than an honest overrun. When
  identity alone exceeds the ceiling the output says so instead of cutting it.
- **No silent truncation.** Requesting a ceiling always produces a `_budget`
  block — ceiling, estimate, whether it fitted, and what was dropped per layer.
  Silence would read as "everything was included."
- **Default unchanged.** Without a ceiling the output is byte-identical to
  before, so nothing that consumes this script needed to change.

The estimate is ~4 characters per token rather than a real tokenizer. Pulling a
tokenizer in would put a model load on the one path whose entire purpose is to be
cheap, which would be a self-defeating trade. The consequence — treat the ceiling
as approximate and leave headroom — is documented at the flag, in
`CONFIGURATION.md`, and in the module docstring.

## Queued: observer provenance (TASK-194)

Honcho keys observations by (observer, observed). KennisBank records
`evidence_basis`, which answers what *kind* of origin a fragment has — `agent` is
one of six values — but never *which* agent. With Claude Code, Codex and the
Copilot CLI all writing into one vault, `evidence_basis: agent` became ambiguous
at exactly the moment the distinction started to matter.

The proposal is deliberately half of Honcho's model: one optional `observer`
field, no second half. KennisBank has exactly one observed subject — the vault
owner's work — so the pair collapses to a single field. Building the second half
before a second subject exists would be modelling for an imagined future.

Cheap now, expensive later: it is one optional field today, and a migration
across every fragment once attribution is needed retroactively.

## Queued behind a measurement: stated versus inferred (TASK-171)

Honcho splits deductive conclusions ("the peer stated this") from inductive ones
("the peer probably prefers this"). An initial read of this review suggested
KennisBank lacks that axis entirely. Reading `scripts/_memory.py` corrected that:
three axes each cover part of it.

- `status` — whether a fragment has been judged, not how it was arrived at.
- `evidence_basis` — the channel it arrived through. `getypt` is close to
  "stated" and `autoresearch` close to "inferred", but both conflate channel with
  inference: a `cc-sessie` fragment may be a verbatim quote or a model's
  generalisation.
- `memory_type` — what kind of claim it is.

So the gap is real but narrower than it first looked: once both reach
`status: current`, an inference dressed as a fact is indistinguishable from a
quoted one. That matters directly for the system's first non-negotiable
constraint — no wrong or stale recall — because the two failure modes are not
equally likely and one score cannot express both.

It is still not worth building on that argument alone. This is a schema change to
the layer whose ranking is already tuned, and the repository's own habit is to
measure before changing ranking inputs. TASK-171 therefore gates the field behind
a number from the memory eval set: what fraction of wrong-recall cases are
inferences presented as stated fact. Below a meaningful threshold, the answer is
to close it and record the measurement.

## Rejected, with reasons

**The infrastructure.** Postgres, pgvector, a queue and a worker service, against
KISS and against SQLite-as-a-disposable-cache. The deeper objection is
authority: Honcho's database is the source of truth, while KennisBank's index is
a throwaway that `rm kb-index.db && kb-index --rebuild` reconstructs from
markdown. That property is worth more than anything the heavier stack buys, and
it is not recoverable once given up.

**The absence of a readable layer.** Honcho's conclusions live in Postgres and
are reachable only through its API. KennisBank's markdown is readable in
Obsidian, diffable in git, and editable by hand. Losing that would cost
editor-in-chief control — the human merging, superseding and deciding — which is
the part a hosted vendor structurally cannot offer.

**Cloud-first provider defaults.** Local Ollama is not the happy path there; the
configuration assumes Gemini, Claude or OpenAI. It is runnable locally, but the
grain of the project runs the other way, and "lokaal, altijd" is not a preference
here.

**`/chat` as a retrieval interface.** Answering a natural-language question about
a peer means an LLM call on the read path. For KennisBank that is the hot path,
where the budget is sub-second and a cold model load costs tens of seconds. The
same value arrives through precomputed representations without the latency.

## What this says about KennisBank's position

A well-funded team solving the same problem sharpens rather than threatens the
case for this project. Honcho competes on retrieval quality as a service.
KennisBank's differentiator is not that it retrieves better — that claim would
need the benchmark work their evals represent — but that the knowledge stays
local, stays readable, stays diffable, and stays under human editorial control,
while getting sharper over time.

The one place they are unambiguously ahead is measurement. They publish against
LongMemEval and LoCoMo; KennisBank has an eval harness and eval sets but no
comparable public number. That is a gap in evidence, not in architecture, and it
is worth remembering the next time a design argument here is settled by taste.

## Addendum: the product site (honcho.dev, same day)

The repository shows their architecture; the landing page shows their bets —
what a funded team in the same problem space believes is worth paying Google
for. (The page was reached through a paid ad on the query "memory for ai
agents"; the category has commercial heat.) What is new relative to the
repository review, and what each item means here:

**The pitch is token economics, not recall quality.** Headline "Memory That
Reasons"; tagline "Better context. Fewer tokens."; the closing line "Use the
10K tokens you need, not the 100K you don't", with a claimed 60–90% token
saving. They sell memory as *cost reduction on the context window*. That is a
direct market validation of the token-ceiling work adopted in this review
(TASK-193): the bound on assembled context is not a hygiene feature, it is the
thing the market prices. KennisBank's version of "fewer tokens" is fewer
injected tokens per prompt — same lever, no invoice.

**Reasoning effort at recall time is a dial, and they charge per position on
it.** Query pricing runs $0.001 (Minimal) to $0.50 (Max) per query — a 500×
range for the same question answered with more or less reasoning. That is a
product expression of an architectural knob KennisBank also has but frames as
levels (L0–L3, cheap lookup versus full bodies). The lesson is not to add
recall-time reasoning to the hot path — that rejection stands — but that
*tiered effort with an explicit opt-in* is a validated shape: the default stays
sub-second, and a deeper pass is something the user asks for, knowing it costs.

**Custom small models for the memory task** ("Neuromancer reasoning engine",
claiming SOTA at lower cost and latency). The same move this vault already
made empirically: the judge-model measurement picked qwen3.5:4b over 9b, and
the embedding sweep picked the 4b embedder. Smallest model that does the job —
independently converged on, again.

**"Dreaming" is productized background reasoning**: Pattern Identification,
Hypothesis Testing, Conflict Resolution. KennisBank has deterministic analogs
for two of the three already shipped — `conflict-scan.py` and `kb-state-audit`
are Conflict Resolution; the supersede pass is a narrow Hypothesis Test — and
the third, Pattern Identification, is exactly the queued distillation-proposal
job (TASK-174). A funded competitor naming that background triad as a headline
feature is decent evidence the queue is pointed at the right thing.

**They are distributing into KennisBank's exact niche.** A Claude Code plugin,
an OpenAI Codex integration, an agent skill installed via npx, and "Coding
Agents" as a named use case. The overlap is no longer conceptual; it is the
same clients. This sharpens rather than weakens the differentiation, because
their model is ingestion priced per million tokens into a hosted service —
the structural opposite of local, readable, diffable, MIT.

**Benchmark numbers now exist** (LoCoMo 89.9%, LongMemEval-S 90.4%, BEAM
0.630/0.618, ~200ms response) where the repository only had a claim. Still
vendor-reported, still the benchmarks the field's own comparison calls
insufficient, so the do-not-chase position stands. One honest comparative
footnote: their ~200ms is a hosted service's network round-trip; the local
recall path here measures 460–520ms p50 including a local embed. Same order of
magnitude, no server, no per-query bill.

**Global versus local representations, with knowledge asymmetry.** The docs
detail what the repo README implied: a message updates the writer's global
self-representation and each observer's local representation of the writer —
and a peer learns nothing from conversations it was not in. Elegant, genuinely
multi-party, and still the half of the model TASK-194 deliberately does not
adopt while the vault has one observed subject.

**What nobody is selling, still.** Their cadence-driven summaries (short every
20 messages, long every 60) automate consolidation on a schedule; their
dreaming optimizes representations in the background. Nothing on the site —
or anywhere in the field's marketing — claims to know whether an injected
memory *helped the task*. The outcome loop (TASK-173) remains white space, in
the market as much as in the literature.

## Sources

- [plastic-labs/honcho](https://github.com/plastic-labs/honcho) — repository and
  README, retrieved 2026-08-15.
- [honcho.dev](https://www.honcho.dev/) landing page and
  [architecture docs](https://honcho.dev/docs/v2/documentation/core-concepts/architecture),
  retrieved 2026-08-15.

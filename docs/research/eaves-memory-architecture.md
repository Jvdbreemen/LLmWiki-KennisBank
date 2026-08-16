# Eaves: what a multi-agent memory system looks like from the other side

Status: research, with three tasks filed
Date: 2026-08-16
Reviewed: [mackerson/eaves](https://github.com/mackerson/eaves) v0.4.2 at
`fce7f20` (2026-08-15), read in full on the memory, shadow and channel paths
Baseline: the v0.32.0 line, after `honcho-memory-architecture.md`,
`agent-memory-field-review-and-strategy.md` and `narrowed-supersede-2026-08-16`
Question this answers: does Eaves hold anything that makes KennisBank's memory
work better when several agents use it at the same time?

## Executive conclusion

Yes, three things — and the most valuable one is a defect it exposed in our own
code rather than anything to copy from theirs.

Eaves is the first system reviewed here that runs several agents against one
memory store as its normal mode, so it has had to answer questions KennisBank
has so far only been able to postpone. Its answers are cruder than ours
everywhere the *lifecycle* of a fragment is concerned — no judge, no status,
no supersession, no validity interval, key-overwrite as the only update — and
sharper than ours everywhere *several writers* are concerned. That split is
exactly what makes it worth reading: it is weak where we are strong, so the
overlap is small and the transferable part is unusually clean.

The three findings, in descending order of value:

1. **Our SessionStart freshness gate is vault-global, not per client.** A
   second agent starting within 300 seconds of the first silently receives no
   memory-health notice, no distillation notice, no orientation and no
   upstream warning. This is ours, not Eaves' — asking their question of our
   code is what surfaced it. **TASK-195.**
2. **Weighted min-max fusion instead of RRF.** Eaves fuses its lexical and
   semantic arms by weight, not by rank, and renormalises the weights onto
   whichever arms actually fired. That is precisely the mechanism that would
   have let the memory layer keep a lexical arm at a small weight, instead of
   `_kbindex.py` having to delete it because RRF weighs a weak ranking equally
   with a strong one. Eval-gated. **TASK-196.**
3. **A working-state tier that is held, not retrieved.** Eaves keeps small,
   always-in-context, agent-edited core-memory blocks alongside the searchable
   archive. KennisBank has the archive and the retrieval, and its only
   equivalent of a running summary — `kb-checkpoint.py` — is written by hand.
   **TASK-197.**

Nothing in Eaves' capture or lifecycle handling should be adopted. Details
under "Rejected".

## What Eaves is

A local-first Electron desktop app (TypeScript, better-sqlite3) for talking to
several model providers — Claude, GPT, Gemini, OpenRouter, local models —
through one interface, where each configured *agent* is a persistent persona
with its own memory. Storage is SQLite on the device, extension is a sandboxed
plugin system, and sync is optional LAN peer-to-peer. The licence and the
stated privacy position are close enough to KennisBank's that the comparison is
fair rather than aspirational: same locality constraint, same "no cloud without
asking" default, a different application shape.

Its memory is three separate mechanisms, and the separation is the design:

**`memory_blocks` — core memory, per agent, always in context.** Labelled
blocks (`human`, `current_focus` seeded by default), each with a `char_limit`
of 2000 and a `read_only` flag. The agent edits them itself through exactly two
tools, `core_memory_replace` and `core_memory_append`. There is deliberately no
read tool: the blocks are already in the prompt, so reading them is free and a
tool call would only waste a turn.

**`memory_entries` — the archive, shared by every agent.** Key/value with
free-form JSON metadata, an FTS5 index over value+key, and a `vec0` table whose
dimensions are bound at runtime to the active embedder's signature. Writes are
upserts by key; embedding happens asynchronously after the durable write, so a
store never blocks on an embedding call. Search fuses bm25 and vector distance.

**`agent_memories` — a per-agent review queue.** Rows are created with status
`candidate` and move to `approved` through a UI, individually or in bulk. It is
the human gate that the rest of the system does not use: nothing in the archive
path passes through it.

Around those sit two services that matter more to this review than the storage
does — `ShadowService` and `ChannelDispatcher` — described below.

## The multi-agent question, answered concretely

Eaves' answer has four parts. Each one is a decision KennisBank will have to
make, whether or not it makes the same one.

### 1. Two tiers, two scopes

Core memory is **private per agent** (`memory_blocks.agent_id`, and every read
goes through `getByAgent(agentId)`). The archive is **one shared pool**: any
agent can `search_memories` its way to anything any other agent stored.

That split is the whole model, and it is a good one. Working state — who am I
talking to, what am I in the middle of — is per agent because it *is* per
agent. Durable facts are shared because a fact that is true for one agent is
true for the others. Neither tier needs a permission system to be useful, which
is why the design costs almost nothing.

### 2. Attribution is written and never read

`store` puts `metadata.agentId` on the entry and the repository writes an
`agent_id` column. `search`, `list` and `retrieve` never filter on either. So
Eaves records who wrote a memory and then cannot answer a question about it.

This is TASK-194 (observer provenance) from the Honcho review, arriving from a
second direction — and with a useful extra data point: Eaves has had the column
since the schema was written and still has not used it. Writing the field is
the easy half; the value is in what reads it. TASK-194's acceptance criteria
already say so (criterion #4, "queryable from the index for per-client recall
measurement"). This review changes nothing about that task except its
confidence.

### 3. Observer agents ("shadows")

A shadow is a real agent with `archetype.type === 'shadow'`. It may name a
`leadAgentId`, in which case it sees only that agent's events, or omit it, in
which case it sees everything. Instances are keyed by the *shadow's* id, so
several shadows can watch one lead. Each buffers events until 20 have arrived
or 90 seconds have passed, renders them into a digest capped at 4000
characters, and asks its own model for a JSON object with two fields: a `focus`
string that replaces the target's `current_focus` block wholesale, and a list
of durable `facts` upserted into the archive by key. Memories land against the
lead when there is one, against the shadow itself when there is not. There is
no human gate; the Memory view is described in the code as "the correction
surface".

The *architecture* here is the interesting part and the *policy* is the part to
leave alone. An observer that is itself an agent, scoped either to one lead or
to everything, is a clean way to express "extract memory from what is
happening" without wiring extraction into the turn loop. But writing a
model's raw JSON straight into memory with no verification is a step backwards
from what `_judge.py` and the status lifecycle already do here.

### 4. Agent-to-agent traffic is bounded by a budget, not a lock

`ChannelDispatcher` runs turns only from explicit dispatch intents. Its comment
is worth quoting because it records a real incident: "Deliberately NO
message:created / message:updated subscriptions: repository storage events
never start a turn (ADR-001 Decision 3 — this also closes the forged-event
dispatch chain from #39)." On top of that sit `MAX_CHAIN_DEPTH = 3`, a
2-second per-channel cooldown, and an active-dispatch set.

KennisBank has no agent-to-agent messaging and should not acquire any. The
transferable lesson is narrower and it is about *our* concurrency work: a
storage event is not an authorisation to do work. TASK-183 (the index-lock
handoff window) is the same class of problem — two workers deciding
independently that it is their turn.

## Where the two designs agree

Independently, and therefore worth noting:

- **Bounded context assembly.** `buildMemoryContext` caps its archive manifest
  at 60 entries and emits keys, tags and descriptions but never values, with
  an explicit "… and N more (N total)" tail. The commit comment says it
  "replaces the old raw `list('agent:{id}:*')` dump". TASK-193 reached the same
  conclusion here and is Done.
- **Writes never block on the network.** Their `store` returns as soon as the
  row and the FTS entry are durable, then embeds in the background; our sweep
  is off the hot path for the same reason (PRINCIPLES #1).
- **Bounded, resumable backfill.** `backfillVectors(max)` embeds in batches of
  32, stops on the first failing batch, and returns a count — the same shape as
  `embed-sweep.py`.
- **The vector table is bound to the embedder.** `ensureVecTable(signature,
  dims)` drops and rebuilds when either changes, because vectors from a
  different model are incomparable. ADR-0001 and the `unit_norm` marker in
  `_kbindex.py` are our version of the same rule.

Four independent arrivals at the same answer is decent evidence those four are
structural rather than taste.

## Adopted

### TASK-195 — the freshness gate needs to be per client

`kb-session-start.py` reads one state file for the whole vault
(`state_path = runtime / STATE_NAME`, line 492) and gates on elapsed time alone
(`is_fresh`, line 256). `_write_state` records which client last completed —
and nothing reads it.

The gate conflates two different questions:

- *Has the maintenance work been done recently?* Vault-global, and correctly so:
  the index only needs rebuilding once no matter how many agents start.
- *Has **this agent** been told what it needs to know?* Per client, and
  currently answered with the wrong state.

Concretely: start Claude Code, then start Codex 60 seconds later. The second
session returns early at line 524 and never runs NOTIFICATIONS, so it gets no
`memory-notify` health warning, no `distill-notify` prompt, no orientation
summary and no `git-upstream-check`. The agent is not told anything is wrong;
the output is simply empty, which is indistinguishable from "nothing to report".
Silence is the designed success signal of every one of those scripts, which is
what makes the failure invisible.

`kb-checkpoint.py` already sits deliberately in front of the gate for a related
reason (TASK-79: a `source=compact` start is nearly always inside the window).
That is the same problem solved once, for one script, by moving it out of the
gate — rather than by fixing the gate.

The fix is small: key the freshness state per client while leaving the
maintenance lock global. Notifications are cheap reads; maintenance is not.

### TASK-197 — a working-state tier, shared rather than per agent

The one place KennisBank should deliberately *invert* Eaves' design.

Eaves scopes `current_focus` per agent because its agents are different
personas with different jobs. KennisBank has one subject: the vault owner's
work. "What is being worked on right now" is the same answer for Claude Code,
Codex and the Copilot CLI, and each of them currently rediscovers it from
scratch. A shared focus block is both cheaper than per-agent blocks and more
useful — it is the mechanism by which three clients stop feeling like three
systems.

We have the manual version already: `/checkpoint` writes markdown, and
`kb-checkpoint.py --notify` surfaces it before the freshness gate. What is
missing is the automatic sibling. Per PRINCIPLES #3, what needs manual
discipline does not happen.

Scope discipline matters here. This must not become a second memory layer: one
small block, hard character cap, written by the existing off-hot-path sweep,
injected at SessionStart, no retrieval and no index. If it needs a rank factor,
it has become something else and the task is wrong.

## Queued behind a measurement

### TASK-196 — weighted fusion versus RRF

The sharpest technical idea in the repository, and it lands on a decision we
have already made and measured.

`_kbindex.py` fuses its arms with RRF and, on the memory layer, has had to drop
the lexical arm entirely. The comment there is precise about why: "RRF weighs
both rankings equally, which pays off only when they are comparably strong: a
weak ranking pushes good hits out of the top k." On wiki the arms are close and
fusion beats both; on memory they differ by nearly a factor two in MRR and
fusion beat neither, so it was removed (TASK-128,
`embedding-model-sweep-2026-08.md`).

Eaves' `fuseScores` does not have that failure mode. It min-max normalises each
signal within the candidate pool, weights them (`SEMANTIC_WEIGHT = 0.65`), and
— the part that matters — renormalises the weights onto whichever signals
actually fired, so a query that only hits one arm still tops out near 1.0
instead of being scaled down by its weight. Their own comment names the
motivation exactly: RRF "keeps only rank and, on a small corpus, collapses
every hit into a ~0.03 blur", while weighted min-max "preserves the gradient".

So the question TASK-128 could not ask is now askable: **is the memory layer's
lexical arm worthless, or was it only worthless at equal weight?** A literal
term match is an independent relevance signal — our own `min_cos` code path
says so, letting FTS hits bypass the cosine floor — and dropping the arm threw
that signal away along with the fusion that mishandled it.

One caveat from their code carries over unchanged, and it is the reason this is
eval-gated rather than adopted: min-max is intra-query relative, never
cross-query calibrated. The best item in any pool lands near 1.0 even when the
query is off-topic. So the fused score can order results and express confidence
*within* one result set, and can never become a `score > X` gate. Our `min_cos`
floor stays on the cosine, exactly where it is now.

Winner rule as usual: it flips only if it beats the current default on the
frozen eval set. If it does not, the finding is that the arm really is
worthless on short atomic fragments, which is worth knowing too.

## Rejected, with reasons

**Key-overwrite as the update mechanism.** `store` upserts by key, so a
corrected fact destroys the one it corrects. There is no supersession chain, no
`valid_from`/`valid_until`, no status. KennisBank's bi-temporal model exists
because "what did I believe in June" is a real question; `narrowed-supersede`
was written last week precisely to stop supersession from being too
destructive. Adopting this would undo two months of work.

**Unverified writes.** `consolidateDream` writes model output into memory with
no judge and no gate. Our capture path — extract, embed, dedup, reconcile,
judge, status — is the more expensive and better answer, and TASK-178 covers
making it fully autonomous without lowering the bar.

**`expires_at` without a pruner.** Their `AgentMemoryRepository` carries an
honest comment: the column exists, nothing writes it, the prune was deleted
because wiring it up "would have been a permanent no-op that read as coverage."
Not a defect to adopt — a habit to keep. It is the same lesson TASK-160 found
in `trust_factor`: a field with one value is not a field.

**The candidate/approved review queue.** `agent_memories` is a human gate that
the archive path does not use, so it gates nothing while looking like it does.
Our direction is the opposite (TASK-178, autonomous lifecycle, no required
human approval).

**Per-agent private core memory.** Correct for their application shape, wrong
for ours — see TASK-197.

**Everything about channels.** No agent-to-agent messaging here, so no loop
budget needed. The generalisable half — a storage event must never authorise
work — is already the shape of TASK-183.

## What this says about KennisBank's position

The field review's conclusion holds and gains a data point. Eaves is a fifth
independent system that solves *personalization* memory well and does not
attempt *institutional* memory at all: it remembers what you told it, never
whether remembering helped. Its `agent_memories` review queue is the only
outcome-shaped mechanism in the codebase and nothing routes through it.

What is new is the axis. Every previous review (Honcho, EverOS, EverMemOS,
Memanto) compared single-subject memory quality, where KennisBank is strong.
Eaves is the first to compare *concurrency*, and there we are behind — not
architecturally, but in the unexamined places. One shared vault, one shared
index, three clients that can start within seconds of each other, and a
freshness gate that has never been asked which client it is talking to.

The retrieval loop measures itself. The multi-client loop does not measure
itself at all, because nothing has been counting how often a second client
starts inside a first client's window. TASK-195 fixes the gate; the more
durable lesson is that "several agents at once" is a mode this vault has been
running in for two releases without a single measurement pointed at it.

## Sources

- [mackerson/eaves](https://github.com/mackerson/eaves) v0.4.2, `fce7f20`,
  read at `src/main/repositories/{MemoryBlockRepository,MemoryEntryRepository,AgentMemoryRepository}.ts`,
  `src/main/services/{CoreMemoryBackend,memoryContext,coreMemoryTools,ShadowService,shadowConsolidate,ChannelDispatcher}.ts`,
  `src/shared/shadowDefaults.ts`
- `docs/research/honcho-memory-architecture.md` — TASK-193 (Done), TASK-194
- `docs/research/agent-memory-field-review-and-strategy.md` — the
  Experience/Memory distinction
- `docs/research/embedding-model-sweep-2026-08.md` — TASK-128, why the memory
  layer lost its lexical arm
- `docs/research/narrowed-supersede-2026-08-16.md` — the supersession model
  this review declines to trade away

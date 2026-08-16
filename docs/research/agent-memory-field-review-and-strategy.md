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

### 3. Dreaming — autonomous wiki drafts from memory clusters (TASK-174)

Principle #3: what requires manual discipline does not happen. Distillation to
the wiki is human-triggered; `distill-notify.py` counts and mentions. Upgraded
by owner directive (2026-08-15) from proposal-surfacing to draft-writing: an
off-hours dream pass clusters the memory layer (LLM consolidation, not the
graph communities TASK-134 measured as insufficient), detects clusters no wiki
article covers, and writes real `status: draft` articles into the vault with
full provenance. Draft-to-published promotion stays the one human act — the
wiki is the layer the human reads. The wiki layer's saturation (recall@5 =
1.000) makes this about keeping the curated layer fed, not about its
retrieval. TASK-165's caution applies to the drafting half: drafts carry
their sources, in English, rather than re-summarising them.

### Owner decisions, recorded same day

Three directives on 2026-08-15 moved items from "queued analysis" to "decided
direction": the memory lifecycle runs fully autonomously with no required
human (TASK-178 — autonomous quarantine exit via grounded verification and
corroboration, deterministic-only demotion, signal-driven noise once the
sensor is fixed); skills evolve autonomously between sessions (TASK-177);
and dreaming writes drafts rather than proposals (TASK-174 above). The
usage-detection sensor these depend on gets verified and fixed first
(TASK-179): the current scan counts only tool-call reads, so the most
successful injections — snippet sufficient, no Read needed — are invisible,
which is the probable reason usage measured as noise in the factor
decomposition. Autonomy built on that sensor would down-weight the best
memories first; the sensor precedes the autonomy.

### 4. Observer provenance (TASK-194) — now with an empirical argument

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
5. **TASK-174 distillation proposals; TASK-194 observer field** alongside
   TASK-162 step 2, since corroboration and observer attribution touch the same
   sweep path.
6. **TASK-175 procedure promotion**, gated on telemetry.

## Follow-up: the primary sources behind the eight frameworks

Added 2026-08-15, after chasing the vectorize comparison down to papers and
repositories. Licences first, because they decide what can transfer:

| System | Primary source | Licence | Transfer allowed |
| --- | --- | --- | --- |
| Hindsight | arXiv 2512.12818, github.com/vectorize-io | **MIT** | Ideas *and* code |
| Zep/Graphiti | arXiv 2501.13956, github.com/getzep/graphiti | **Apache 2.0** | Ideas and code (with notice) |
| Mem0 | arXiv 2504.19413 | Apache 2.0 | Already transferred — `_reconcile` cites the pattern |
| Honcho | reviewed separately | AGPL-3.0 | Ideas only |
| PROJECTMEM | arXiv 2606.12329, github.com/riponcm/projectmem | paper CC-BY-4.0 | Prior art to read |

Note the article ranking these systems is published by vectorize.io, which also
builds Hindsight — the 94.6% at the top of its own comparison table is the
publisher's product. The paper and ablations stand on their own, but the
ranking should be read as a vendor's.

Four findings change or sharpen queued work; the rest confirmed what the
August measurements already established.

**Hindsight's ablation is external evidence for TASK-171.** The top LongMemEval
scorer is built on three epistemically distinct networks — world facts,
experience, opinions — extracted and retrieved separately, and collapsing them
"substantially reduces reasoning quality, particularly when distinguishing
between observed facts and derived beliefs." That is the stated-versus-inferred
axis, load-bearing in the best-scoring public system. The local measurement
still gates the task; the expected outcome moved.

**PROJECTMEM is prior art for TASK-173.** "A local-first, event-sourced memory
and judgment layer for AI coding agents", whose judgment layer assesses whether
memories "proved beneficial or harmful during task execution" — the outcome
loop, in this exact niche, under the same local-first constraint. Maturity
unknown; read before designing, especially their outcome definition and their
attribution of outcomes to individual memories. The white-space claim needs
qualifying: no product sells this, but the literature has an attempt.

**Graphiti does bi-temporality at the fact level; KennisBank does it at the
document level.** Automatic edge invalidation on contradiction, full lineage
preserved, and point-in-time queries ("what was true on date X"). KennisBank's
frontmatter supports the same reconstruction in principle — `valid_from`,
`valid_until`, the closed-log — but no query surface exposes it. Not queued:
there is no demonstrated use case yet, and a point-in-time view is a rendered
view of data that already exists, buildable the day a question needs it. Their
requirement list (Neo4j or equivalent) is also the reminder of what the
SQLite-and-markdown constraint buys.

**Hindsight's recall weights strategies per query** rather than uniformly — the
opposite of the uniform factor product that `rank-factors-2026-08-14` caught
overwriting the ranking here. Their ablation says multi-method recall beats any
single strategy on their corpus; this vault's measurement says the lexical arm
hurt its memory layer. Both can be true — per-query routing is exactly the kind
of mechanism that would reconcile them — but it is tuning-by-instrument work
and sits behind TASK-161's eval set like every other ranking change.

Confirmed rather than new: Mem0's ADD/UPDATE/DELETE/NOOP loop is already the
`_reconcile` pattern; Letta/MemGPT's self-editing core blocks are what the
human-edited CLAUDE.md identity layer does deliberately by hand; LangMem and
LlamaIndex Memory are the lock-in cautionary tales already recorded above.

### Memanto (added 2026-08-15, via an @moorcheh_ai post)

Memanto (github.com/moorcheh-ai/memanto, **MIT**, ~1.8k stars, arXiv
2604.22085) is Moorcheh's agent-memory layer: "storage is a filing cabinet,
Memanto is the chief of staff." Local Docker+Ollama mode exists alongside the
hosted engine. One real steal, several convergences worth recording, and one
claimed differentiator that does not survive contact with this vault's
architecture.

**The steal: OKF has a second implementation (TASK-176).** Memanto exports its
estate "as plain Markdown in the Open Knowledge Format... intentionally
supporting competitor implementations" — the same
GoogleCloudPlatform/knowledge-catalog v0.2 spec TASK-92 adopted for export.
That changes what TASK-92's bundle is: not only a rendered view but an
interchange surface another shipping system reads and writes. TASK-176 queues
the interop check — outbound bundle ingested by a local Memanto, trust tiers
surviving the round trip, and a mapping table between their 13 memory
categories and this vault's 4 types. Divergences are findings about a young
spec, worth filing upstream.

**Determinism is their headline; this vault already has the property and does
not claim it.** Their pitch — deterministic retrieval, no behavioral drift
from approximate-nearest-neighbour search — is a property KennisBank gets
structurally: brute-force vec0 KNN plus FTS5, proven bit-reproducible in the
L2 scene report (two bracketing baseline runs, zero flips). At personal-vault
scale, exact search is affordable and ANN drift is a problem other people
have. The one leak is known and recorded: day-granular recency reordered 146
of 856 near-ties across a midnight boundary — under the same TASK-161 freeze
as every other `_rank` change. A 1.8k-star product marketing this property as
its differentiator suggests the README here could afford one sentence
claiming it.

**Convergences, at this point unremarkable and therefore load-bearing:**
supersede-rather-than-append "preserving what was believed and when" is this
vault's supersession + closed-log + `valid_until`, verbatim; their scheduled
daily curation (merge duplicates, flag contradictions, expire) is the
maintenance pass family; typed memories with confidence are `memory_type` +
`importance`. Their `--as-of` / `--changed-since` recall filters are the
**second independent sighting** of a point-in-time query surface (Graphiti's
was the first) — still unqueued here for lack of a use case, but two
sightings upgrade it from idea to pattern, and the bi-temporal frontmatter
already contains everything such a surface would read.

**What does not transfer: "no ingestion cost, no indexing delay."** That is a
property of their hosted binarization engine (MIB/ITS), not of their memory
design. KennisBank's ingestion cost *is* the local embed, which no scoring
trick removes, and its SQLite index is searchable the moment the embed lands.
The 13-category taxonomy is also not adopted: thirteen types is
over-taxonomization by this repo's standards, though `goal` and `instruction`
name real classes the current four types do not — worth remembering if the
TASK-172 dead-end audit ends up touching the extraction taxonomy anyway.

Their README's benchmark note deserves quoting because it is the position
this document keeps arguing: "cross-project scores on these benchmarks are
not comparable" — from a project reporting 89.8% on LongMemEval.

### EverMind / EverOS / EverMemOS (added 2026-08-15, via an evermind.ai listicle)

The listicle itself (evermind.ai ranks itself #3 in its own comparison,
without publishing its own scores) is the weakest source in this document.
What it led to is not.

**EverOS (github.com/EverMind-AI/EverOS, Apache 2.0, ~12k stars) is the
closest direct competitor to KennisBank found in this entire review.** Its
stack is this vault's stack, independently arrived at: markdown files as "the
canonical source of truth (readable, editable, Git-versioned)", SQLite for
local indexing, vectors beside it (LanceDB where this vault uses sqlite-vec),
offline "memory evolution that merges episode clusters and refines profiles
and skills between sessions" — the cold-path sweep — plus a Claude Code
plugin and MCP surface into the same clients. A 12k-star Apache project now
occupies the "local-first, Markdown-native, user-owned" lane by name.

What that narrows, and what it does not. The positioning sentence "plain
markdown, local index, your machine" is no longer unique. What remains
KennisBank's and not theirs: **fully local models** (EverOS's minimum tier
requires an OpenRouter API key; this vault's floor is Ollama and no key at
all), the **editorial quality gate** (judge, quarantine, human review-log —
their evolution is autonomous), **bi-temporality with a reversible
supersession lifecycle**, and the **measurement discipline** (private eval
sets, pre-registered gates, published retractions). Those four are the
differentiators worth stating in the README now that the lane is shared.
Apache 2.0 also means their code is inspectable and reusable with notice —
their skill-record format and episode-cluster merge are worth reading when
TASK-175 and TASK-174 respectively come up, since EverOS ships a version of
both ("agent skill records stored as .md files", refined between sessions).

Update, same day: the owner adopted the autonomous-evolution half of that
idea outright — TASK-177 copies EverOS's between-session skill refinement,
with KennisBank-native rails (grounded-verifier asymmetry, git-commit
reversibility, closed-log auditability, kb-state-audit as a hard gate) in
place of a human gate. Creation of new skills (TASK-175) still proposes; the
split between autonomous refinement and gated creation is recorded as a
deliberate decision the owner can flatten later. This narrows the editorial
differentiator above to "the quality gate on knowledge a human reads" —
skills are executed, not read, and now evolve on the memory subsystem's
default-on precedent instead.

**EverMemOS (arXiv 2601.02163) is the scene tier this vault already
falsified — with the one variable the local experiment said would matter.**
Their pipeline is MemCells (episodic traces from dialogue) consolidated into
thematic MemScenes, with "reconstructive recollection" doing scene-guided
retrieval. The L2 scene experiment here (TASK-134) measured exactly that
architecture with graph-community clustering and rejected it against a
pre-registered winner rule — while recording that the oracle bound (+0.040
recall@5, p < 0.0001) would pay "if a clustering five times better than graph
communities existed." LLM-consolidated thematic scenes are precisely the
candidate for that better clusterer. This does not reopen TASK-134: their
SOTA claim is on conversational benchmarks, and TASK-137 established the
local oracle was computed against a routing rule the code does not use, so
any re-run owes that fix first. But if the scene question ever returns, the
first arm to test is LLM consolidation, not another graph algorithm — the
door the null result left open now has a named occupant.

**The benchmark tables have stopped agreeing, which is the strongest
do-not-chase evidence yet.** The same systems, scored by two vendor
comparisons in the same month: Mem0 at 49.0% LongMemEval (vectorize's table)
and 94.4% (EverMind's); Zep at 63.8% and 90.2%. Forty-five-point swings on
the same benchmark mean the number measures the evaluation harness, not the
system. Memanto's caveat, EverMind's self-ranking, and this spread together
close the question of whether public memory benchmarks can arbitrate
anything for this project: they cannot.

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
- Follow-up primary sources: Hindsight (arXiv 2512.12818), Zep/Graphiti (arXiv
  2501.13956, github.com/getzep/graphiti), PROJECTMEM (arXiv 2606.12329,
  github.com/riponcm/projectmem). Retrieved 2026-08-15.
- Memanto (arXiv 2604.22085, github.com/moorcheh-ai/memanto, MIT) and the
  Moorcheh engine docs (docs.moorcheh.ai). Retrieved 2026-08-15, via an
  @moorcheh_ai X post (the post itself is login-walled; the org and paper are
  primary).
- EverOS (github.com/EverMind-AI/EverOS, Apache 2.0) and EverMemOS (arXiv
  2601.02163, github.com/EverMind-AI/EverMemOS). Retrieved 2026-08-15, via
  evermind.ai's own comparison listicle — a vendor source; the repos and paper
  are primary.

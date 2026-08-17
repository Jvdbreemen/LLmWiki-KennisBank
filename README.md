# LLmWiki-KennisBank

**English** · [Nederlands](README.nl.md)

> **Installing with an AI agent?** (Claude Code, Claude Cowork, Codex,
> Copilot CLI, OpenCode) → follow the
> **[Agent install guide](docs/AGENT-INSTALL.md)**. One command per platform;
> `AGENTS.md` is the underlying deployment contract.

**A sovereign memory layer for serious AI work.**

Every agent session creates valuable context: decisions, fixes, preferences,
architecture trade-offs, dead ends, and lessons you do not want to rediscover
next week. Then the model forgets. KennisBank turns that temporary context into
a durable local knowledge system for Claude Code, Codex, OpenCode, the GitHub
Copilot CLI, and other developer agents.

It captures what happened, distils it into a sourced wiki, extracts time-aware
memories, retrieves the right knowledge before the next answer, and measures
whether that knowledge actually helped. The result is an AI workspace that gets
sharper over time without handing your private work to a hosted memory vendor.

Plain markdown. Local SQLite. Local Ollama by default. Your own machine. You
stay the editor-in-chief: the system proposes, quarantines, and flags, but a
human merges, supersedes, and decides. Open the vault in Obsidian and it is
just notes. Very well-organized notes that happen to power an AI memory.

## First-class coding-agent integrations

One `setup.sh` flow installs and upgrades KennisBank for **Claude Code**,
**OpenAI Codex**, and the standalone **GitHub Copilot CLI** on Windows, macOS,
and Linux. OpenCode remains supported as an additional local client.

- Skill and generated prompt descriptions are English so every client can
  discover them consistently.
- Each client registers one fail-open coordinator at session start and one at
  exit. Independent jobs run concurrently, dependent work follows in explicit
  phases. Routine no-change output stays silent.
- A client may still show one generic row for each lifecycle event; those
  UI-owned rows cannot be suppressed portably while keeping automation.
- Setup replaces only legacy KennisBank start/exit entries and preserves
  unrelated user hooks plus prompt and presearch behavior.
- The same local stdio MCP server and explicitly pinned `KENNISBANK_VAULT`
  serve every installed client.

Install or upgrade selected clients:

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents claude,codex,copilot
```

After restarting the client, use `$sessiestart` and `$sessielog` in Codex
(`/prompts:sessiestart` remains a compatibility alias), or `/sessiestart` and
`/sessielog` in Copilot for explicit on-demand workflows.

Based on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): raw sessions go in, structured knowledge comes out. KennisBank extends the pattern into a closed loop:

```
capture ──> consolidate ──> retrieve ──> measure
   ^                                        │
   └────────────── learn <─────────────────┘
```

- **Capture**: session logs, transcript archiving, and an autonomous memory sweep that extracts, types, and judges candidate memories after each session.
- **Consolidate**: `/wiki` compiles sessions into wiki articles with per-claim provenance; new facts reconcile against old ones at write time (add, supersede, or drop) with a bi-temporal validity model.
- **Retrieve**: hooks inject relevant wiki articles and memories into every prompt, in any project: hybrid semantic + keyword search, ranked by relevance x recency x importance, expanded with the best-connected graph neighbour.
- **Measure**: a recall@k eval harness and a threshold calibration harness make every retrieval change testable instead of vibes-based.
- **Learn**: usage telemetry tracks which injected knowledge was actually used, boosting warm documents and keeping recently-used articles out of the stale list.

## Why this exists

Vendor memory systems (Mem0, Zep, Letta, Cognee) are powerful but cloud-shaped: your knowledge lives in their store, behind their API, on their pricing tier. KennisBank takes the two mechanisms that actually matter from that literature, temporal validity of facts and invalidation-at-write, and rebuilds them in plain markdown frontmatter plus SQLite. What you own stays portable; what the agent needs stays fast.

The design bias throughout: **deterministic where possible, LLM only where it adds judgment, fail-open everywhere**. A dead model never blocks a session, never loses a transcript, and never deletes verified knowledge.

## Feature highlights (v0.34.0)

### New in v0.34.0

The autonomous review learns what it already asked.

**A verdict that never changes no longer owns the budget.** v0.33.0 let
quarantined memories review themselves, but nothing remembered the answers,
so the grounded check re-asked the same question of the same passage every
sweep and got the same answer. On the vault that surfaced it, 40 of 40 slots
went to memories already graded `partial` by a whole-transcript reading,
while 49 newer memories were never judged at all. Trap 1 now records its own
outcomes and picks candidates in two tiers — never judged first, then
anything past its window, so retries rotate. It orders, it never excludes:
trap 1 reads a selected passage where the client reads the whole transcript,
so it still promotes memories the client called `partial`, and those
promotions are what drains the queue.

**The session-start message says something you can act on.** It used to
report one number and blame the settings or Ollama; on a vault where both
were fine and every memory had already been judged, that was three wrong
answers in one sentence. It now reports two counts — waiting for a verdict
versus judged and undecidable — and names the path that actually moves each,
including `memory-doctor.py decide` for the half only a person can settle.

**Bookkeeping that fails safely.** An inconclusive outcome expires in hours
rather than being ignored, because `no_transcript` is deterministic and would
otherwise park a broken source at the head of the queue forever. A refused
write no longer buys a cooldown. An unreadable state file is moved aside
instead of overwritten. No migration: the first sweep after upgrading
re-judges the oldest memories once, and the one after that is already
spending its budget on new knowledge.

### New in v0.33.0

The human leaves the memory loop.

**Quarantined memories now review themselves.** Three traps, each gated by
pre-registered measurements: the local model promotes what a memory's own
source transcript supports (never fabricated in 210 checks); the client LLM
adjudicates whole transcripts for the rest — behind an explicit
`auto_review_llm` toggle, OFF by default, because that is cloud; retraction
needs double agreement plus a failed refutation, capped and reversible.
First real run: 993 quarantined memories drained to 42, recall@1 +0.035.

**`/kennisbank:review` is an audit view now**, not a work queue: what the
system decided, on what evidence, with per-line undo (`demote` / `reopen`).
No step waits for a human.

**A wave of silently-failing defects is gone**, each adversarially verified
before fixing: a checkout that resolved the vault to `$HOME`, one env-var
typo that turned retrieval off for every session, a sweep fallback that
wrote zero memories, a default-model flip whose doctor check gave false
assurance, a lock race that ran two index builders at once, FTS rows that a
cap fix never reached, and memories judged with the embedding of their
previous content. The open backlog went to zero, every task carrying its
evidence or its parking reason.

### New in v0.32.0

The memory layer stops treating "newer statement about the same subject" as
"complete replacement".

**Every supersession this vault ever made was hand-labelled** (237 pairs,
twelve parallel readers, adversarial verification): 61% duplicate cleanups, 11%
genuine replacements — and **27% narrowed**, meaning the successor dropped
facts whose only carrier was the memory it closed. The recall path filters on
`status=current`, so those facts were not ranked lower; they were gone.

**Closing now requires covering.** Both closing judges demand that a successor
carries everything of lasting value before the old memory closes; partial
coverage keeps both. Replayed on all adjudicated pairs: knowledge-losing
closures drop from 57.8% to 37.5%, duplicate handling unchanged.

**The 64 wrongly closed memories are back.** Questions only they could answer
went from recall@5 0.000 to 0.333–0.600; the full 1224-question eval moved by
at most +0.002.

Also new: a freshness-aware eval set (89 questions, holdout kept unrun) that
delivered the third independent measurement against the recency weighting —
it does not beat raw cosine even on its own home ground.

### New in v0.31.1

A patch carrying a fix that was written, reviewed and approved two days ago and
then never merged — the follow-up commit that processed PR #114's Copilot review
stayed behind on its branch.

**The C4 reference prescribed the bug its own skill warns about.** It documented
the upgrade stamp as `git rev-parse --short $LATEST`, without `^{}`. Tags here
are annotated, so that records the tag object rather than the commit — how
v0.28.0 and v0.29.0 both ended up stamped with a SHA present in no branch.

A wording change in `kennisbank-upgrade`'s step 10 rides along. It reads better;
it does not change behaviour, and both forms were tested to confirm that.

### New in v0.31.0

A release about measurement: three things this repository believed turned out to
be wrong when checked, and the most useful change is one line.

**Long wiki articles are searchable again.** The full-text index stored only the
first 4000 characters of a document — the truncation the *embedding* model
needs, because it runs at a context size chosen to keep VRAM free. FTS5 has no
such limit and was paying it anyway, so 72 of 206 articles were partly invisible
to both halves of the hybrid search. Questions about material past that point go
from **recall@5 0.450 to 0.725**, with the existing 329-question set unchanged.

**Run `build-kb-index.py --rebuild` once after upgrading.** The stored text
changed but the file hashes did not, so the incremental build has nothing to
react to and you would keep the old index.

**Memories record where they came from.** A swept memory now carries
`source_chunk: "N/M"`, the chunk of its source transcript it was extracted from
— known at capture time and previously discarded.

**A near-miss JSON answer is no longer thrown away.** Four verifier replies in
56 were counted unparseable; all four held a well-formed object with broken
string delimiters. The repair runs only after an honest parse fails, and only
sticks if the result parses.

**The trust factor was measured and rejected.** Asking a local model whether a
memory is supported by its own source works better than expected and is still
the wrong thing to rank on: it answers `supported` for 88.7% of memories, and of
20 `unsupported` verdicts checked against whole transcripts, zero were right.
`supported` may raise trust; nothing may lower it. See
`docs/research/llm-trust-verification-2026-08-15.md`.

### New in v0.30.0

v0.29.0 fixed a memory layer that had quietly stopped capturing. This release is
about the decisions it makes now that it is capturing again — and about the fact
that you could not see any of them.

- **A closed memory is visible again, and reversible in practice.** The design
  rested on superseding being safe because nothing is deleted. True on disk and
  false everywhere else: recall filters on `current` and `/kennisbank:review`
  walks the `unverified` queue only, so a closed memory appeared in no path a
  human uses. Every closure is now logged with what replaced it and why, and
  `memory-doctor.py closed` / `reopen <stem>` is the way back.
- **`volatility: state | event` puts the update rule in the structure.** A state
  is replaced when its value changes; an event is never closed. Deriving that
  from prose scored 7/20, 5/20 and 4/20 across three models, so it is now
  decided once, at write time. On the live vault the guard protects three pairs
  that merely read alike — including the locations of two *different* skills at
  cosine 0.867.
- **`kb-state-audit.py` compares memories against an authority**, not against
  each other: 4 contradictions found on this vault, every one a stale
  `qwen3-embedding:8b`, with no model call — plus a coverage line saying where
  it was blind.
- **Finding supersede pairs is 11x faster with an identical result.** 1,271,215
  pairwise comparisons (1171.86 s) become an index query (106.94 s) returning
  the same 163 pairs. Exact, not approximate, with the old path as fallback.
- **Two prompts reordered and re-measured.** Reconcile: NOOP on unrelated pairs
  25% → **0%**. Supersede: recognition of real replacements 30% → **55%**.
- **Progress and an estimate on every long-running script**, because a sweep
  that runs ten minutes writing nothing is indistinguishable from a hang.
  `KB_NO_PROGRESS=1` silences it.

Two measurements contradicted the task that asked for them, and both are in the
changelog rather than quietly dropped: the supersede judge turns out **not** to
be too conservative (86% of its refusals are correct; the recorded history is
full of duplicate cleanups), and growing the corpus cost memory `recall@5`
0.778 → 0.768, below a floor set a day in advance.

### New in v0.29.0

> **Upgrading:** run `ollama pull qwen3.5:4b`, then set `"model"` in
> `<vault>/.claude/kennisbank-llm.json` to match. `setup.sh` copies that file on
> install and never overwrites it, so every existing vault carries a pin that
> beats the code default — leave it and your hooks keep loading the old model.

The memory layer had quietly stopped capturing, and nothing said so. Three
independent causes, each invisible for the same reason: every seam is fail-safe,
so a component that never answers looks exactly like one with nothing to report.

- **The judge was thinking away its own answer.** `qwen3.5` is a reasoning
  model, and its chain-of-thought spent the same context budget as the answer.
  Measured on three real pairs: 30-56 s per call, and **one in three came back
  empty** — after which `extract` returns `[]`, `judge` returns `unverified` and
  `reconcile` returns `ADD`, all silently. With `think: false`: 1.6 s, none
  empty.
- **Capture could read only one client's transcripts.** The parser knew Claude
  Code's shape alone, so Codex and Copilot sessions produced nothing: **39 of
  299 archived transcripts, 94 MB**, including single sessions of 21 and 26 MB.
  An unreadable transcript is still swept and still marked done, which looks
  exactly like a session where nothing happened. Now 7 of 299, together 0.07 MB.
- **Capture read six chunks of a session.** Measured over four long transcripts
  and 120 extractor calls: **78% of all unique knowledge sits beyond chunk 6**,
  with 0.9% duplicates. The cap assumed later chunks repeat; they do not. Now 40
  chunks and 60 memories per transcript, with a 150-chunk budget per run so a
  sweep cannot hold the GPU that retrieval needs.
- **One judge model, sized to coexist.** Eight surfaces wrote a model name and
  they no longer disagree. `qwen3.5:4b` at 3.13 GB fits beside
  `qwen3-embedding:4b` at 4.06 GB on a 16 GB card; the old `gemma4:12b` needed
  8.06 GB and evicted the embedder, after which every recall met a 30-60 s cold
  load against a 2 s budget.

### New in v0.28.0

> **Upgrading:** run `ollama pull qwen3-embedding:4b` first. `setup.sh`
> validates with `ollama show` and does not pull, so a vault without the model
> fails the install loudly. The first index build afterwards re-embeds the whole
> vault, because the model identity gates cache reuse.

- **A measured default instead of an inherited one.** Nine embedding models
  were run against this project's own eval sets, because published benchmarks
  rank models on public corpora and the margins here are two to four points.
  `qwen3-embedding:4b` wins on both layers while being faster (322 ms against
  347 ms warm p50) and holding 2.2 GB less on the card.
- **The memory layer was discarding a third of its own index.** Its similarity
  floor of 0.60 was calibrated on article-length text; memory fragments score
  structurally lower. Re-measured on the previous model too, so this was a
  standing fault rather than migration fallout. The floor is now 0.45.
- **Lexical search no longer drags the memory layer down.** RRF weighs its two
  rankings equally, which only pays off when they are comparably strong. On
  wiki they are, and the fusion beats both arms. On memory it beat neither, so
  the lexical half is gone there: recall@5 goes from 0.658 to 0.794.
- **Instruction prefixes per side**, so e5, embeddinggemma, arctic-embed and
  nomic can be run the way they were trained. Off by default; the document
  prefix is part of the cache identity.
- **Three measurement harnesses** — `embed-sweep.py` (models against a scratch
  vault), `recall-ablation.py` (dense versus lexical), `rerank-eval.py`
  (what a cross-encoder would add). Method and full results in
  `docs/research/embedding-model-sweep-2026-08.md`.

### New in v0.27.0

- **The embedding endpoint can no longer be pointed off-box without you saying
  so.** It was taken verbatim from `kennisbank-embed.json` and used before the
  API-key check, so a single config write sent every prompt — and the whole
  vault at the next rebuild — to an arbitrary host, with the no-cloud warning
  still reporting nothing. Locality is now enforced at the sink. If you run
  Ollama on another machine, set `KB_EMBED_ALLOW_REMOTE=1`.
- **Capture can no longer erase a memory you approved.** Two titles that
  slugified to the same filename landed on the same file, so a second capture
  overwrote an approved memory — status reset, text gone, no backup, and a
  success message. Colliding titles now land beside each other.
- **A missing index no longer costs seven seconds per prompt.** During an index
  rebuild every prompt fell back to parsing a 170 MB JSON cache in pure Python
  (6766 ms, 186 MB). That fallback is gone; you get the same visible notice the
  hook already shows for a cold model, and the hot path stays at ~1.2 s.
- **`setup.sh --skip-doctor`** for tests and CI that run `doctor.sh`
  themselves. A normal install still runs the closing gate.

### New in v0.26.1

- **The C4 documentation set now matches the code it describes.** The
  architecture plate specification named five vault folders where there are
  ten, claimed all four SQLite databases rebuild from the markdown when
  `kb-usage.db` cannot, and named an Atlas lens that was removed some time ago.
- **`claude-cli` is back in the documented consent boundary.** It is a cloud
  provider alongside OpenRouter, and the one that neither installer offers, so
  it is the one a reader most needs told about. The per-call cloud warning, and
  how its coverage differs from the setup-time one, is documented rather than
  left as an open question.

### New in v0.26.0

- **MCP tools now say what they are.** Every tool carries annotations, so a
  client knows which calls are read-only and may run in parallel. Six
  retrieval tools previously presented as possibly-destructive, costing
  confirmation prompts and serialisation on the interactive path.
- **A broken `mcp` install no longer looks healthy.** `pip install mcp` now
  lands on 2.x, where the old server API is gone; that used to produce a
  silently dead MCP server that exited 0. It now fails loudly and says why.
- **C4 architecture documentation** under `C4-Documentation/`: code,
  component, container and context levels, plus a dimensioned specification
  for a single high-level architecture plate.
- **The `mcp>=2` bump is deliberately not included.** A modern-only server
  breaks every client in use today; the upgrade is gated on a measurement.
  See `docs/superpowers/plans/mcp-2026-07-28-migration.md`.

### New in v0.25.0

- **An eval never counts as usage.** The recall ranking is fed by usage
  telemetry, so an eval that logged its own recall calls was measuring a
  signal it had just moved. `kb-eval` now disables usage telemetry for the
  duration of every run — unconditionally, no flag to remember — and
  restores the previous state afterwards, so learning continues as normal.
  The run says so on stderr, before and after the results.
- **`doctor.sh` catches a stray `KB_USAGE_DISABLE`.** Left in your shell
  profile, that variable silently stops the KennisBank from learning from
  usage. Now it is reported instead of invisible.

### New in v0.24.1

- **No more console pop-ups on Windows.** The detached index-maintenance
  worker spawned each background job with a freshly allocated visible
  console window at every session start. Jobs now run with
  `CREATE_NO_WINDOW`, so background maintenance is invisible again.
- **Eval-set privacy guard.** Personal eval sets can never enter the
  repository or a release (`.gitignore` + `test_eval_privacy.py`); the
  shipped example sets are fully fabricated.

### New in v0.24.0

- **Graph retrieval, proven and default-on.** The `(buur)` expansion entry
  now comes from the weighted graph index (`kb-graph.db`, sub-millisecond)
  instead of a regex over article bodies. Measured on a 329-question eval
  set: recall@1 0.745 -> 0.790, recall@5 -> 1.000, MRR 0.836 -> 0.882 —
  single-hop included. Toggle `graph_retrieval` turns it back off.
- **Evidence-first eval harness.** `kb-eval` now measures exactly what the
  hook runs (threshold + expansion parity), reports `--latency` p50/p95,
  and A/Bs variants with `--expand/--no-expand`; `kb-eval-gen.py` proposes
  candidate questions into drafts so eval sets grow without hand-writing.
  The same gate REJECTED llm_wiki's source-overlap ranking boost on real
  data — the knob exists but stays off, with the numbers recorded.
- **Human memory review everywhere.** `/kennisbank:review`,
  `memory-doctor.py pending/decide` and MCP `review_pending/review_decide`
  share one crash-safe decision path with the Atlas GUI: approve, reject or
  skip unverified memories; a failed write never reports as decided.
- **Deterministic gates.** `wiki-scan.py` closes /wiki's last free-form LLM
  decision point; a refusal gate keeps "I cannot answer this" out of the
  archive; kb-lint rejects conclusions cited as evidence (`self-source`)
  and surfaces index drift; `kb-normalize.py` fixes link/tag form after
  every LLM write; sweep-written memories carry `model_id`+`prompt_version`.
- **Atlas: heatmap, Cmd+K, facets — and CI.** The Overzicht lens shows a
  365-day activity heatmap and freshness buckets; Cmd/Ctrl+K jumps to any
  lens or document; the Recall Inspector filters by layer and exports the
  waterfall as JSON. Atlas sidecar+frontend tests now run in CI.
- **OKF v0.2 export.** `kb-okf-export.py` renders the vault as an Open
  Knowledge Format bundle — trust tiers map 1:1 onto the memory lifecycle;
  deterministic and byte-idempotent.

### New in v0.23.0

- **Vault orientation at session start.** `kb-orientation.py` summarises the
  vault in a few lines — document counts, recently changed articles,
  frequently used knowledge, open backlog tasks — with pure SQL reads,
  sub-second. `/sessiestart` runs it by default; the opt-in `orientation`
  toggle injects it at every session start.
- **Agent install guide.** `docs/AGENT-INSTALL.md` gives AI agents the
  shortest correct install path per platform (Claude Code, Codex, Copilot
  CLI, OpenCode, Claude Cowork), linked from the top of both READMEs.

### New in v0.22.0

- **A checkpoint primitive that survives context compaction.** `/checkpoint`
  saves a forward-looking work-state snapshot (active task, open decisions,
  next step) to the vault; an opt-in `checkpoints` toggle lets Claude's
  PreCompact hook write a stub automatically right before compaction, and the
  session-start coordinator now surfaces open checkpoints *before* its
  freshness gate — exactly the moment a compact event would otherwise swallow
  the notice. Codex and Copilot get the same recall path and a manual
  `$checkpoint` / `/checkpoint` command.
- **The knowledge graph became a queryable layer.** `graph.json` now loads
  into its own `kb-graph.db` (fingerprint-gated, rebuilt by the background
  worker), with a deterministic edge layer from wikilinks and frontmatter, a
  link-only provenance ring for session logs, and scope controlled by
  `.graphifyignore`. A full `kb-index.db` rebuild no longer drags the graph
  down with it.
- **Session start got an order of magnitude faster.** Cold start went from
  35.7 s to 1.3 s: the notification tier is decoupled, the staleness count
  moved to the background worker, and the status line only reads precomputed
  state. The test suite also stopped running `setup.sh` eighteen times.
- **Memory writes deduplicate at capture time**, a cold embedding model
  reports itself instead of failing silently, and every settings toggle is now
  test-coupled to the surfaces that manage it.

### New in v0.21.0

- **Retrieval has a relevance floor.** The hook used to inject the top-k
  unconditionally, so a prompt with nothing relevant still received the three
  least-bad documents, and the memory block had no gate at all. The threshold now
  sits on the cosine, taken free from the distance the vector index already
  returns. Your index rebuilds once on the first session after upgrading.
- **SessionStart stopped blocking.** It ran the three index builders inline —
  roughly 210 s worst case, and 300 s for Copilot, above the timeout that client
  declares for itself. Maintenance now runs in a detached worker behind a lock,
  which also ends two processes writing the same index concurrently.
- **The embedding cache left the hot path.** Every non-trivial prompt parsed tens
  of megabytes of JSON and scored the whole corpus in pure Python, to decide
  something the index already knows. It is now only the fallback for a broken
  index.
- **`/kennisbank-release`.** Releasing has been manual since v0.16.0. The skill
  captures the procedure, including the two steps that went wrong by hand last
  time, and a test now couples the changelog version to both README headings so a
  half-finished bump fails instead of shipping.

### New in v0.20.0

- **Three silent-failure bugs on core paths.** Memory recall returned an empty
  list once a vault passed ~1024 documents (sqlite-vec rejects a KNN with
  `k > 4096`, and the error fell outside the guarded block). Every temporal
  question resolved to the same wrong range at high confidence, because an empty
  regex alternation matches the empty string. And `activity-locales.json` was
  never deployed to a vault at all, so a clean install ran with an empty
  vocabulary. None of the three logged anything.
- **`safe-edit` can no longer strand the wiki write path.** It writes before the
  git step, so a failing commit used to leave the article overwritten and the
  tree dirty — after which every later call refused, while `/wiki` and
  `/reconcile` both forbid `--force`. The original bytes are now restored.
- **CI runs the whole suite.** `unittest discover` skipped 19 tests written as
  module-level functions, including the documentation guard that had never once
  executed — the reason stale doc claims survived. A new lint checks bilingual
  fact parity and code-derived claims, and found two real gaps immediately.
- **Lighter index maintenance.** Four write-only tables dropped (~23.7 MB and a
  full scan per event), source hashing made lazy, and the rollup cache removed
  after it was measured returning answers for the wrong query.

### New in v0.19.0

- **Distill huge sessions without drowning the context.** `/destilleer` can now
  reduce a large transcript to plain conversation text with the new
  `strip-transcript.py` (thinking, tool calls and subagent turns dropped,
  ~10-25x smaller) and fan the work out to subagents. The command docs also make
  the stub-versus-transcript distinction explicit and flag the overlap with
  `/sessielog`, and `/wiki` gains a `kb-lint --json` recipe to prove a new
  article's provenance is clean.

### New in v0.18.1

- **Deterministic prompt-hook runtime budget.** Interactive retrieval now has a
  separate 2-second hard ceiling, so a legacy or accidentally high
  `KB_RETRIEVE_TIMEOUT` cannot hold UserPromptSubmit until the client kills it.
  Longer waits require explicitly raising both the requested timeout and
  `KB_PROMPT_HOOK_MAX_EMBED_TIMEOUT`.

### New in v0.18.0

- **No cold-model timeout on the first prompt.** The `kb-retrieve` hook no longer
  times out on a cold embedding model: it embeds once per prompt, bounds the
  hot-path embed to an explicit timeout (2.0s), and self-heals by pre-warming the
  model at session start and firing a detached warm on a miss. Fully local and
  fail-open.
- **Upstream-drift warning.** A session-start notification warns when your git
  repository has fallen behind its upstream (current branch and/or `main`).
  cwd-aware and silent when clean; all clients get it from the one coordinator.

### New in v0.17.1

- **One coordinated start and exit hook per client.** Startup maintenance is
  phased and concurrent. Exit capture completes first, then independent usage
  attribution and Copilot import work run concurrently. Both paths are
  time-bounded, silent on routine success, and fail-open.
- **Native coordinated session workflows.** Copilot exposes `/sessiestart` and
  `/sessielog`; Codex exposes `$sessiestart` and `$sessielog` plus `/prompts:*`
  compatibility. The semantic `/sessielog` workflow invokes one deterministic
  helper for its post-save indexes, sweep launch, and notices.
- **Deterministic, non-destructive upgrade.** Setup recognizes old script
  basenames, removes only legacy KennisBank start/exit entries, deduplicates
  coordinators, and preserves unrelated hooks plus prompt/presearch behavior.

### New in v0.15
- **Multilingual temporal recall.** `/watdeedik`, `/timeline`, and `/weeklog`
  now understand dates and periods in **Dutch, English, German, French, Spanish,
  and Italian** out of the box (`vorige week`, `letzte Woche`,
  `la semaine dernière`, `la semana pasada`, `begin april`, `vor zwei Wochen`),
  with exact calendar ranges. An optional `dateparser` fallback extends coverage
  to 200+ languages, and an off-by-default local-LLM last resort handles
  compositional phrasing like "het weekend voor afgelopen maandag".
- **Richer relative phrasing.** Relative weekdays, week parts
  (`begin/midden/eind vorige week`), weekends, "N units ago" in both word orders,
  and month names with year inference are all resolved deterministically. 138
  pinned test cases guard the behaviour.

### New in v0.14
- **Local LiteParse document intake.** `/intake` and `/import documents <path>`
  parse PDFs, Office files, spreadsheets, presentations, and document-like
  images into citeable markdown under `<vault>/05-bronnen/liteparse/`.
- **Source material stays separate.** Parsed binary documents become `type: bron`
  markdown with frontmatter pointing back to the original local file, so wiki
  articles can cite them with explicit `[[05-bronnen/...]]` links instead of
  pretending they were session logs.
- **OCR is explicit.** Native-text documents parse without OCR by default; use
  `--ocr` only for scans and only when local Tesseract/tessdata is available.

### New in v0.13
- **Temporal Activity Recall.** Ask what happened on a date, during a week, or
  around a topic with `/watdeedik`, `/timeline`, and `/weeklog`. The feature
  builds a local `<vault>/.claude/kb-activity.db` from raw sessions,
  transcripts, memories, wiki updates, and usage telemetry.
- **Strict time-aware retrieval.** Dates and periods are parsed deterministically
  in Dutch and English (`vorige week`, `2026-07-03`, `3 juli 2026`,
  `between 2026-07-01 and 2026-07-07`). Range filtering is hard: events outside
  the requested period are not silently mixed in.
- **Topic timelines with evidence.** Follow subjects such as "Codex MCP" or
  "OpenRouter" through time using entities, tags, aliases, FTS and source refs.
  Local aliases can be configured in `<vault>/.claude/activity-topic-aliases.json`.
- **MCP temporal tools.** The local `kennisbank` MCP server now exposes
  `what_did_i_do`, `timeline`, `weeklog`, and `topic_timeline` alongside
  `recall` and `capture`, so Codex, OpenCode and other local agents use the same
  API as the slash commands.
- **Measured recall.** `kb-activity-eval.py` provides a temporal eval harness for
  date recall, period recall, topic timelines, negative controls and provenance
  coverage. The repo ships a non-personal example eval set.

### New in v0.12
- **One setup for install and upgrade.** `setup.sh` is now the authoritative
  path for first install, repair, and upgrade: it refreshes tooling, preserves
  user data, runs migrations, installs selected agent integrations, and blocks
  completion when validation fails.
- **Multi-agent by design.** Choose `claude`, `codex`, `opencode`, or `all`.
  Claude Code gets native commands and hooks; Codex gets shared skills,
  `/prompts:*` aliases, hooks, MCP, and `AGENTS.md`; OpenCode gets commands,
  shared skills, MCP, global rules, and a local plugin.
- **Verified local-first models.** Setup validates the selected backend before
  it returns. Ollama remains the default for local memory extraction and judging,
  including smoke tests for the configured embedding and chat models.
- **OpenRouter as explicit cloud opt-in.** If you want an external LLM for the
  judge/extraction step, setup can configure OpenRouter with a model slug and
  API-key environment variable. Secrets are never written to the repo or vault.
- **Agent-friendly operating contract.** `AGENTS.md`, `CONFIGURATION.md`, and
  the agent integration docs now spell out the active vault path, setup
  validation, Codex/OpenCode behavior, hooks, MCP, and privacy boundaries.
- **v0.12.1 Codex hotfix.** Re-running setup now repairs the Codex MCP TOML
  block without duplicating `[mcp_servers.kennisbank.env]`, and validation
  catches malformed Codex TOML before setup reports success.
- **v0.12.2 MCP runtime hotfix.** Setup now installs the Python MCP SDK for
  Codex/OpenCode targets and validates the stdio server with a real
  initialize/list-tools handshake, so a configured `kennisbank` MCP server no
  longer fails only when the agent starts.

### Knowledge (the wiki layer)
- `/wiki` compiles raw session logs into interlinked wiki articles, updating existing ones via a guarded rewrite engine (`safe-edit.py`) instead of clobbering them.
- **Provenance-lint** (`kb-lint.py`): every article must trace back to its sources with resolving wikilinks to a raw session or an imported source; `/wiki` writes that provenance per key point at distillation time. A hallucination during distillation can no longer become a permanent "fact" that nobody can check.
- `/stale` finds outdated articles, and usage telemetry keeps warm articles out of the list: an article you used last week is not stale, however old its `updated` date.
- Thinking tools: `/reconcile` surfaces contradictions between articles, `/uitdaag` adversarially challenges a claim, `/brug` finds conceptual bridges between two topics.

### Memory (the agent layer)
- An autonomous **capture sweep** runs detached in the background (launched at session start, over transcripts archived at session end): extract candidates, type them (`feit`, `voorkeur`, `procedure`, `beslissing`), deduplicate, and let an independent judge decide `current` versus quarantine (`unverified`) with an importance score (1-5).
- **Bi-temporal validity**: every memory carries `valid_from` (event time, from the session date) separate from `created` (capture time); superseding or expiring a fact stamps `valid_until`. The system knows not just what is true, but since when and until when.
- **Write-time invalidation** (Mem0 pattern, local): a new fact reconciles against the most similar existing memories at write time: ADD, SUPERSEDE (the old fact is closed and linked), or NOOP. A deterministic temporal guard ensures an older fact can never invalidate a newer one, so bulk re-imports are safe.
- Cross-memory maintenance: supersede pass, noise recheck, and cluster promotion (recurring themes get flagged as wiki candidates).

### Retrieval (the hooks layer)
- **Every prompt, every project**: a UserPromptSubmit hook embeds your prompt and injects the top-matching wiki articles and memories as context. A PreToolUse hook checks the vault before Claude searches the web.
- Hybrid index (`kb-index.db`): semantic vectors (sqlite-vec) fused with FTS5 keyword search, so exact terms are found even when embeddings miss them.
- Ranking: relevance x recency (half-life per memory type) x importance, plus a usage boost for documents that recently proved useful.
- **Graph-neighbour expansion**: the most-referenced wikilink neighbour of your hits rides along as one extra entry, turning loose hits into a coherent knowledge neighbourhood.

### Measurement (the trust layer)
- `kb-eval.py`: recall@1/3/5 and MRR against your personal eval set of questions. Run it before and after any retrieval change; a drop is a regression, not an opinion.
- `kb-activity-eval.py`: temporal recall evals for date questions, period questions, topic timelines, negative controls and source-ref coverage.
- `kb-calibrate.py`: checks all cosine thresholds (dedup, rewrite, reconcile, conflict, retrieve) against the active embedding model using a hand-labelled pair set, and proposes boundaries with separation margins. It writes nothing: you decide. Switch embedding models without silently degrading.
- `doctor.sh`: one command verifies the whole install, from vault layout and hook registration to provenance coverage.

### Sovereignty (the whole point)
- Local Ollama models for both embeddings and judgment, swappable via config (`kennisbank-embed.json`, `kennisbank-llm.json`); OpenAI-compatible endpoints supported when you choose to.
- LiteParse 2.x for local PDF/Office/image document parsing during intake.
- Everything is markdown + SQLite in a folder you own. Obsidian-compatible. MIT-licensed.
- Human update authority: agents never silently delete; superseded knowledge is closed and linked, quarantined knowledge cannot displace verified knowledge, and large rewrites require your confirmation.

## Prerequisites

- At least one local agent client: [Claude Code](https://claude.ai/code), Codex, OpenCode, or the [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
- Python 3.10+
- [Ollama](https://ollama.com) with:
  - `qwen3-embedding:4b` (embeddings; multilingual default. English-only vaults can use the lighter `nomic-embed-text`)
  - a chat model for the memory judge/extraction (default `qwen3.5:4b`; pin another via `<vault>/.claude/kennisbank-llm.json`, but keep it small enough to sit beside the embedding model)

Ollama is optional in the sense that everything fails open without it, but the memory sweep, semantic retrieval, and deduplication are the heart of the system: install it. For the **LLM judge/extraction only**, setup can also configure OpenRouter as an explicit cloud opt-in. Embeddings remain local by default.

The setup creates two root directories by default:
- `~/KennisBank/` - the vault (wiki, logs, memory, templates, scripts)
- `~/Claude/research/` - output directory for `/autoresearch`

Both paths are configurable. For a non-default vault, set `KENNISBANK_VAULT` when running setup; that same value is written into agent hooks and MCP config so clients do not fall back to `~/KennisBank`.

## Installation

```bash
git clone https://github.com/Jvdbreemen/LLmWiki-KennisBank.git
cd LLmWiki-KennisBank
bash setup.sh           # interactive
bash setup.sh --yes     # non-interactive (recommended for AI agents)
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents claude,codex,opencode
```

In one idempotent run, the setup script:
- creates the vault directory structure under `$KENNISBANK_VAULT` or `~/KennisBank/`
- copies scripts and templates into place
- bootstraps the settings toggles and runs version-gated migrations
- asks which agent environments to install (`claude`, `codex`, `opencode`, or `all`; default `claude,codex`)
- installs Claude Code commands/skills/hooks when `claude` is selected
- installs Codex command skills, `/prompts:*` compatibility aliases, MCP config,
  and global `AGENTS.md`; upgrades remove old KennisBank Codex hooks
- installs OpenCode commands, shared skills, MCP config, global `AGENTS.md`, and a local plugin hook when `opencode` is selected
- installs Copilot command skills, MCP config, personal instructions, and a
  custom agent profile; upgrades remove old KennisBank Copilot hooks
- asks for the LLM backend in interactive mode: default `ollama`, optional `openrouter` with model slug and API key env-var
- validates the install before returning: `doctor.sh`, agent config checks, MCP runtime handshake for Codex/OpenCode, local Ollama smoke tests, and OpenRouter smoke tests when OpenRouter is selected

**Re-running `setup.sh` is safe and is the upgrade mechanism**: it refreshes tooling and repairs agent config without clobbering user data, customizations, or vault contents. The `/kennisbank-upgrade` skill wraps it with release-tag checkout, drift detection, backups, version stamping, and the same post-install validation.

Useful flags:

```bash
bash setup.sh --yes --agents claude,codex      # default non-interactive target set
bash setup.sh --yes --agents all               # Claude Code + Codex + OpenCode + Copilot
bash setup.sh --yes --agents codex             # Codex only
bash setup.sh --yes --skip-model-check         # CI/offline validation without Ollama smoke tests
bash setup.sh --yes --skip-doctor              # skip the closing doctor gate (tests/CI that run doctor.sh themselves)
```

For OpenRouter, setup writes only non-secret config to
`<vault>/.claude/kennisbank-llm.json`: provider, model, endpoint, and
`api_key_env`. The API key itself must be in the named environment variable
or, if you enter it during setup, in the user-local secrets file
`~/.config/kennisbank/secrets.json`. It is never written to the repo or vault.

After install, read [POST-INSTALL.md](POST-INSTALL.md) for the first-session walkthrough.

### The hookset

Claude Code, Codex, and Copilot each receive one SessionStart coordinator and
one exit coordinator plus their prompt/tool hooks. The table names coordinator
children as jobs, not separately registered handlers. OpenCode receives MCP
plus a global plugin under `~/.config/opencode/plugins/`.

| Hook | Script | What it does |
|------|--------|--------------|
| SessionStart | `kb-session-start.py` | Coordinate concurrent index/sweep jobs, then notices; emit one actionable report |
| Coordinator job | `build-embed-index.py`, `build-kb-index.py`, `build-activity-index.py`, `sweep-launch.py` | Run independent maintenance concurrently |
| Coordinator notice | `memory-notify.py`, `distill-notify.py` | Report health/actions after maintenance |
| UserPromptSubmit | `kb-retrieve.py` | Inject matching wiki + memory context into the prompt |
| SessionEnd/Stop | `kb-session-end.py` | Capture the transcript/event first; then attribute usage and import Copilot activity concurrently |
| Exit coordinator capture | `archive-transcript.py` or `kb-copilot-capture.py` | Persist the client-native session source before follow-up work |
| Exit coordinator jobs | `kb-usage-scan.py`, Copilot `import-copilot.py` | Attribute useful recall and make Copilot activity immediately indexable |
| PreToolUse (WebSearch\|WebFetch) | `kb-presearch.py` | Consult the vault before searching the web |

The hooks are fail-open by design: an error means no injected context or a skipped background step, never a blocked session.

## Commands reference

| Command | Arguments | What it does |
|---------|-----------|--------------|
| `/sessielog` | none | Writes and curates the semantic session log, then runs one mechanical post-save coordinator |
| `/sessiestart` | none | Read vault context, memory, wiki status, suggest next actions |
| `/wiki` | optional topic | Compiles raw logs (last 7 days) into wiki articles with per-key-point provenance, validated by kb-lint |
| `/intake` | none | Processes files in `~/KennisBank/00-inbox/`, including local LiteParse conversion of PDF/Office/image documents to source markdown |
| `/stale` | none | Detects articles older than 60 days, skipping recently-used ones |
| `/import` | `cc` \| `claudeai <path>` \| `folder <path> [prefix]` \| `documents <path> [prefix]` \| `cowork` \| `all` | Bulk-import old sessions from Claude Code history, a claude.ai export bundle, any markdown folder, document sources via LiteParse, or Mac desktop Claude data; `all` runs every detected source, no argument asks interactively |
| `/destilleer` | none | Imports archived CC transcripts and compiles them into the wiki |
| `/autoresearch` | topic | Multi-round web research via the autoresearch skill (not a command file), saves to `~/Claude/research/` |
| `/reconcile` | optional topic | Surface contradictions across wiki articles and produce a reconciliation log |
| `/uitdaag` | claim or decision | Adversarially challenge a claim for weak reasoning or missing evidence |
| `/brug` | two topics | Find conceptual bridges and shared principles between two topics |
| `/weeklog` | optional period/topic | Weekly activity rollup with decisions, releases/tasks, open loops and source refs |
| `/timeline` | date/period/topic | Chronological temporal activity timeline with strict range filtering |
| `/watdeedik` | date/period/topic | Compact answer to "what did I do then?" with evidence links |
| `/kennisbank:settings` | none | Show and flip the background-automation toggles |
| `/kennisbank:review` | optional topic | Walk the unverified-memory queue; the human decides approve/reject/skip per item |
| `/kennisbank:rebuild-index` | none | Rebuild the hybrid search index from the vault markdown |
| `/kennisbank:rebuild-memory` | none | Re-extract ALL memory from archived transcripts (heavy; semantic dedup makes it near-idempotent) |
| `/kennisbank-upgrade` | optional `--dry-run` | Upgrade the deployed vault to the latest release tag |
| `/kennisbank-contribute` | optional `--dry-run` | PR local tooling edits back upstream |

## Skills

Three skills ship with the system. Claude Code gets them under `~/.claude/skills/`; Codex and OpenCode get them under the shared user skill location `~/.agents/skills/`, which both clients discover. Commands are single prompts; skills are multi-step procedures with their own guardrails.

| Skill | Invoked via | What it does |
|-------|-------------|--------------|
| `autoresearch` | `/autoresearch <topic>` or "research/deep dive/onderzoek [topic]" | Autonomous iterative research loop: multi-round web searches, synthesis, and one structured, cited document in `~/Claude/research/`. Checks your own vault first (lazy hierarchy) so research fills gaps instead of repeating what you already know. Built on Karpathy's autoresearch pattern. |
| `kennisbank-upgrade` | `/kennisbank-upgrade [--dry-run]` | Upgrades a deployed vault to the latest official release tag (never bare main): fetches tags, shows the changelog delta, detects local drift with a CRLF-agnostic diff, backs up drifted categories, deploys via `setup.sh`, stamps the installed version, and verifies with `doctor.sh`. |
| `kennisbank-contribute` | `/kennisbank-contribute [--dry-run]` | The reverse direction: isolates local tooling edits in a deployed vault (scripts, templates, commands, skills), filters out personal vault content, then branches, commits, pushes, and opens an upstream PR. Ownership equals durability: improvements survive the next upgrade because they land upstream. |

Upgrade and contribute are two halves of one loop: `contribute` sends your local improvements upstream, `upgrade` brings released improvements back down. A vault that follows both never drifts permanently from the project.

## Vault structure

```
~/KennisBank/
  00-inbox/        Drop files here for processing
  01-raw/
    sessies/       Session logs (raw-sessie-YYYY-MM-DD-topic.md)
    transcripts/   Archived Claude Code transcripts (SessionEnd hook)
  02-wiki/         Compiled wiki articles
  03-projecten/    Project-specific notes
  04-templates/    Article and log templates
  05-bronnen/      Source materials and references
  06-claude/       Claude-internal context files, eval + calibration sets
  07-media/        Media descriptions and asset metadata (not the binaries)
  08-archive/      Archived articles
  09-memory/       Agent memory (typed, judged, bi-temporal; archive/ for retired items)
  .claude/
    scripts/       Python + shell tooling (incl. doctor.sh)
    kb-index.db    Hybrid vector + FTS index (refreshed incrementally each session)
    kb-usage.db    Usage telemetry (survives rebuilds and model switches)
  graphify-out/    Knowledge graph output (optional)
```

## Background automation toggles

Eleven background behaviours are individual toggles in `kennisbank-settings.json`, managed with `/kennisbank:settings`:

| Toggle | Default | Controls |
|--------|---------|----------|
| `auto_archive` | off | Archive the transcript at session end |
| `distill_notify` | on | Notify at start that transcripts are pending |
| `embed_index` | on | Refresh the wiki embedding cache at start |
| `daily_graphify` | on | Update the knowledge graph once a day |
| `memory_capture` | on | Extract and judge memories into `09-memory/` |
| `memory_recall` | on | Inject memories into context via hooks |
| `usage_telemetry` | on | Track which injected knowledge gets used |
| `activity_llm_fallback` | off | Local-LLM fallback for exotic date phrasing in temporal recall |
| `checkpoints` | off | Auto-save a work-state stub at context compaction (PreCompact) |
| `orientation` | off | Inject a compact vault orientation at session start |
| `graph_retrieval` | on | Source the neighbor expansion from the weighted graph index (A/B-proven, TASK-87) |

## Measuring your retrieval

Two harnesses keep the system honest:

```bash
# recall@k against your personal eval set (06-claude/kb-eval-set.json)
python3 ~/KennisBank/.claude/scripts/kb-eval.py

# threshold calibration against the active embedding model
python3 ~/KennisBank/.claude/scripts/kb-calibrate.py
```

Maintain the eval set as your vault grows (questions you know the answer to, with the expected article), and run both harnesses after any change to thresholds, models, or ranking. Example sets ship in the repo root.

## Migrating from older Claude tooling

The `/import` command backfills the vault from existing Claude history. It handles Claude Code session JSONL files under `~/.claude/projects/`, claude.ai export bundles, Mac desktop Claude (Cowork) conversation data, and any generic markdown or text folder. Each importer writes raw session files that `/wiki` can compile afterwards. For the memory layer, `/kennisbank:rebuild-memory` re-extracts all archived transcripts through the full sweep (semantic dedup makes re-runs near-idempotent).

For binary/source documents, `/intake` and `/import documents <path>` use
LiteParse 2.x locally to turn PDFs, Office files, spreadsheets, presentations,
and document-like images into markdown under `05-bronnen/liteparse/`. This does
not call a cloud parser or an LLM. OCR is opt-in (`--ocr`) so native-text PDFs
do not get polluted by missing Tesseract/tessdata diagnostics; Office/image
formats may still require local LibreOffice/ImageMagick tooling as LiteParse
reports.

## Using KennisBank from other agents (Codex, OpenCode, Copilot, ChatGPT)

The vault is not Claude-Code-only. `scripts/kb-mcp.py` is a local **MCP server** exposing nine primitives: eight tools - `recall` (search memory + wiki), `capture` (save a new memory), `review_pending` and `review_decide` (the human review queue), and the temporal set `what_did_i_do`, `timeline`, `weeklog`, `topic_timeline` - plus an `instructions` resource (a nudge to pull before searching externally). MCP is the one protocol every modern agent already speaks, so any client running **on this machine** can use the vault.

Every tool carries MCP annotations, which is not cosmetic: a client derives from `readOnlyHint` whether a call needs confirmation and whether it may run in parallel, and defaults both to "no" when the hint is absent. The six read-only retrieval tools are marked as such; `capture` is a non-destructive writer, `review_decide` a destructive one. The pull nudge travels on three carriers, because none of them reaches every client on its own: the `instructions` field of the protocol handshake, the `kennisbank://instructions` resource, and the managed block in `.github/copilot-instructions.md`.

**The hard boundary: local only.** The MCP server binds nothing to the network
(stdio transport); the vault never leaves your machine. Claude Code, Codex,
GitHub Copilot CLI, OpenCode, and compatible local stdio clients can reach it
directly. Agents that run *in the cloud* (hosted ChatGPT) cannot reach a local
stdio server, and the answer is **not** to tunnel your sovereign vault to the
internet - it is the manual bridge below.

### Codex CLI

`setup.sh --agents codex` installs:

- `~/.agents/skills/<command>/SKILL.md`, including `sessiestart`, `sessielog`,
  temporal commands, and the hand-authored KennisBank skills
- `~/.codex/prompts/*.md` aliases, invoked as `/prompts:sessielog`, `/prompts:sessiestart`, `/prompts:kennisbank-upgrade`, etc.
- `~/.codex/AGENTS.md` with the active vault path
- `~/.codex/hooks.json` with one SessionStart and one exit coordinator plus
  fail-open prompt/tool hooks
- `~/.codex/config.toml` MCP server `kennisbank`

Use `$sessiestart` and `$sessielog` as native Codex skills. Codex does not
expose arbitrary bare slash aliases; the deprecated prompt compatibility form
is `/prompts:<name>`. KennisBank installs one start and one exit coordinator.
Codex may show one client-owned row per lifecycle event, but routine output
stays silent. Setup replaces legacy start/exit entries while
preserving unrelated and non-startup hooks. MCP tools remain available through
the configured `kennisbank` server, and setup proves the server starts before
reporting success.

Manual MCP equivalent:

```bash
py -3 -m pip install mcp==1.28.1
```


```toml
[mcp_servers.kennisbank]
command = "py"
args = ["-3", "/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]

[mcp_servers.kennisbank.env]
KENNISBANK_VAULT = "/absolute/path/to/vault"
KB_LLM_PROVIDERS = "ollama"
KB_LLM_MODEL = "qwen3.5:4b"
KB_LLM_ENDPOINT = "http://localhost:11434"
```

### OpenCode

`setup.sh --agents opencode` installs:

- `~/.config/opencode/commands/*.md`, invoked as `/sessielog`, `/sessiestart`, `/kennisbank-upgrade`, etc.
- `~/.agents/skills/{autoresearch,kennisbank-upgrade,kennisbank-contribute}/`
- `~/.config/opencode/AGENTS.md` with the active vault path
- `~/.config/opencode/opencode.json` MCP server `kennisbank`
- `~/.config/opencode/plugins/kennisbank.js`, a fail-open local plugin for session maintenance events

OpenCode reads global commands directly from `~/.config/opencode/commands/`, so the command names match the Claude Code names. Retrieval should use the MCP `recall` tool and the installed skills; the plugin handles background maintenance where OpenCode exposes matching events.

### GitHub Copilot CLI - a first-class local agent

The **standalone** GitHub Copilot CLI (`npm install -g @github/copilot`, invoked as `copilot`) is a managed KennisBank target, exactly like Codex and OpenCode - not a hand-written snippet. One local vault, one stdio MCP server, one local recall layer, now shared across all four agents. Whatever you do in a Copilot session becomes searchable KennisBank history next to your Claude Code, Codex, and OpenCode work; ask `/watdeedik` or `/timeline` and Copilot's sessions show up alongside the rest.

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents copilot
```

`setup.sh --agents copilot` installs, idempotently and login-free:

- `~/.copilot/mcp-config.json` - MCP server `kennisbank` (`recall`, `capture`, and the temporal tools), registered by a key-scoped JSON merge and validated with a real initialize/list-tools handshake
- `~/.copilot/hooks/kennisbank.json` - one cross-platform SessionStart
  coordinator plus fail-open activity capture hooks
- `~/.copilot/copilot-instructions.md` - a KennisBank managed instruction block
- `~/.copilot/agents/kennisbank.agent.md` - a custom agent profile, selected with `copilot --agent kennisbank`
- native slash-command skills at `~/.agents/skills/`, including
  `/sessiestart`, `/sessielog`, `/weeklog`, and `/timeline` (list with
  `copilot skill list`)

KennisBank coordinates startup behind one hook because Copilot has no hook
field that hides its own timeline rows. One generic row can remain; six to
eight old rows become one. On upgrade, setup removes only known legacy
SessionStart commands and leaves unrelated entries untouched.

Run Copilot through the wrapper to pin the vault and local-LLM env: `python3 <vault>/.claude/scripts/kennisbank-copilot.py` (a trivial exec that hands off to the real `copilot`; `--kb-doctor`, `--kb-dry-run`, and `--kb-print-env` work without a GitHub login).

**The cloud boundary is precise.** Copilot is cloud-backed - a live model turn
needs a GitHub Copilot subscription and sends requests to GitHub. Your vault,
recall, MCP server, skills, and instructions stay local; their installation and
`copilot mcp list` work without login. The integration is opt-in. See
[agent integrations](docs/agent-integrations.md), the original
[Copilot ADR](docs/adr/0003-copilot-cli-integration.md), and the
[SessionStart coordinator ADR](docs/adr/ADR-006-coordinate-sessionstart-work-behind-one-client-hook.md)
and [session logging/exit coordinator ADR](docs/adr/ADR-007-coordinate-session-logging-and-exit-work-behind-one-client-hook.md).

### GitHub Copilot (VS Code agent mode) - works, with one caveat

This is Copilot's **VS Code agent mode** (MCP tools inside the editor) - a different, manual integration from the standalone GitHub Copilot CLI covered above. Copilot's agent mode supports MCP **tools** over stdio, but **not** MCP resources or prompts. So `recall` and `capture` work, but the `instructions` nudge (a resource) will not surface. Put the nudge in `.github/copilot-instructions.md` instead:

```markdown
You have a local KennisBank via MCP tools `recall` and `capture`.
Call `recall` before searching externally; call `capture` to save a reusable fact.
```

Register the server in VS Code settings (`mcp.json` / `"servers"`):

```json
{
  "servers": {
    "kennisbank": {
      "command": "python3",
      "args": ["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]
    }
  }
}
```

The wider adapter registry and the rest of the client snippets live in
[docs/agent-integrations.md](docs/agent-integrations.md).

### ChatGPT - the manual bridge (sovereignty first)

Hosted ChatGPT can only connect to **remote** MCP servers on the public internet; exposing a local server means tunnelling (Secure Tunnel / ngrok / Cloudflare), which routes your queries **and** the returned knowledge through OpenAI's infrastructure. That breaks the whole point of a sovereign vault, so KennisBank does not do it by default. Instead, **you** stay the gate:

```bash
python3 .claude/scripts/kb-ask.py "how did I fix the ESP32 BLE crash"
python3 .claude/scripts/kb-ask.py "my topic" --k 8 --clip   # also copy to clipboard
```

`kb-ask` retrieves locally and prints a ready-to-paste context block (a short instruction for the model, then the hits, then your question). Paste it at the top of your ChatGPT message. Nothing leaves the machine automatically - you choose what to share.

### ChatGPT data export - get control of your own chats back

You can pull your ChatGPT history *into* the sovereign vault, so lessons from those conversations become your own retrievable knowledge instead of living only in OpenAI's cloud:

1. In ChatGPT, open **Settings → Data controls → Export data** and confirm. (Requires being signed in on the web app.)
2. OpenAI emails you a download link within minutes to a day; the link is time-limited. Download the ZIP - it contains `conversations.json` (plus `chat.html`, media).
3. Import it into the vault:
   ```bash
   python3 .claude/scripts/import-chatgpt-export.py --input ~/Downloads/chatgpt-export.zip
   # preview first if you like:
   python3 .claude/scripts/import-chatgpt-export.py --input ~/Downloads/chatgpt-export.zip --dry-run --verbose
   ```
   Each conversation becomes a raw session log under `01-raw/sessies/`. Then run `/wiki` to compile them into articles and `/kennisbank:rebuild-memory` to extract the memory layer. Re-imports are skip-by-default (idempotent); pass `--force` to overwrite.

The importer walks ChatGPT's message *tree* (`mapping`), orders turns by timestamp, and keeps only your and the assistant's turns - system and tool nodes are dropped. It runs fully locally; nothing is sent anywhere.

## Documentation

| File | For |
|------|-----|
| [docs/guiding-principles-and-values.md](docs/guiding-principles-and-values.md) | The guiding principles and values, worked out as one document |
| [PRINCIPLES.md](PRINCIPLES.md) | The design laws that govern every decision (concise reference) |
| [VALUES.md](VALUES.md) | What the project cares about - its character (concise reference) |
| [AGENTS.md](AGENTS.md) | AI coding agents (Claude Code, Codex, GitHub Copilot CLI, and OpenCode) installing this on a user's behalf |
| [POST-INSTALL.md](POST-INSTALL.md) | First-session walkthrough after `setup.sh` finishes |
| [CONFIGURATION.md](CONFIGURATION.md) | Every configurable knob: paths, thresholds, models, toggles |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom / cause / fix for common problems |
| [OBSIDIAN.md](OBSIDIAN.md) | Open the vault in Obsidian, recommended free plugins |
| [CHANGELOG.md](CHANGELOG.md) | Release history, Keep a Changelog format |
| [vault-structure/README.md](vault-structure/README.md) | Directory-by-directory reference |

## Customization

1. Edit `<vault>/CLAUDE.md` after setup. Replace `[YOUR NAME]` and `[YOUR PROJECTS]` with your own. For a non-default install, `<vault>` is the exact `KENNISBANK_VAULT` path you used.
2. **Vault path.** All Python scripts, `doctor.sh`, and generated agent integrations honor the `KENNISBANK_VAULT` environment variable (default `~/KennisBank`). See [CONFIGURATION.md](CONFIGURATION.md) section 9 for the non-default vault contract.
3. **Embedding backend.** Swappable via `<vault>/.claude/kennisbank-embed.json` or `KB_EMBED_*` env vars: local Ollama by default, OpenAI-compatible endpoints when configured. Switching models invalidates the cache by design; run `kb-calibrate.py` afterwards to check the thresholds against the new model (it proposes values, you set them).
4. **LLM backend** (judge/extraction): `<vault>/.claude/kennisbank-llm.json` or `KB_LLM_*` env vars. Default Ollama `qwen3.5:4b` (sized to coexist with the embedding model on one GPU); optional OpenRouter uses `https://openrouter.ai/api/v1/chat/completions` through the OpenAI-compatible chat schema.
5. **Wiki categories.** `build-karpathy-index.py` groups articles using a built-in taxonomy; override with a `categories.json` (copy [`categories.example.json`](categories.example.json)).
6. The commands are in Dutch by default (they follow prompt language). Change section headings if you prefer English.
7. Stale threshold (default 60 days): pass `--days N` or edit `stale-check.py`.
8. `auto-crosslink.py` tunables: `MIN_CONFIDENCE` (default `0.75`) and `MAX_NEW_LINKS` (default `5`).
9. Research output path: changing it touches several places (`setup.sh`, the autoresearch skill, and the command prose) - see [CONFIGURATION.md](CONFIGURATION.md) section 5.
10. To enable the `/autoresearch` trigger, add this snippet to your global `~/.claude/CLAUDE.md`:
    ```
    # autoresearch
    - **autoresearch** (`~/.claude/skills/autoresearch/SKILL.md`) - multi-round research with lazy hierarchy check. Output to `~/Claude/research/`. Trigger: `/autoresearch`
    When the user types `/autoresearch`, invoke the Skill tool with `skill: "autoresearch"` before doing anything else.
    ```

## Optional: graphify integration

`auto-crosslink.py` reads from `<vault>/graphify-out/graph.json`, produced by the graphify skill when run on the vault. Without it, the crosslink step is silently skipped. Retrieval benefits indirectly: the graph-neighbour expansion follows the wikilinks that crosslinking maintains.

## Optional: knowledge graph dashboard

[Understand-Anything](https://github.com/Lum1104/Understand-Anything) is a separate Claude Code plugin (MIT) that turns a Karpathy-pattern wiki into an interactive knowledge graph dashboard. Build the required index with `python3 scripts/build-karpathy-index.py`, then run `/understand-knowledge` inside `<vault>/02-wiki`. See `--help` for flags; categories are customizable via `categories.json`.

## Credits

- Pattern: [Andrej Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- Vault/CMS inspiration: [claude-obsidian by AgriciDaniel](https://github.com/AgriciDaniel/claude-obsidian)
- Memory-architecture lessons: the public work around Mem0, Zep/Graphiti, Letta, and Cognee, rebuilt here local-first

## License

MIT. See [LICENSE](LICENSE).

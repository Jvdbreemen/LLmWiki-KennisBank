# Changelog

All notable changes to LLmWiki-KennisBank are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.34.0] - 2026-08-17

The autonomous review learns what it already asked. v0.33.0 let quarantined
memories review themselves, but nothing remembered the answers, so a verdict
that never changes became a permanent claim on the budget — and the message
that reported it named two causes that were fine and omitted the one action
that helps.

### Upgrading

- No migration. Trap 1 has no record yet, so the first sweep after upgrading
  judges the oldest memories once more and writes their outcomes; from the
  run after that the budget goes to memories nothing has read yet. Measured
  on a real vault: run 1 covered the 40 known-undecided memories, run 2
  covered 40 freshly captured ones with zero overlap.
- New state file `.claude/memory-verify-attempts.json` holds trap 1's own
  outcomes, keyed by vault-relative path. Deleting it is safe and costs one
  round of verdicts.
- The session-start memory message changed. It now reports two counts instead
  of one and points at `memory-doctor.py pending` / `decide` for the half a
  person has to decide. Anything parsing the old sentence needs updating.
- `VERIFY_PROMPT_VERSION` is now load-bearing: bumping it reopens every
  recorded outcome at once, which is intended (a new prompt is the one reason
  to expect a different answer) and bounded by `VERIFY_PASS_CAP`.

### Added

- `kb-verify.py --retry-settled` re-judges memories still inside their
  cooldown, for a deliberate full drain of the backlog.
- `KB_VERIFY_RETRY_DAYS` (default 7) and `KB_VERIFY_RETRY_HOURS` (default 6):
  how long a real verdict and an inconclusive outcome stand before a memory
  is offered to trap 1 again.
- `_groundcheck.candidates()` — one candidate-selection rule shared by the
  sweep and the CLI, which carried a copied block until now — and
  `is_settled()`, the single predicate for "trap 1 will leave this alone",
  shared by the pass and the report so the two cannot disagree.
- Heartbeat keys `rot_waiting` and `rot_undecided` next to the existing
  `rot`, and `memory-doctor.rot_breakdown()` behind them.

### Changed

- The session-start message splits the rot count: memories still waiting for
  a verdict point at the sweep and the model; memories that were judged and
  came back undecidable point at `memory-doctor.py pending` and
  `decide <stem> approve|reject|skip`, the only path where a person moves an
  unverified memory. The old sentence named `/kennisbank:settings` and Ollama
  for a state neither had anything to do with.
- Trap 1 records outcomes and picks candidates in two tiers: never judged at
  this prompt version first (oldest capture first), then anything past its
  window (oldest attempt first, so retries rotate). It orders, it never
  excludes — trap 1 reads a selected passage where the client reads the whole
  transcript, so it still promotes memories the client graded `partial`, and
  those promotions are what drains the queue.
- Outcomes are collected during a pass and written once instead of once per
  verdict, so a full drain no longer rewrites a growing file per memory.

### Fixed

- **Settled verdicts starved the grounded check.** Trap 1 sorted unverified
  memories oldest-first with no record of what it had already judged, and a
  verdict is a property of claim-against-passage rather than a coin flip, so
  `partial` came back `partial` every run. On the vault that surfaced this,
  all 24 memories past the rot cutoff had been graded `partial` by a whole-
  transcript client read; together with 16 younger ones they held 40 of 40
  slots of `VERIFY_PASS_CAP`, so 49 newer memories were never judged at all
  and the same 40 were re-judged every sweep at 6-8 s of local model each.
- An inconclusive outcome is recorded too, under a short window.
  `no_transcript` is deterministic rather than transient — an empty or
  truncated source yields an empty passage on every run — so leaving it
  unrecorded parked those memories at the head of the queue permanently, the
  same starvation from the other side.
- A refused promotion no longer buys a cooldown. `_memory.promote` returns
  false on a locked or read-only file, which is ordinary on Windows with a
  sync client holding it; the verdict was recorded anyway, parking a memory
  trap 1 wanted to promote with nothing in the promote log to show for it.
- Verify outcomes are keyed on the vault-relative path rather than the bare
  stem. The memory scan is recursive and `09-memory/archive/` exists, so two
  files could share a key and one could inherit the other's cooldown.
- An unreadable attempts file is moved aside to `.corrupt` instead of being
  silently replaced by a single record.
- `rot_breakdown` and `candidates()` now answer the same question. The report
  called every recorded memory final while the pass requeued the ones on an
  older prompt version or past their window, so the message claimed "decide
  by hand" about work the next sweep was about to redo.

## [0.33.0] - 2026-08-17

The human leaves the memory loop. Quarantined memories now promote, escalate
and retract autonomously — safety comes from evidence and reversibility, not
from a person approving things — and `/kennisbank:review` becomes an audit
view with per-line undo. Around that: a wave of verified fixes for defects
that failed silently, and the open backlog worked down to zero with every
task carrying its evidence.

### Upgrading

- The sweep gains a grounded-verification pass: unverified memories whose own
  source transcript supports them are promoted to `current` automatically
  (local model only, evidence quote in the promote log). Drain an existing
  backlog once with `kb-verify.py`.
- Traps 2/3 (whole-transcript adjudication by the client LLM) ship **OFF**:
  they sit behind the new `auto_review_llm` toggle, because bundles exist to
  be read by a client LLM and that is cloud. "Lokaal, altijd" holds unless
  you flip it deliberately.
- The FTS index heals itself on the first session start after this upgrade:
  rows truncated under the old body cap (72 of 206 wiki articles) are
  repaired from the embedding cache, no manual `--rebuild` needed.
- `setup.sh` now pulls the resolved embedding model when it is missing
  (skipped with `--skip-model-check`); `doctor.sh` warns when the index was
  built with a different embed backend than the code resolves, with the
  remedy.
- New config key `memory_threshold` in `kennisbank-embed.json` (default
  0.45): the memory-layer floor is now tunable per vault, resolved per call.

### Added

- **Autonomous memory review** (TASK-195, design in
  `docs/superpowers/specs/2026-08-16-autonomous-memory-review-design.md`).
  Three traps, each gated by pre-registered measurements (G0–G3): grounded
  promotion by the local model against the memory's own source chunk
  (`supported` never fabricated in 210 checks); client-LLM whole-transcript
  adjudication for what trap 1 cannot support (`kb-autoreview.py` bundle/
  apply — an agent proposes, code disposes); retraction only on double
  agreement plus a failed refutation, capped per run, reversible with one
  `reopen()`. First real run on this vault: 993 quarantined memories judged,
  949 promoted with evidence across both traps, 2 retracted, 42 left for a
  later cycle. Recall on the 1224-question set improved (+0.035 recall@1,
  +0.026 MRR) with freshness slices stable.
- **`/kennisbank:review` is an audit view now**, not a work queue: it renders
  the promote log (route, prompt version, evidence quote) and the closed log,
  with one undo per direction — `memory-doctor.py demote <stem>` (promotion
  was premature, back to quarantine; exactly one legal edge, mirroring
  `promote()`) and `reopen <stem>`. No step in the pipeline waits for a
  human.
- **The sweep's primary budget is wall-clock time** (`KB_SWEEP_TIME_BUDGET`,
  default 900s sized on a measured ~430s/transcript run). The old chunk
  budget assumed 5-6s per chunk but only counted the extract call; per chunk
  the sweep also pays dedup embeds, reconcile and judge, so 150 chunks
  bounded nearly two hours of GPU. Budget stops name their brake and report
  how many transcripts stay pending.
- **`context-budget.py` now enforces a budget.** The script was named for one it
  never had: L0-L3 nest content but bounded nothing, so an L3 answer over three
  long articles was an order of magnitude larger than one over a short article,
  with no signal to the caller. `--max-tokens` (or `KB_CONTEXT_MAX_TOKENS`) caps
  the assembled result. Entries are dropped in a fixed order — `bodies`, then
  `relevant`, then `active` — lowest-ranked first, so the weakest match goes
  before the best one; `identity` is never trimmed. Requesting a ceiling always
  emits a `_budget` block reporting the ceiling, the estimate, whether it fitted
  and what was dropped, because silence would read as "everything was included".
  Sizing is ~4 characters per token, deliberately dependency-free so a cheap path
  stays cheap — leave headroom against an exact count. Without a ceiling the
  output is byte-identical to before. (TASK-193)

### Documentation

- **Agent-memory field review and strategy**
  (`docs/research/agent-memory-field-review-and-strategy.md`): KennisBank read
  against the Tsinghua Awesome-Memory-for-Agents taxonomy (~300 papers), an
  eight-framework production comparison, and the full August research series
  through the v0.31.1 rerank and factor measurements. Finding: the retrieval
  loop now measures and corrects itself faster than external review can track —
  everything retrieval-side this review recommended was independently done, in
  flight, or measured obsolete on the same days it was written, which the
  document records rather than smooths over. The one gap that survived all
  three derivations: the system cannot tell whether remembering *helped*.
  Three August documents hit that wall independently ("none says what the user
  needs"), and the outcome loop (TASK-173) is the queued answer. Also queued:
  dead-end capture audit (TASK-172), automated distillation proposals
  (TASK-174), procedure-to-skill promotion (TASK-175). Two earlier
  recommendations were deleted as superseded by `rank-factors-2026-08-14` and
  TASK-162's design.

- **Honcho architecture review** (`docs/research/honcho-memory-architecture.md`):
  plastic-labs/honcho compared against KennisBank — four points of independent
  convergence, the one idea adopted above, two queued (observer provenance,
  TASK-194; a stated-versus-inferred axis gated behind a measurement, TASK-171),
  and the infrastructure rejected with reasons. Records the AGPL-3.0 versus MIT
  boundary: ideas and API shapes transfer, code does not.

- **The open backlog went to zero.** All 40 open tasks were triaged against
  the repository by parallel verification agents: delivered work closed with
  its commits cited, superseded and parked work archived with a close-out
  note saying where the direction lives and what reopening takes, verified
  defects fixed (below). Two bug claims were narrowed and two extra defect
  sites found during verification.

### Fixed

Every fix below was adversarially re-verified against the source before
implementation; most failed *silently*, which is why they lived so long.

- **A repo checkout next to a `~/.claude` directory resolved the vault to
  `$HOME`** and exported that root to every child process. `_script_vault()`
  now matches the installed layout (grandparent *named* `.claude`); the bare
  `parents[2]` header is deleted from 47 scripts and vault resolution flows
  through `vault_root()` only, guarded by tests. Also the real cause of three
  chronic CI test failures. (TASK-181/167)
- **One malformed env var turned retrieval off for every session**: six
  module-level `int(os.environ...)` sites raised at import and the fail-open
  hook swallowed it. One fail-soft reader (`_common.env_int/env_float`) with
  a full-text guard against the class. (TASK-185)
- **The sweep's partial-deploy fallback wrote zero memories**: its lambda
  drifted out of sync with `reconcile()`'s signature and raised TypeError on
  every candidate. Star-args now; it cannot drift again. (TASK-180)
- **The embed default-model flip (v0.28.0, 8b→4b) had no migration story**:
  doctor.sh checked a stale `:8b` literal and reported the OLD model as
  installed on exactly the vaults whose recall had gone dark. Single-source
  constant, `--print-model` for shell callers, an index-vs-code mismatch
  warning with the remedy, and a pull in setup. Config-pinned vaults are
  untouched. (TASK-182)
- **The embeddings cache path froze at import** (2s → 835s test runs on
  import order; the deeper cause behind several lazy-import workarounds):
  `cache_file()` resolves per call. (TASK-196)
- **A second session could steal the maintenance lock mid-handoff** and run
  two index builders at once (reproduced deterministically). Dead-pid grace
  window, every lock mutation under an OS-level mutex with a re-judge inside
  it, and one `pid_alive` (the `_embeddings` copy read access-denied as
  dead and spawned duplicate warm children). (TASK-183)
- **The FTS body-cap fix never reached already-indexed rows** — 16.6% of
  wiki text stayed unsearchable while the changelog said fixed. The index
  stamps its cap and heals mismatched rows on the next incremental build;
  embed failures are reported by document name. (TASK-186)
- **An edited memory was judged with the embedding of its previous
  content**: index vectors were served by path without a hash check, feeding
  the very passes that close memories. Vectors now carry the stored file
  hash and mismatches fall back to re-embedding. (TASK-191)
- **kb-eval could measure a different retrieval system than the live hook
  runs**: eval embedded queries with the query prefix, production embedded
  bare. One seam (`embed_query`) for both, a static guard on every
  query-bearing file, and a behavioral test that drives the real hook.
  (TASK-184)
- **The documented `scene_retrieval` toggle was read by zero production
  paths** — flipping it was a silent no-op. Wired (default OFF, so nothing
  changes without opt-in); the memory floor resolves per call; a failed
  settings *load* no longer silently disables the default-ON graph
  neighbour. New guard: every retrieval toggle must have a production
  reader. (TASK-188)
- **Two wide-span JSON parses survived the `_llmjson` migration**: scene
  clustering silently degraded to baseline recall on a commentary brace, and
  the judge-model sweep scored candidates against a stricter parser than
  production runs (old sweep reports are not comparable to new ones). Both
  routed through `_llmjson`, with a repo-wide guard. (TASK-189)
- **The Atlas overview cache served one date's payload for another** within
  its TTL; keyed on (vault, date) now. (TASK-187)

### Changed

- One corpus snapshot and one neighbour computation per sweep instead of
  three full reloads and two KNN probes (the brute fallback was twice
  15m26s); passes prune what they closed, equivalence pinned by tests. The
  embed config is memoized on (path, mtime, size), removing ~5000 redundant
  reads per index build. Duplicated helpers folded into single owners
  (JSONL log writers, QueryCache, the kb-mcp activity dispatcher, the
  config-key boundary, the canonical recall-rank helper). (TASK-190/191)
- `kb-lint.py` and the CI workflow are fully English per repo policy, with
  a ratchet guard over `.github/` plus every translated script. Backlog
  task files are historical records and stay as written. (TASK-192)

## [0.32.0] - 2026-08-16

The memory layer stops treating "newer statement about the same subject" as
"complete replacement". Hand-labelling every supersession this vault ever made
showed that assumption was wrong more than twice as often as it was right, in
the direction that loses knowledge.

### Upgrading

Nothing is required. The 64 wrongly closed memories were healed as a data
operation and are already live in the vault; this release ships the prompts
that stop the loss from recurring. Until it is deployed, sweeps keep closing
memories under the old rule.

### Changed

- **Closing a memory now requires covering it.** Both closing judges — the
  write-time reconcile and the maintenance supersede pass — no longer close on
  "a different value" alone. Closing requires that the successor carries
  everything of lasting value; partial coverage keeps both memories open. Both
  prompts move to version 3, stamped into the closed-log, so every closure
  stays traceable to the prompt that caused it.

  Grounds: all 237 historic supersessions were hand-labelled with adversarial
  verification (TASK-161). 61% were duplicate cleanups, only 11% genuinely
  replaced substance, and **27% NARROWED** — the successor dropped facts whose
  only carrier was the memory it closed, and the `status=current` recall filter
  made those facts unreachable rather than lower-ranked. Replayed on all 209
  adjudicated pairs, the v3 prompts cut knowledge-losing closures from 57.8% to
  37.5% while the duplicate defence (which rests on the non-LLM dedup paths) is
  unchanged. An improvement, not a solution, and the research says so.

### Fixed

- **64 wrongly closed memories are reachable again.** Every closure the
  labelling adjudicated as NARROWED was reopened via the TASK-150 machinery —
  reopened, not merged forward, because merge-forward would use the operation
  class being repaired as the repair. The pre-registered gate opened: questions
  answerable only by those memories went from recall@5 0.000 to 0.333
  (production) / 0.600 (cosine re-sort). The full 1224-question memory eval is
  unchanged (+0.000/+0.002/+0.001): healing added answers without disturbing
  existing ones.

### Research

- `docs/research/freshness-eval-2026-08-16.md` — the eval set that can see what
  recency is for: 89 questions from labelled pairs, dev/holdout split, holdout
  deliberately never run. On recency's home ground (newest-wins) the recency
  weighting does not beat raw cosine; and with old answers finally back in the
  pool (oldest-wins) it actively buries them — the third independent
  measurement pointing the same way as TASK-138 and TASK-160.
- `docs/research/narrowed-supersede-2026-08-16.md` — the coverage fix and its
  three validation arms.

## [0.31.1] - 2026-08-15

A patch that ships a fix which had already been written, reviewed and approved —
and then lost. PR #114 landed as `e314f70`; the follow-up commit that processed
its Copilot review stayed behind on the branch and sat there for two days. The
repository's rule is to read the review before merging. This is the step after
that one: having acted on it, make sure the acting lands.

### Fixed

- **The C4 reference documented the bug the skill it documents warns about.**
  `C4-Documentation/c4-code-skills.md` described step 10 of the upgrade skill as
  `git rev-parse --short $LATEST`, with no `^{}`. Every tag in this repository is
  annotated, so that command returns the SHA of the tag *object* rather than the
  commit — which is precisely how v0.28.0 came to be stamped `80b0285` instead of
  `86eb290`, and v0.29.0 `1506a9c` instead of `1cb608d`. Anyone following the
  reference instead of the skill would have reproduced it a third time.

### Changed

- `skills/kennisbank-upgrade/SKILL.md` reads more clearly at the same step, and
  its explanation of how step 8 and step 10 differ is corrected. **Not a
  behaviour fix**: the previous form
  `"<git rev-parse --short "$LATEST^{}">"` and the new
  `"<git rev-parse --short $LATEST^{}>"` were tested and behave identically,
  because a command substitution opens its own quoting context. Recorded as
  cosmetic rather than folded into the fix above, which is where it would have
  looked like a second defect.

### Not in this release

`perf/default-embed-qwen3-4b` was examined and deliberately left out. Its content
is already on main by another route — the default is `qwen3-embedding:4b` and
`docs/research/embedding-model-sweep-2026-08.md` is present — and the branch is
behind main elsewhere. Stale, not unreleased.

## [0.31.0] - 2026-08-15

A release about measurement. Three things this repository believed turned out to
be wrong when checked, and the most useful change is one line.

### Upgrading

**Rebuild the index once, or you get none of the retrieval gain.** The stored
text changed but the file hashes did not, so the incremental build sees nothing
to do:

    python3 "$VAULT/.claude/scripts/build-kb-index.py" --rebuild

Roughly ten minutes for ~1900 documents, entirely from the embedding cache — the
vectors are unchanged, only the searchable text is rewritten. Nothing else is
required; `source_chunk` is a new frontmatter field on newly captured memories
and its absence is normal.

### Fixed

- **Two thirds of long wiki articles were unsearchable, and half of that was for
  no reason.** `build-kb-index` stored only the first 4000 characters of a
  document in the full-text index — the same truncation the *embedding* model
  requires, because it runs at `num_ctx=2048` to keep VRAM free. FTS5 has no
  such limit and was paying it anyway. 72 of 206 articles run past 4000
  characters, and 16.6% of all wiki text was reachable by neither half of the
  hybrid search.

  Measured against a rule fixed before the run: questions about material past
  the cap go from **recall@5 0.450 to 0.725**, and the existing 329-question set
  is unchanged at 1.000. The vector arm is still blind past the cap; this lets
  the lexical arm route around it.

- **A model answer that was not quite JSON is no longer thrown away.** Four
  verifier replies in 56 were counted unparseable; all four contained a
  well-formed object with broken string delimiters (`\"…\"` or `'…'`).
  `_llmjson` repairs both shapes, but only after an honest parse has failed and
  only if the repair then parses — a repair that yields nothing valid is
  discarded, so a broken answer stays broken instead of becoming a plausible
  wrong one.

### Added

- **Memories record where they came from.** A swept memory now carries
  `source_chunk: "N/M"` — chunk N of M in its source transcript. The sweep knew
  this and discarded it, so checking a memory against its own source meant
  retrieving the passage again. M is the whole transcript's chunk count, never
  the capped slice a run happened to read, so a reader can re-chunk and detect a
  stale stamp rather than trust a wrong one.

### Decided against

- **The trust factor will not be built on grounded verification.** Two of the
  five ranking factors were measured to do literally nothing (TASK-160), and the
  proposed replacement — asking a local model whether a memory is supported by
  its source — was validated in depth and rejected on its own numbers. It
  answers `supported` for 88.7% of memories, which is the same near-uniformity
  that made `trust_factor` inert in the first place; and of the 20 `unsupported`
  verdicts adjudicated against whole transcripts, **zero** were correct. Uniform
  where it is reliable, unreliable where it varies.

  What survives: `supported` may raise trust, nothing may lower it — which is
  where the vault already stood, now for a measured reason. Full evidence in
  `docs/research/llm-trust-verification-2026-08-15.md`, including six
  corrections to that document's own earlier claims.

### Research

- `docs/research/wiki-embed-cap-2026-08-15.md` — the embed-cap measurement, with
  its rule committed before the numbers existed.
- `docs/research/llm-trust-verification-2026-08-15.md` — grounded verification,
  end to end.
- `docs/research/rerank-ceiling-2026-08-14.md` and `rank-factors-2026-08-14.md`
  — re-sorting the existing candidate pool by raw cosine more than doubles
  recall@1, and recency carries half of what the current ranking loses.

## [0.30.0] - 2026-08-14

v0.29.0 fixed a memory layer that had quietly stopped capturing. This release is
about the decisions it makes once it is capturing again — and about the fact
that, until now, you could not see any of them. Two of the measurements here
contradict the assumption that asked for them, and both are reported as they
came out.

### Upgrading

Nothing is required. `volatility` is a new frontmatter field and an absent value
reads as `event`, so existing memories need no migration.

Two things worth knowing before you read a heartbeat and draw a conclusion:

- **`supersede_pass` will report zero on an existing vault, at any threshold.**
  A memory without a `volatility` label counts as an event, and events are never
  closed. On a vault of 1595 memories, all 163 candidate pairs above the new
  threshold are skipped for that reason. That is the designed trade, not a
  broken guard: new captures arrive with labels, old ones do not, and the pass
  starts working again as the corpus turns over.
- **Scripts now write progress to stderr.** `KB_NO_PROGRESS=1` silences it
  everywhere; hooks and the heartbeat were already silent and stay that way.

### Added

- **A closed memory is visible again, and reversible in practice.** The design
  rested on superseding being safe because nothing is deleted. True on disk and
  false everywhere else: recall filters on `current` and `/kennisbank:review`
  walks the `unverified` queue only, so a closed memory appeared in no path a
  human uses — functionally the same as deletion. Every closure now lands in
  `.claude/memory-closed-log.jsonl` with what replaced it and why, and
  `memory-doctor.py closed` / `reopen <stem>` is the way back.
- **A discarded candidate leaves a record.** `NOOP` is the one reconcile action
  where the new memory is never written. The heartbeat counted how often;
  nothing said what. Now `.claude/memory-noop-log.jsonl`, read with
  `memory-doctor.py discarded`. Bounded at 2000 lines, because unlike closures
  these are common.
- **`volatility: state | event`, the update rule in the structure.**
  `memory_type` says what a memory is about; none of its values says "replace me
  when the value changes", so every decision re-derived that from prose — scored
  7/20, 5/20 and 4/20 across three models. `event` is the safe default because
  destroying history is the irreversible error. Measured on the live vault: of
  nine pairs above 0.85 that the old pass could have closed, three were
  genuinely different facts that merely read alike, including the locations of
  two *different* skills at cosine 0.867.
- **`kb-state-audit.py`** compares memories against an authority rather than
  against each other — the config files and the constants in these scripts are
  right by definition about what runs now. Deterministic, read-only, no model
  call. On this vault: 4 contradictions (every one a stale
  `qwen3-embedding:8b`), 11 unsupported claims, a coverage line saying how many
  memories carried nothing checkable, and a pile for memories that hold a
  checkable value but count as an event and can therefore never be corrected.
- **Progress and an estimate on every long-running script.** A sweep once ran
  ten minutes writing nothing, which from the outside is indistinguishable from
  a hang. Percentage, bar, counts, elapsed and an estimate from measured
  throughput; one rewritten line on a terminal, throttled whole lines in a log.

### Changed

- **The supersede window is aimed at the band where the real cases are.**
  Threshold 0.85 → 0.75 and `TOP_K` 2 → 3. On 149 real supersede pairs, 0.85
  saw 58% of them and 0.75 sees 95%. `TOP_K = 3` is complete rather than a
  compromise: no memory in this vault has more than three neighbours above the
  threshold.
- **Finding pairs is 11x faster, with an identical result.** The maintenance
  pass compared every memory with every other one — 1,271,215 pairs, measured at
  1171.86 s — and `cluster_promote_pass` walked the same triangle again. Routed
  through `kb-index.db` it takes 106.94 s and returns the same 163 pairs, with
  the largest cosine disagreement at 4.01e-07. It is exact, not approximate, and
  falls back to the old path whenever the index cannot answer.
- **Two prompts reordered, both measured.** `RECONCILE_SYSTEM` and
  `SUPERSEDE_SYSTEM` now ask "is this even about the same thing?" first and put
  the destructive action last. Reconcile: NOOP on unrelated pairs 25% → **0%**.
  Supersede: recognition of real replacements 30% → **55%**. Both are faster
  too.

### Fixed

- **A zero meant "nothing to do" and "this crashed" alike.** Every maintenance
  pass ran inside `except Exception: 0`, so a timeout, an ImportError and an
  idle vault wrote the same heartbeat line. The counters stay integers, because
  readers depend on that, and the reason is recorded beside them.
- **JSON parsing took the widest possible slice.** `raw[find("{"):rfind("}")+1]`
  runs to the last brace anywhere in the answer, so a model that keeps talking
  after its object broke the parse — silently, since every seam is fail-safe.
  Five seams now take the first complete object, and handle a brace in the
  *leading* prose too.
- **The upgrade stamped a tag object as if it were a commit.** Every tag here is
  annotated, so `git rev-parse v0.29.0` returned the tag's SHA, not the commit's.
  Two consecutive upgrades recorded a SHA that appears in no branch.
- **The test suite's hermeticity pin was slow here and switched off entirely.**
  It pinned `127.0.0.1:1` on the premise that a closed port refuses instantly;
  measured, every closed loopback port on this machine times out at ~2012 ms. It
  now binds a listening socket that closes at once. The larger half: an ambient
  `KB_LLM_ENDPOINT` in the user's settings beat the `setdefault`, so the pin
  never fired for the LLM seam on the machine where Ollama runs, while CI stayed
  pinned. Assigned now, with `KB_INTEGRATION=1` as the only override.

### Measured, and not what was expected

Two results in this release contradict the task that asked for them. Both are
recorded rather than absorbed, because a rule set in advance is only worth
something if it is allowed to fail.

- **The supersede judge is not too conservative.** It looked that way at 30%
  agreement. Hand-labelling 22 of the 44 pairs where it contradicts the vault's
  own history shows it is right on **19 of 22**: nearly every "miss" is the same
  memory captured twice, weeks apart, in slightly different words. Two ADR
  memories in that set supersede *each other*, in both directions. So the
  fail-safe bias stays: it costs about 3% of real replacements while the
  refusals it produces are 86% correct.
- **Growing the memory corpus cost recall.** After the first sweep under the
  raised intake caps, memory `recall@5` fell from 0.778 to **0.768** — below a
  floor recorded a day earlier — and `recall@1` from 0.322 to 0.266. Wiki holds
  at 1.000. `retrieve_top_n` is 3, and 209 more current memories compete for
  those three slots. The eval is one-sided by construction, since it asks only
  about memories that existed before the sweep, and that does not rescue the
  number. Reranking the top-20 candidates moves from worth-doing to blocking.

Reports: `docs/research/supersede-window-2026-08-13.md`,
`docs/research/supersede-judge-labelled-2026-08-13.md`,
`docs/research/recall-after-growth-2026-08-14.md`.

## [0.29.0] - 2026-08-13

The memory layer had quietly stopped capturing, and nothing said so. Three
independent causes, each invisible for the same reason: every seam is fail-safe,
so a component that never answers looks exactly like one that had nothing to
report.

### Upgrading

**Pull the new judge model, then edit your vault's pin.** The local
judge/extraction default moves from `gemma4:latest` to `qwen3.5:4b`:

```bash
ollama pull qwen3.5:4b
```

Changing the code default is not enough for an existing vault, and this is the
step to not skip: `setup.sh` copies `kennisbank-llm.example.json` to
`<vault>/.claude/kennisbank-llm.json` at install time and never overwrites it
afterwards without `--force`, so **every** installed vault carries an explicit
`"model"` — and `_llm.model_for()` returns that before it ever reaches the code
default. Set it to `qwen3.5:4b` (or whatever you actually run):

```json
{ "providers": ["ollama"], "model": "qwen3.5:4b", "endpoint": "http://localhost:11434" }
```

Leave it and the split is invisible but real: the generated Codex, opencode and
Copilot configs now put `KB_LLM_MODEL=qwen3.5:4b` in the environment, while the
Claude Code hooks and memory-sweep run without that variable and keep loading
the old model — two tags in one vault, with the hot path holding the one that
evicts the embedder. A `KB_LLM_MODEL` exported in your user environment beats
both, so check that too (`install-agent-envs.py` writes one on Windows).

Cached temporal date resolutions are keyed by model from now on, so the opt-in
`activity_llm_fallback` recomputes phrases it had already answered rather than
serving the previous model's reading of them.

### Changed

- **Capture reads 40 chunks of a session instead of 6.** The old caps (6 chunks,
  20 memories per transcript) were a cost decision from when a chunk took
  30-56 s. Measured after that cost fell, over four long transcripts and 120
  real extractor calls: 78% of all unique knowledge sits beyond chunk 6, and
  only 0.9% of candidates are duplicates. The premise behind the cap — later
  chunks repeat the early ones — is simply false, so what the sweep discarded
  was knowledge. `max_chunks` is now 40 and `max_memories_per_transcript` 60;
  the second number mattered as much as the first, because at ~4 candidates per
  chunk the old 20 stopped the write loop after five chunks regardless.
  A new per-run budget of 150 chunks keeps one sweep to roughly a quarter of an
  hour: the sweep is detached but shares one GPU with the embedding model that
  serves retrieval. It stops between transcripts, never inside one, so nothing
  lands half-read in the append-only watermark. `--all` ignores both, because
  that command promises the whole archive. Overrides: `KB_SWEEP_MAX_CHUNKS`,
  `KB_SWEEP_MAX_MEMORIES`, `KB_SWEEP_CHUNK_BUDGET`. The heartbeat now reports
  `chunks_read`, `chunks_skipped` and `budget_reached`, because "5 memories
  written" should not be indistinguishable from "5 written and 300 chunks
  ignored".
- **The local judge model now has to fit beside the embedding model.** The
  default is `qwen3.5:4b` (was `gemma4:latest`), and no generated agent config
  hardcodes `gemma4:12b` any more — that was four surfaces in
  `install-agent-envs.py`, a fifth in `_copilot.py`, two `gemma4:latest`
  fallbacks, and the opt-in temporal date fallback in `_activity.py`. They share
  one constant, guarded by
  `tests/test_llm_model_default.py`, because the old spread is what let a
  corrected environment be silently undone by re-running the installer. The
  reason is VRAM, not preference: measured on an RTX 3080 Laptop (16 GB) with
  both models resident, `qwen3-embedding:4b` at ctx 2048 costs 4.06 GB and
  `qwen3.5:4b` at ctx 4096 costs 3.13 GB, together 7.19 GB. `gemma4:12b` costs
  8.06 GB, so Ollama evicted the embedding model and the next recall met a
  30-60 s cold load against the retrieval hook's 2 s budget — retrieval stopped
  answering for whole sessions without reporting anything.
- **The embedding model is sized by context and never unloaded on a timer.**
  Ollama allocates an embedding model from `num_ctx`, not from document length,
  so `qwen3-embedding:4b` claimed 6.24 GB against 2.5 GB of weights. The vault's
  longest embedded document is about 1000 tokens, so the window is pinned at
  2048 (`KB_EMBED_NUM_CTX`) and costs 4.06 GB; the vectors are identical, proven
  by cosine 1.000000 between a 16384-ctx and a 2048-ctx embedding of the same
  text and by a fresh embedding matching the one already in `kb-index.db`. No
  re-index, no threshold recalibration. `keep_alive` is now `-1`
  (`KB_EMBED_KEEP_ALIVE`): the old 30-minute TTL meant any longer gap turned
  retrieval off for the next prompt.
- **Session start says when the embedding model is cold.** The status line adds
  `embedding-model koud` (and `(wordt geladen)` while a warm-up child is alive)
  by reading Ollama's process table. It stays a readout: `/api/ps` answers in
  about 3 ms and never loads a model, the call is capped at 100 ms, and an
  unknown state (another provider, Ollama down) says nothing rather than guess.
  Until now a cold model only surfaced through the retrieval hook, which reports
  the miss after the answer was already given without the vault. One caveat: the
  line asks about the model `_embeddings` resolves, and with no
  `kennisbank-embed.json` and no `KB_EMBED_MODEL` that still falls back to the
  legacy `OLLAMA_EMBED_MODEL` variable. If that names a model you do not run,
  the answer is an honest "cold" about a model you never chose — pin `model` in
  `kennisbank-embed.json`.
- **Copilot MCP output is compact by default.** The managed Copilot server
  registration now sets `KENNISBANK_MCP_COMPACT_OUTPUT=1`, so temporal tools
  return a short summary with at most three events and recall trims results and
  snippets. Codex, Claude, and OpenCode retain their structured temporal MCP
  responses.

### Fixed

- **The judge thought away its own answer.** `qwen3.5` is a reasoning model, and
  its chain-of-thought spent the same `num_ctx` budget as the answer. When the
  thinking filled the window, Ollama returned `done_reason: "length"` with an
  **empty** response and the reasoning in a `thinking` field nothing reads.
  Measured on three real reconcile pairs at num_ctx 4096: 30.2 / 40.3 / 55.7 s
  per call, 2106-3885 tokens of thinking, and **one call in three came back
  empty**. With `think: false`: 1.6-1.7 s, 39-48 tokens, none empty. So the seam
  was roughly 25x slower and failed outright about a third of the time — and it
  failed invisibly, because the fail-safes turn a silent model into `extract ->
  []`, `judge -> unverified`, `reconcile -> ADD`. Set `KB_LLM_THINK=1` to hand
  the budget back to the model's reasoning.
- **Capture could read only one client's transcripts.** `transcript_text()`
  looked for `message.role`, which is Claude Code's shape alone. Codex writes
  `{timestamp, type, payload}` and Copilot a flat hook-event log, so both
  produced nothing: **39 of 299 archived transcripts, 94 MB of session content**,
  including single Codex sessions of 21 and 26 MB. An unreadable transcript is
  still swept and still written to the watermark, so it looks exactly like a
  session in which nothing happened. Now 7 of 299 read as empty, together
  0.07 MB. Tool records, repeated `agent_message`s and the injected `developer`
  instruction block stay out. Note that the Copilot format holds no assistant
  replies at all, so it yields half a conversation.
- **`memory-sweep.py --help` started a real sweep.** `argv` is hand-parsed and
  `--help` fell through every branch into `run_sweep()`. Asking a script what it
  does is not supposed to be a write operation.
- **The sweep CLI discarded the raised memory cap.** `main()` hardcoded
  `max_memories_per_transcript=20` and passed it on, so the measured default
  never reached production — and `sweep-launch.py` starts the sweep through
  exactly that path.
- **Maintenance re-embedded the whole corpus before doing anything.**
  `_maintenance.current_items()` fell back to `get_cached()`, which re-embeds
  whenever the cached entry carries a different `embed_id`; on a vault where
  1506 of 1531 entries sit under an older id, every pass that builds a pool
  wanted to embed 1506 memories first. It now reads the vectors from
  `kb-index.db`, which already holds them in the current space: **16.8 s instead
  of over ten minutes without finishing.** Fail-soft — a missing index or a
  different `embed_id` falls back to the old path, and vectors from another
  embedding space are refused outright.
- **A single-flight lock could hand itself the lock on Windows.** `is_stale()`
  treated any mtime in the future as a clock change and reclaimed the lock. On
  Windows `time.time()` reads a clock with a 15.625 ms resolution while the
  filesystem stamps `st_mtime` from a finer one, so a lock the process created
  microseconds ago measures as slightly in the future: 586 of 5000 samples on
  the target machine. `sweep-launch.py`, `index-launch.py` and the SessionStart
  coordinator therefore gave away their own fresh lock about one time in eight,
  which is how two index builders could end up writing `kb-index.db` at once.
  The window is symmetric now (`abs(age) > STALE_SEC`), so a genuine clock
  change still expires a lock. Same fix in `_embeddings.warm_in_progress()`,
  where the noise spawned a second warm-up child.

### Added

- **`scripts/judge-model-sweep.py`** — compares judge models on the three seams
  they actually drive, scoring the RAW response so a fail-safe fallback is never
  counted as a success. Read-only on the vault, and it refuses to run with a
  cloud provider in the chain. Verdict for this release, in
  `docs/research/judge-model-4b-vs-9b-2026-08.md`: keep `qwen3.5:4b`. The 9b
  extracted nothing from five of six transcript chunks.
- **`docs/research/recall-baseline-2026-08-13.md`** — recall before the capture
  caps take effect (memory @5 0.778, wiki @5 1.000), so the effect of a larger
  corpus can be measured rather than assumed. `retrieve_top_n` is 3, and a fact
  that is captured but ranks fourth is as invisible as one never captured.
- **`docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md`**
  — a design for state-replaces / events-accumulate, written after the recall
  hook injected a superseded model default into the very prompt asking which
  model to use. Includes the adversarial review that cost the first draft four
  of its claims.

## [0.28.0] - 2026-08-03

Nine embedding models were measured on one real vault against its owner's own
eval sets. The default changes, and two similarity floors turn out to have been
wrong for longer than the model switch — one of them was discarding a third of
the memory layer's own index.

### Upgrading

**Pull the new model first.** `setup.sh` validates with `ollama show` and does
not pull, so a vault without it fails the install loudly rather than degrading
quietly:

```bash
ollama pull qwen3-embedding:4b
```

The first index build after the upgrade re-embeds the whole vault, because
`embed_id()` changes with the model and cross-model vectors are never reused.
Roughly eleven minutes for 1500 documents. A vault that pins `model` in
`kennisbank-embed.json` keeps its own choice — config beats the default.

### Changed

- **Default embedding model is now `qwen3-embedding:4b`** (was
  `qwen3-embedding:8b`). It is not a compromise for size: measured vector-only
  on the project's eval sets it scores wiki MRR 0.967 against 0.961 and memory
  MRR 0.540 against 0.530, at 322 ms warm p50 against 347 ms, holding 6.2 GB
  resident instead of 8.4 GB on a 16 GB card.
- **`retrieve_threshold` is 0.50** (was 0.60), in the shipped example config and
  in the runtime fallback in `kb-retrieve.py`. Measured over 329 wiki eval
  questions on the new default: true-match cosine p50 0.761, and the old floor
  discarded 13 of 329 genuine hits. **An existing vault keeps whatever its own
  `kennisbank-embed.json` says** — config beats the default — so a vault
  installed before this release still runs 0.60 until that value is edited.
- **`MEMORY_MIN_COS` is 0.45** (was 0.60), overridable with
  `KB_MEMORY_THRESHOLD`. Memories are short and atomic, so their cosine sits
  structurally below an article's: p50 0.615 against 0.761. The old floor
  discarded 366 of 806 retrievable memory hits.
- **The memory layer no longer runs a lexical arm.** RRF weighs both rankings
  equally, which pays off only when they are comparably strong. On wiki they are
  (fusion beats both arms, so it stays); on memory they differ by nearly a
  factor two in MRR and the fusion beat neither. Measured on the production
  route, memory recall@5 goes from 0.658 to 0.794. `KB_MEMORY_FTS=1` restores
  the old behaviour.
- `/sessiestart` no longer claims its context layers complement third-party
  tooling the installation neither ships nor checks for.

### Fixed

- **The memory floor was over-filtering before the model switch, not because of
  it.** Re-measured against a `qwen3-embedding:8b` index, the 0.60 floor
  discarded 260 of 798 retrievable hits there too — a third of the layer. The
  two models' distributions are close (memory p50 0.638 against 0.615), so the
  switch made an existing fault visible rather than causing it. Anyone who ran
  the previous defaults was affected.

### Added

- **Instruction prefixes per side.** e5, embeddinggemma, arctic-embed and nomic
  expect a task prefix, and a different one on the query side than on the
  document side. Configure `query_prefix` / `doc_prefix` in
  `kennisbank-embed.json`, or `KB_EMBED_QUERY_PREFIX` / `KB_EMBED_DOC_PREFIX`.
  Default empty, so nothing changes unless you set it. `embed_id()` folds in the
  document prefix, because the same text under a different prefix is a different
  vector and reusing across that is as wrong as reusing across a model change.
- **`scripts/embed-sweep.py`** — compares embedding models on quality and
  hot-path latency against a scratch vault, never the live one. Evicts every
  model before a probe and reports the load call separately from the warm
  percentiles.
- **`scripts/recall-ablation.py`** — splits recall into hybrid, dense-only and
  fts-only over one index, so the contribution of each half is measurable.
- **`scripts/rerank-eval.py`** — measures what a cross-encoder reranker would
  add, including the ceiling that reordering cannot exceed.
- `docs/research/embedding-model-sweep-2026-08.md` — method, all nine models,
  the traps (a 512-token context collapses whole-article embedding; an
  English-only model scores 0.984 on a Dutch wiki through lexical rescue alone),
  and what was deliberately not decided.

### Notes

- The 47-second p95 recorded for the old default was VRAM contention, not the
  model. The retrieval hook keeps its model resident for 30 minutes, so a second
  model loaded beside it evicted the first mid-measurement. Under
  evict-load-warmup-measure, nothing in the sweep exceeded 1017 ms p95.
- Precision was not measured. Lowering a floor admits weaker matches and there
  is no labelled set to quantify that; `retrieve_top_n` caps the effect at three
  documents.
- The semantic-tiling thresholds (0.85 / 0.62) are still calibrated for the old
  model. They run off the hot path and were left alone.

## [0.27.0] - 2026-08-01

A security audit of the script layer produced two Critical and six High
findings; this release closes the four heaviest, plus a memory defect that
could destroy a decision you had made. Three of them change behaviour you can
observe, which is why this is a minor and not a patch: a remote embedding
endpoint is now refused unless you opt in, a missing index no longer triggers a
slow fallback, and capture stops reporting success for work it did not do.

### Security

- **The embedding endpoint was attacker-controllable, and nothing noticed.**
  `_embeddings.embed` took the endpoint verbatim from `kennisbank-embed.json`,
  and the ollama branch ran *before* the API-key check. One config write sent
  every prompt, and at the next index rebuild the entire vault, to an arbitrary
  host with no credential and no warning. Reproduced against a loopback
  listener: the full prompt text arrived and `memory-doctor.cloud_warnings()`
  returned `[]`. Locality is now enforced at the sink — a non-loopback endpoint
  for a local-only provider is refused before any request is issued.
  **If you run Ollama on another machine, set `KB_EMBED_ALLOW_REMOTE=1`**;
  without it that configuration now fails closed instead of silently shipping
  your vault off-box.
- **The guard that should have caught this asserted nothing.** It scanned
  `kb-recall.py` and `_kbindex.py`, which contain zero URLs between them, so its
  assertion loop had never once executed. It now scans the modules that actually
  open sockets and carries a meta-assertion, so a URL-free file list can no
  longer pass silently.

### Fixed

- **Capture could erase a memory you had approved.** `_memory.write()` computed
  the path from the title and wrote unconditionally, so a second capture whose
  title slugified to the same stem overwrote the first. If you had approved that
  memory in between, the approval was destroyed: status back to `unverified`,
  your approved text gone, no backup, no entry in `memory-review-log.jsonl` —
  and the tool reported success. No prompt injection was needed; capturing twice
  on one topic in a session is the ordinary case. Writes now route through
  `unique_memory_path`, so a colliding title lands beside the existing memory
  instead of on top of it.
- **`_memory.set_status` corrupted the file and returned `True`.** It split
  frontmatter with `raw.split("---", 2)`, which treats a `---` inside a value as
  the closing fence. With such a title the status stayed unchanged, the file was
  left with an unterminated title line, and the success return made
  memory-sweep count a supersession that never happened — leaving a superseded
  memory injected into every prompt. Both call sites now use the anchored
  frontmatter parser, and a no-op returns `False`.
- **A missing index cost 6766 ms and 186 MB on every prompt.**
  `build-kb-index` unlinks the index before rebuilding, so for that entire
  window each prompt fell back to parsing a 170 MB JSON cache in pure Python —
  landing exactly after an upgrade or a model switch. The fallback is deleted
  rather than optimised: keeping it alive meant keeping a second retrieval
  implementation alive. **A missing index now returns a sentinel and the hook
  prints the same visible notice it already uses for a cold model**, so you see
  why there is no context instead of waiting seven seconds for it. Measured
  after: 1198 ms, essentially all of it the embedding call.
- **MCP capture reported "Vastgelegd" for a re-capture that wrote nothing.** A
  byte-identical capture now says so instead of claiming success for work that
  did not happen.

### Performance

- **Loading sqlite-vec dragged in numpy on every prompt.** The package's
  `__init__` imports `numpy.typing` for an optional helper that is never called:
  355 ms measured, 319 ms of it numpy. `find_spec` locates the extension without
  executing the module (0.6 ms) and `struct.pack` replaces `serialize_float32`.
  Serialisation is byte-identical and `vec_version` is unchanged at v0.1.9.
- **`setup.sh --skip-doctor` keeps the local gate affordable.** The closing
  doctor gate costs 15 s of a 35 s setup run, and the suite paid it six times
  for validation no test asserts on. The flag is for tests and CI that run
  `doctor.sh` themselves; a normal install should still run the gate, and the
  closing summary no longer claims doctor ran when it was skipped. Measured on
  `tests/test_setup_deploy.py`: 314.87 s to 221.94 s. This is a Windows-side
  win — the same suite takes 62 s on the Linux CI runner, where process startup
  is cheap.

### Notes

- The Copilot review was **unavailable, not skipped**: the bot reports that the
  requesting account has reached its quota limit, the same condition recorded
  for 0.26.1. This release rests on green CI, the full local suite (1123 passed,
  2 skipped) and per-finding reproduction before and after each fix.

## [0.26.1] - 2026-07-30

The C4 documentation set that shipped in 0.26.0 carried six factual errors and
one internal contradiction. This release corrects them. Nothing else changed:
no code, no schema, no output contract.

### Fixed

- **The architecture plate described a vault that does not exist.** Its storage
  box named five numbered folders where `setup.sh` creates ten, so anyone
  drawing the plate from the specification would have drawn half the vault.
  All ten are now named.
- **It claimed all four SQLite databases rebuild from the markdown.** Three do.
  `kb-usage.db` holds behavioural telemetry with no markdown ancestor and no
  rebuild path, so deleting it loses that history for good. Anyone who read the
  old note as permission to delete the derived stores was being told something
  untrue about one of them.
- **It named an Atlas lens that does not exist.** The Timeline lens was dropped
  under TASK-27.18, and the repository's own code-level documentation already
  recorded it as removed along with the route, client method and bucket type
  left behind as dead code. The plate contradicted the rest of the documentation
  set. The seven shipped lenses are now named, with a citation so the stale name
  cannot drift back.
- **`claude-cli` was missing from the documented consent boundary.**
  `CLOUD_PROVIDERS` is `{openrouter, claude-cli}` (`scripts/_llm.py:30`), and
  `claude-cli` shells out to the `claude` binary. The context document had
  narrowed the boundary to OpenRouter alone and asserted it was the only route
  to cloud generation. That was wrong in the direction that matters: neither
  `setup.sh` nor `install-agent-envs.py` offers `claude-cli`, so it is reachable
  only through `kennisbank-llm.json` or `KB_LLM_PROVIDERS` and receives no
  configuration-time warning at all. It is now back in the consent statement.
- **The per-call cloud warning is documented instead of left open.**
  `scripts/_llm.py:164-168` warns on stderr before every cloud call for any
  cloud provider. Its coverage is broader than the setup-time warning at
  `setup.sh:225`, which fires only for OpenRouter and only interactively. For a
  `claude-cli` user it is the only warning there is. Also noted: `VALUES.md`
  calls this a warning gate, but neither site gates; both only echo.
- **Two supporting facts about the detached index worker were wrong.** It does
  not exit on a stale lock: `STALE_SEC` is read only by `acquire_lock()` on the
  non-worker path, where it lets a later launch reclaim a lock left by a killed
  worker. And `_hooks_manifest.py` is not its config file; that manifest lists
  hook scripts only, and the worker's entire configuration surface is one
  `_settings.get("memory_capture")` read.
- **Two geometry errors in the plate specification.** Connector `C5` claimed to
  leave the Retrieval Engine box at an x that sits 13 px outside it, and the
  caption sat 14 px past the specification's own declared safe margin. A
  renderer following the coordinates literally would have drawn both wrong.
- **Two counting errors**, both in text that contradicted itself a few lines
  later: six versus seven component documents, and a fifth versus sixth
  container.

### Changed

- **The plate no longer quotes an exact test count.** It said 1099; the suite
  now collects 1112, and it will keep moving. A drawing does not need the
  number to make its point, so it now says "the full pytest suite".

## [0.26.0] - 2026-07-30

The MCP tool surface tells clients what it is, the server stops failing
silently, and the repository gains a C4 architecture documentation set. The
`mcp>=2` dependency bump is deliberately **not** here: see below.

### Changed

- **Every MCP tool now carries annotations, and this is not cosmetic.** A client
  derives from `annotations.readOnlyHint` whether a call needs confirmation and
  whether it may run in parallel, and defaults both to "no" when the hint is
  absent. Claude Code computes `isReadOnly()` and `isConcurrencySafe()` exactly
  that way, so the six read-only retrieval tools were presenting as
  possibly-destructive and non-parallelisable: needless confirmation prompts and
  serialisation on the interactive path. The values are earned rather than
  guessed — `capture` writes but is not destructive because it only ever creates
  a new unverified file, while `review_decide` is destructive because the write
  path refuses the memory once its status has moved.
- **The pull nudge now travels on three carriers**, because none of them reaches
  every client on its own: the `instructions` field of the protocol handshake,
  the `kennisbank://instructions` resource, and the managed block in
  `.github/copilot-instructions.md`.
- **Tool descriptions are English** per the repository language policy, and
  `timeline` and `weeklog` now point at each other. They read almost identically
  before, which made tool selection a coin flip. Tool and parameter names are
  byte-identical, so no deployed client configuration breaks.

### Fixed

- **A broken `mcp` installation no longer looks like success.** `pip install mcp`
  now resolves to 2.x, where `mcp.server.fastmcp` no longer exists. The old
  import block collapsed that into "no SDK", printed an advisory line and exited
  0, so a fresh install produced a silently dead MCP server indistinguishable
  from a healthy one. An absent package is still a user choice and stays quiet
  with exit 0; a package that is present but whose server API will not import is
  a defect and now exits non-zero, naming the exception on stderr. The blanket
  `except Exception: sys.exit(0)` is gone.
- **Two false claims removed from the source and the README.** Both stated that
  GitHub Copilot supports no MCP resources; verification showed both Copilot
  surfaces call `resources/list` and `resources/read`. The README also advertised
  "seven primitives: six tools" while omitting `review_pending` and
  `review_decide` — it is nine primitives, eight tools.
- **Two documentation guards were over- and under-reaching.** One flagged any
  document that mentioned `doctor.sh` and also contained `[warn]` anywhere, which
  condemned truthful documentation of `build-karpathy-index.py` — a script that
  really does print those markers. It now inspects only fenced blocks that
  actually show a doctor run. The other excluded `tests/` from its notion of
  "code", so opt-in tier knobs read only by the suite counted as ghost variables.

### Added

- **C4 architecture documentation** under `C4-Documentation/`: 20 code-level
  documents, seven components with a master index and relationship diagram, a
  container level with an OpenAPI specification for the Atlas sidecar and an MCP
  tool contract, and a context level with personas and user journeys. Plus a
  fully dimensioned specification for a single high-level architecture plate.
- **A wire-level MCP test harness** (`tests/test_kb_mcp_wire.py`) that spawns the
  server and speaks newline-delimited JSON-RPC to it, asserting the handshake,
  the exact tool names as a contract, the annotations and instructions as
  delivered, and that every byte on stdout parses as JSON-RPC. It replaces a
  guard that branched on "is the SDK present" and passed in either branch.

### Not in this release, on purpose

The `mcp>=2` pin bump is gated rather than scheduled. Measured: a modern-only
server dies against every client currently in use with
`McpError: Method not found: initialize`, because their first frame is
`initialize` and they never probe `server/discover`. The 2026-07-28 revision
protects a non-migrated server through its own stdio fallback rule, so waiting
costs nothing and migrating early can only lose. The gate is a client observed
actually speaking the new revision, plus a post-GA patch release of the SDK. The
full analysis, including the refuted alternative of hand-rolling the transport,
is in `docs/superpowers/plans/mcp-2026-07-28-migration.md`.

## [0.25.0] - 2026-07-29

The eval harness no longer pollutes the signal it measures, and a stray kill
switch can no longer silence usage learning unnoticed.

### Changed

- **An eval run never counts as usage (TASK-97).** The recall ranking is fed by
  usage telemetry (`_rank.usage_factor` boosts warm documents), so an eval that
  registered its own recall calls as usage was measuring a signal it had just
  moved. Worse, run from inside an agent session, its per-question output could
  be picked up by the SessionEnd transcript scan as "this document was used".
  `kb-eval.py` now sets `KB_USAGE_DISABLE=1` for the duration of every run and
  `_usage.enabled()` returns `False` while it is set, which gates all three
  writers (`log_injected`, `mark_used`, `mark_noise`).

  This is unconditional, not a flag: the safe behaviour has to be the default,
  not something you must remember. A `try/finally` restores the previous
  environment state afterwards, so an in-process caller — a long-lived host, a
  test, an eval started inside a Claude Code session — gets normal learning
  behaviour back. A `KB_USAGE_DISABLE` that was already set before the run is
  left exactly as it was.

  What you notice: the eval frames itself on stderr (`usage-telemetrie UIT`
  before the results, `weer AAN` after), so it is visible what happened.
  `stdout` stays clean for `--json` consumers. An eval still *reads* usage
  history — that is deliberate parity with what the hook actually ranks.

### Added

- **`doctor.sh` warns on a stray `KB_USAGE_DISABLE`.** Exported in a shell
  profile or system environment, that variable silently stops the KennisBank
  from learning from usage, and nothing surfaced it. A closed mechanism that
  returns nothing should be visible rather than invisible.

## [0.24.1] - 2026-07-29

Two fixes: no more console windows popping up on Windows at session start, and
the eval-set privacy guard that keeps personal eval sets out of the repository
and releases.

### Fixed

- **Windows: multiple console windows popped up at every session start
  (PR #85).** The detached index-maintenance worker in `index-launch.py` runs
  with `DETACHED_PROCESS` and therefore has no console; each maintenance job it
  spawned (`python.exe` per entry in `JOBS`) then got a freshly allocated
  *visible* console from Windows. The default job runner now passes
  `CREATE_NO_WINDOW`, so jobs run with a hidden console — and children such as
  git inherit it. Background maintenance is now invisible, as it should be.
- **Eval-set privacy guard (PR #84).** Personal eval sets
  (`eval/questions-*.json`) can never enter the repository or a release:
  enforced by `.gitignore` plus `test_eval_privacy.py`. The shipped example
  sets were replaced with fully fabricated entries so no personal vault
  content remains in the distribution.

## [0.24.0] - 2026-07-29

Evidence-first adoption of the llm_wiki-ecosystem lessons (sporen A-G,
TASK-86..92): every feature was built as an experiment behind a toggle,
measured on curated eval sets of 329 wiki / 1224 memory questions, and only
adopted on demonstrated improvement. One feature passed its gate and is now
default-on (graph retrieval); one failed and stays off with the verdict
recorded (source-overlap coupling). Also carries the two Atlas fixes that
shipped after v0.23.0 (PR #80/#81).

### Added

- **Evidence-first eval harness (TASK-86, Spoor A of the llm_wiki adoption
  plan).** Standing rule recorded in Backlog tasks 86-92: no feature gets
  adopted from any external project without an A/B measurement on eval sets
  of at least 100 questions per layer. To carry that rule the harness gained:
  `--latency` (p50/p95 wall time per recall call), `--expand`/`--no-expand`
  (offline A/B of neighbor expansion), an end-to-end injection-path test that
  parses the full hook stdout (claude-mem lesson: silent injection dropout is
  invisible when you only measure the ranking), and `kb-eval-gen.py` — a
  deterministic candidate-question generator (plus optional local-LLM
  paraphrases) that writes `*.draft.json` for human curation and can never
  touch the live sets.

- **Graph retrieval experiment behind a toggle (TASK-87, Spoor B, default
  OFF).** The weighted graph index (`kb-graph.db`, sub-millisecond
  `graph_neighbors`) existed but nothing on the retrieval path called it
  (TASK-67's own finding); the `(buur)` expansion entry instead came from a
  regex over article bodies inside the 2.0 s prompt budget. New
  `graph_retrieval` toggle selects the source of the neighbor: the graph
  (weighted by confidence, wiki-only, never displacing a direct hit, stale
  graph fails open to no neighbor) or the unchanged legacy scan.
  `retrieve_expand` stays the master switch; rollback is one setting.
  Telemetry counts neighbor injections per day (`neighbor_log` in
  kb-usage.db) and `doctor.sh` gained a "graph retrieval" check that WARNS
  when the toggle is on while the graph index is stale — the silent-empty
  failure mode TASK-15 documented. Default-flip only after the kb-eval A/B
  on 100+-question sets (adopt/reject gate in TASK-87). Also fixes the
  README toggle-table drift: it said seven behaviours while there are now
  eleven.

- **Wiki provenance in the index + bibliographic-coupling experiment
  (TASK-88, Spoor C, knob default OFF).** New `_provenance.py` extracts
  source keys per document at index time — wiki: the `[[raw-sessie-*]]` and
  `[[05-bronnen/...]]` provenance links (exactly kb-lint's contract, imported
  from kb-lint itself so the parsers cannot drift); memory: `source_session`.
  Stored in a new `doc_sources` table in kb-index.db (disposable cache — the
  backfill is simply `build-kb-index.py --rebuild`); readers fail soft on
  old indexes. `doctor.sh` reports provenance coverage per layer and warns
  when the `rank_coupling` knob is on with zero coverage. The ranking side:
  `_rank.coupling_factor` gives candidates sharing >=1 source with another
  candidate in the same result set a bounded bonus (1.05 / 1.10 — capped at
  usage-warmth level, never below 1.0; deliberately NOT llm_wiki's unfounded
  4.0/3.0/1.5/1.0 weights). Without the knob the ranking is bit-for-bit
  identical, locked by a regression test. Enabling requires the kb-eval A/B
  on 100+-question sets plus the evidence-of-improvement AC (TASK-88 #5/#6).

- **Human memory review outside Atlas + deterministic wiki-scan (TASK-89,
  Spoor D).** The unverified->current/retracted transition had exactly one
  human entry point: the Atlas GUI. Decision semantics now live once in
  `_memory.py` (approve/reject/**skip** — explicit no-op, Mem0 pattern;
  traversal guard; 400/404/409/500 codes) shared by four surfaces: the Atlas
  sidecar (refactored onto the helper with a vault-identity guard and an
  inline fallback for older vaults), `memory-doctor.py pending/decide`, the
  new `/kennisbank:review` command (the human decides per item, the command
  never decides), and MCP tools `review_pending`/`review_decide` (decide
  only after explicit user confirmation). **Crash-safe order** (llm_wiki
  #614 lesson): the status change is written durably first, the audit line
  (`.claude/memory-review-log.jsonl`) after; any failure leaves the item
  unverified and surfaces the error. doctor.sh shows the queue plus
  decisions (30d) and warns on a large queue with zero decisions. Evidence
  test replays TASK-23: 31 backed-up memories cleared through the regular
  flow, no one-off script. And `wiki-scan.py` closes /wiki step 2 — the
  last free-form LLM decision point: deterministic candidates (markers,
  promote_candidate clusters, recurring H2 headings across >=2 logs) with a
  closed `suggested_action` (herschrijf|nieuw|overslaan, tuple-validated,
  fail-safe overslaan) and a `scanned_logs` silent-empty guard; /wiki
  follows the scan, deviation only with motivation.

- **Structural hardening from ecosystem failure modes (TASK-90, Spoor E).**
  Each failure replayed as a fixture test: (1) **refusal gate** in
  `_extract` — a model answer like "ik kan deze vraag niet beantwoorden" is
  dropped before it persists as canonical knowledge (arkon#25); (2)
  **`self-source` kb-lint rule (HARD)** — provenance links inside
  `## Sessie-herkomst` to `02-wiki/`, `09-memory/`, `.claude/` or
  `06-claude/` are rejected: a stored conclusion never re-enters as evidence
  (llm_wiki #538's self-confirmation loop); (3) **`index-drift` kb-lint rule
  (advisory)** — ghost docs in kb-index.db surfaced (best-confirmed failure
  of the field: llm_wiki #580, Pratiyush `index_sync`, Arkon); (4)
  **producer provenance** — sweep-written memories carry `model_id` and
  `prompt_version` (`EXTRACT_PROMPT_VERSION`); (5) **kb-normalize.py** —
  idempotent deterministic post-pass after every LLM write in /wiki and
  /reconcile (path-prefixed wikilinks -> bare stems, 05-bronnen paths kept,
  bare tags listified; llm_wiki #576: deterministic beats instructed); (6)
  **no-network-during-ingest test** — deterministic ingest paths proven to
  make zero socket calls (arkon#29).

- **OKF v0.2 export as a rendered view of the vault (TASK-92, Spoor G).**
  `kb-okf-export.py` renders the vault as an Open Knowledge Format bundle
  (GoogleCloudPlatform/knowledge-catalog, Apache-2.0 spec) — deliberately an
  export, never internal storage: bi-temporality has no OKF equivalent and
  the vault stays on wikilinks+Obsidian. The motivating fit: OKF's trust
  tiers map 1:1 onto the memory lifecycle (unverified -> draft without
  `verified`; judge-current -> `verified: process:kb-judge`; a review-log
  approve adds `human:owner` -> human-reviewed), `generated` carries the
  producer provenance from TASK-90, `sources[]` the provenance keys from
  TASK-88, `expires` -> `stale_after`. Deterministic and byte-idempotent
  (views are rendered, not prompted); wikilinks become bundle-root-absolute
  markdown links with a broken-link count; per-directory `index.md` plus
  root `okf_version`; `log.md` rendered from activity rollups.

- **Atlas: activity heatmap, Cmd+K palette, waterfall JSON export, facets,
  CI (TASK-91, Spoor F — ideas verified in Pratiyush/llm-wiki).** Principle
  applied: view data is aggregated in the sidecar, never computed per item
  while the user waits (llm_wiki #604 went unusable at 7k pages doing the
  opposite). `/overview` now carries a 365-day activity heatmap (one SQL
  GROUP BY over kb-activity.db) and wiki freshness buckets, rendered as a
  non-graph strip in the Overzicht lens — a half-step toward TASK-44's tour
  idea. New `/titles` endpoint feeds a **Cmd/Ctrl+K palette** (jump to lens
  or open any document; index fetched once per session, pure `fuzzyFilter`
  pinned by vitest). The Recall Inspector gained **facet chips**
  (alle/wiki/memory, client-side, no query per click) and **copy-as-JSON**
  of the whole waterfall. Atlas finally runs in CI: a dedicated job with
  sidecar pytest, frontend typecheck and vitest — until now every Atlas
  change shipped unguarded. `atlas/README` corrected to the seven shipped
  lenses and the real write-path story (docs = contract).

- **`graph_retrieval` default ON — the A/B gate passed (TASK-87).** Formal
  measurement on the curated 329-question wiki set (owner bulk-accepted the
  generated candidates): recall@1 0.745 -> 0.790, @5 0.954 -> 1.000, MRR
  0.836 -> 0.882, and single-hop@1 0.777 -> 0.831 — the GraphRAG
  hurts-single-hop concern did not materialise on this vault; p95 latency
  lower. The `rank_coupling` knob stays OFF: on the same sets wiki MRR rises
  but single-hop@1 drops (0.777 -> 0.765) and memory degrades slightly —
  gate failed, reject confirmed (TASK-88). Honest new baseline for future
  work: memory recall@1 0.361 on 1224 questions is the real improvement
  space.

### Fixed

- **Atlas Graphify lens now answers HEAD on `/graphify-html` (TASK-84, PR
  #80).** The lens probe issued a HEAD request the sidecar rejected, so the
  embedded graph page never loaded.
- **Atlas launcher no longer leaves orphan processes on Windows (TASK-85, PR
  #81).** Python signal handlers never run on Windows process termination;
  the launcher now binds itself to a Job Object with KILL_ON_JOB_CLOSE so
  the OS tears down the sidecar+vite tree however the launcher dies.
- **kb-eval measured a different pipeline than the hook runs.** `_live_hits_fn`
  called `recall_hits()` without `expand=` and `min_cos=` while production
  passes both. The harness now resolves the same knobs through the same
  function (`kb-retrieve.retrieve_params`, extracted as the single source of
  truth) over the same config file. Consequence: numbers measured before this
  fix (including the TASK-70 wiki@5 = 1.000 ceiling) are not comparable to
  anything measured after it — this is the first honest baseline, not a
  regression.

## [0.23.0] - 2026-07-26

A small quality release: a vault orientation summary at session start, an
agent-focused install guide, and a test-isolation fix.

### Added

- **Vault orientation at session start (TASK-80, idea borrowed from Mind's
  `space_get`).** `kb-orientation.py` prints a compact "what lives in this
  vault" summary: document counts per layer, most recently changed articles,
  frequently used knowledge (kb-usage.db) and open backlog tasks in the
  session directory. Pure SQL reads, sub-second, no embeddings. `/sessiestart`
  runs it as its orientation step; a new opt-in toggle `orientation`
  (default off) additionally injects it at every session start through the
  coordinator's notification phase.
- **Agent install guide (TASK-82).** `docs/AGENT-INSTALL.md` gives AI agents
  the shortest correct install path per platform (Claude Code, Codex CLI,
  Copilot CLI, OpenCode, Claude Cowork) with a capability matrix; both READMEs
  link it in their opening lines. The Claude Cowork section is verified
  against the Claude Desktop 3P extensions documentation (2026-07): skills,
  plugins and MCP work there, Claude Code-style hooks do not.

### Fixed

- **Test isolation: `test_layer2_absent_degrades_gracefully` read the
  developer's real vault settings** through the `activity_llm_fallback`
  default, so enabling that toggle locally made the suite fail. The test now
  forces the settings module off.

## [0.22.0] - 2026-07-26

The knowledge graph becomes a queryable layer instead of a standalone HTML
artefact, session start gets an order of magnitude faster, and a new
checkpoint primitive bridges context compaction.

### Added

- **Checkpoint primitive (TASK-79, idea borrowed from Mind).** `/checkpoint`
  saves a forward-looking work-state snapshot to `01-raw/checkpoints/` (active
  task, open decisions, next step) and `kb-checkpoint.py` registers it in
  `.claude/kb-checkpoint-state.json`. A new opt-in toggle `checkpoints`
  (default off) additionally lets Claude's `PreCompact` hook write a stub
  automatically right before context compaction. The SessionStart coordinator
  now parses the `source` field and surfaces open checkpoints BEFORE the 300s
  freshness gate — a compact event almost always falls inside that gate, so in
  the notification phase the notice would vanish at exactly the wrong moment.
  Codex and Copilot have no PreCompact equivalent; there the write path is
  manual (`$checkpoint` / `/checkpoint`) while the notice works through the
  shared coordinator. `/sessielog` closes open checkpoints automatically.
  Design note: `docs/superpowers/specs/2026-07-26-checkpoint-primitief.md`.
- **The knowledge graph is queryable through tables in its own database
  (TASK-71).** `graph.json` is loaded into SQLite at session start
  (fingerprint-gated), so retrieval and the MCP tools can query graph
  neighbours without parsing the JSON file.
- **Deterministic edge layer and scope prune for the graph (TASK-70).**
  Wikilinks and frontmatter produce edges without an LLM pass; nodes outside
  the graphify scope are pruned during the merge.
- **Link-only provenance ring for sessions (TASK-68).** Session logs attach to
  the graph as a provenance ring without weighing in as full articles.
- **Graphify scope via `.graphifyignore` (TASK-67).** The scope lives in a
  file in the vault instead of a path argument that could differ per
  invocation.

### Changed

- **Cold session start from 35.7 s down to 1.3 s (TASK-74).** The
  notification tier is decoupled and `kb-session-start` no longer needs its
  own hook timeout above the declared ceiling.
- **Staleness count moved to the background worker (TASK-76).** The stale
  count ran on the hot path; the status line now only reads precomputed state.
- **Test suite: shared installation for the deploy inspection (TASK-77).**
  The suite ran `setup.sh` 18 times (~12.6 min); the inspection tests now
  share a single installation.

### Fixed

- **The graph survives an index rebuild (TASK-75).** The graph tables live in
  their own `kb-graph.db`, so a full rebuild of `kb-index.db` no longer drags
  them down; the status line reports "graph not loaded" instead of staying
  silent.
- **`build-graph-index.py` runs with the worker jobs (TASK-78).** The graph
  index was built on a manual rebuild but not by the background worker, so it
  silently went stale.
- **Memory: automatic deduplication and a collision check on write
  (TASK-73).** Near-duplicates are detected at capture time instead of being
  cleaned up afterwards.
- **A cold embedding model no longer fails silently.** The retrieval hook now
  states explicitly that recall was skipped and a warm-up is running, instead
  of an empty injection without explanation.
- **Knobs agree with their source again (TASK-66).** The calibration harness,
  toggles and agent-home fallbacks are now guarded by
  `test_knob_consistency`.
- **Docs: the post-install doctor transcript is real output (TASK-59).**
- **Toggle surfaces updated.** `activity_llm_fallback` was missing from the
  `set` block of `/kennisbank:settings` and from the CONFIGURATION table; the
  "7 toggles" count in the command had drifted. Both repaired while adding
  the ninth toggle.

## [0.21.0] - 2026-07-25

The four structural items the v0.20.0 analysis identified but deliberately left
out, because each needed its own design pass. Two of them change behaviour you
will notice: retrieval now has a relevance floor, and SessionStart no longer
blocks on index maintenance.

### Added

- **A relevance floor on the retrieval hot path.** The hook injected the top-k
  unconditionally: RRF fused the vector and keyword rankings and cut at k with no
  lower bound, so a prompt with nothing relevant still received the three
  least-bad documents. The memory block had no gate at all. The threshold now
  sits on the cosine, which comes free from the distance vec0 already returns and
  was discarding — computing it separately would cost 118 ms per call, twice per
  prompt, on the path that is supposed to be sub-second.
- **`/kennisbank-release`.** Releasing has been manual since v0.16.0. The skill
  codifies the procedure, including the two steps that went wrong by hand at
  v0.20.0: waiting for the Copilot review (its comments are invisible to
  `gh pr view`) and verifying the merge is on `origin/main` before tagging that
  SHA. A new test couples the changelog version, the compare links and both
  README highlight headings, so a half-finished bump fails instead of shipping.

### Changed

- **Vectors are stored normalised.** The cosine-from-distance identity only holds
  for unit vectors, and these embeddings arrive unnormalised — `_embeddings.cosine`
  normalises at comparison time, which is why it went unnoticed. Merely checking
  the assumption, as first designed, would have reported "not normalised" forever
  and the floor would never have engaged. Normalising on the write path also makes
  vec0's L2 ordering identical to cosine ordering, which is what a semantic search
  wants regardless. **Your index rebuilds once** on the first session after
  upgrading; embeddings come from the cache, so nothing is re-embedded.
- **SessionStart no longer blocks on index maintenance.** It ran the three
  builders inline: roughly 210 s worst case for Claude and Codex, 300 s for
  Copilot — the latter above the timeout that integration declares for itself, so
  the coordinator could exceed its own ceiling. `index-launch.py` now takes a lock,
  spawns a detached worker and returns. A consequence worth knowing: the
  coordinator no longer reports builder output, because the builders are no longer
  its children.
- **The embedding cache is off the hot path.** Every non-trivial prompt parsed
  tens of megabytes of JSON and ran a pure-Python cosine loop over the whole
  corpus, to decide something the index already knows. It is now the fallback for
  a vault whose index is missing or broken, behind a one-open readiness probe.
- **Hook timeouts are declared in one place.** They were scattered across three
  installers, and for Claude nothing was written at all — no file recorded what
  the default there even was. `register-hooks` only fills a timeout in when
  absent, so a hand-set value survives.

### Fixed

- **Two processes wrote the same index concurrently.** `sweep-launch.py` spawned
  the memory sweep and the index build both detached, under a comment reading
  "sweep first, then the index" — but nothing enforced that order. The worker now
  runs them sequentially behind one lock.
- **A lock with a future mtime never expired.** `acquire_lock` treated a negative
  age as "not stale", so a clock change would freeze maintenance permanently.
- **FTS dropped out on prompts containing punctuation.** `search()` passed the
  raw prompt to FTS5, which reads `?`, `/` and `+` as syntax; the resulting error
  was swallowed, so the keyword half of the fusion silently vanished on exactly
  those queries. Gate and ranking now share one expression builder.

### Not verified here

The floor changes ranking for every prompt, and `kb-eval` needs a real vault with
a local embedding model — CI has neither. Hits now carry `cos` and `fts` so the
harness can measure the threshold at all:

```
python3 scripts/kb-eval.py        # after the first session rebuilds the index
```

If 0.60 proves too strict, `KB_RETRIEVE_THRESHOLD` and `memory_threshold` lower
it without a rebuild.

## [0.20.0] - 2026-07-25

A maintenance release from a full codebase analysis. Three of the fixes are
silent-failure bugs on core paths: they produced no log, no exit code and no
doctor signal, so nothing surfaced them until the code was read end to end.
Every fix here landed with a test that was confirmed red against the unpatched
source first.

### Fixed

- **Memory recall died silently above ~1024 documents.** `_kbindex.search` sized
  its candidate pool from the corpus and capped it at 5000, but sqlite-vec
  rejects a KNN query with `k > 4096`. That `OperationalError` fell outside the
  FTS-only `try`, propagated to `kb-recall.recall_hits` and turned recall into an
  empty list — no warning anywhere. Verified directly against the extension:
  `k=4096` succeeds, `k=4097` raises. The pool is now capped at the extension's
  limit, keeping the corpus term that prevents layer starvation.
- **Every temporal question resolved to the same wrong range.**
  `_activity._alt([])` returned an empty string, which embeds as `\b(?:)\b` and
  matches the empty string at every word boundary, so every parser branch fired
  at confidence 0.95 — including for explicit ISO dates. It now returns a
  never-matching sentinel, so layer 1 misses and the next layer gets its turn.
- **`activity-locales.json` never reached a vault.** `setup.sh` deployed only
  `scripts/*.py` and `scripts/*.sh`, and `_activity` resolves the file next to
  itself with no repo-relative fallback, so every clean install ran with an empty
  layer-1 vocabulary. Combined with the bug above that was wrong rather than
  degraded. CI never caught it because CI runs from the repo root. `doctor.sh`
  now probes the *loaded* vocabulary rather than the file's presence.
- **A failed commit blocked the entire `/wiki` write path.** `safe-edit.py`
  writes the article before `git add`/`commit` — unavoidable, git only sees what
  is on disk — but had no rollback. A failing pre-commit hook left the article
  overwritten and staged, and because the tree was then dirty every later call
  refused with exit 3, while both callers forbid `--force`. The original bytes
  are now restored on any post-write failure, and a file created by that call is
  removed rather than left empty.
- **The dirty-tree guard's self-exception never fired on Windows.** The target
  path was built with the OS separator while `git status --porcelain` always
  emits forward slashes, so a tree where only the target was dirty — the normal
  case for a second pass over the same article — was refused. Non-ASCII paths
  were also mishandled: git quotes them unless `core.quotepath=false`, and the
  output was decoded with the platform default codec.
- **The graphify staleness flag was wiped on every session start.**
  `build-embed-index.py` deleted `.needs-rebuild` unconditionally, gated on the
  unrelated `embed_index` toggle, so both readers always reported "not stale" and
  the signal did not exist in practice. A test pinned that behaviour as intended
  and was replaced.
- **The rollup cache returned answers for the wrong query.** Its key carried
  neither the event limit nor the project filter, so a `weeklog` with a low
  `max_events` poisoned a subsequent `what_did_i_do` over the same period — the
  regression test reported 1 event where there were 37. Its invalidation was
  broken too, comparing two disjoint hash namespaces, so it was wiped on every
  index build. Removed rather than repaired: measured, it saved 0.88 ms and cost
  34 ms per hit.
- **Shipped artefacts hardcoded the vault path.** `CLAUDE.md.template` and the
  autoresearch skill used `~/KennisBank` while `setup.sh` honours
  `KENNISBANK_VAULT`, so on a differently-named vault the deployed `CLAUDE.md`
  pointed at a directory that does not exist. This is ADR-0002.
- **Upgrade backups landed in the directory the host scans.** Skill backups were
  written as `<name>.pre-<tag>.bak` inside `~/.claude/skills/`, where they load
  as additional triggerable skills carrying the same description as the real one.

### Changed

- **CI collects the whole test suite.** `unittest discover` does not collect bare
  module-level `test_*` functions; six files are written that way and their tests
  had never run — 763 collected against 782. One of them was the documentation
  guard, which is the root cause of the stale doc claims corrected below: the
  gate existed, but nobody ever walked past it. `pytest` is now a development
  dependency in `requirements-dev.txt`; runtime requirements are unchanged and a
  deployed vault stays stdlib-only. The job timeout was 15 minutes with a comment
  claiming 5-8; the suite takes about 20, so it is now 30.
- **MCP output contract.** `deterministic_rollup` reports `"cache": "none"`
  instead of `"hit"`/`"miss"`, since there is no longer a cache to hit.
- **Index maintenance got cheaper.** Source fingerprints are taken lazily — stat
  first, read only when mtime or size differ (measured 1.67 s warm and 51.75 s
  cold over 2220 files, for a build that usually has nothing to do). The
  embedding cache is written through a process-unique temp file and only when
  something actually changed, and `build-kb-index` returns before the embedding
  probe when there is no work.

### Removed

- **Four write-only tables.** `activity_entities`, `activity_topics`,
  `activity_artifacts` and the FTS5 table `activity_fts` were populated on every
  index build and read by no query — CREATE, DELETE and INSERT, not one SELECT.
  About 23.7 MB of 57.7 MB on the author's vault, but the real cost was latency:
  the FTS delete targets an UNINDEXED column and full-scans, 45 ms per event
  against 0.26 ms, twice per event. `ensure_schema` drops them on existing
  databases; the schema version is deliberately unchanged so no deployed vault
  flips to a warning.
- **Verified-dead code**, each re-checked by an agent tasked with proving it
  still reachable: `kb-usage-scan.assistant_text`, the `iter_activity_events`
  aggregator with four extractors, `scripts/eval-wiki-recall.py`,
  `_copilot.restore_backup`, the `_llm` api-key-environment branch, and two
  indexes the query planner never chose. Net −283 lines.

### Documentation

- **`TROUBLESHOOTING.md` told readers to break the vault resolver.** It claimed
  the path is hardcoded "in every script" and instructed editing path constants
  per script — exactly the regression ADR-0002 prevents. Untouched since
  2026-05-08, while `KENNISBANK_VAULT` landed 2026-06-14.
- **`AGENTS.md` described a superseded contract.** It still called Codex and
  Copilot hookless per ADR-005 and claimed validation expects no lifecycle hooks,
  while the code requires each hook exactly once. That file presents itself as
  the agent-facing deployment contract, so an agent following it would
  fail-validate a correct install.
- Both READMEs promised sub-second retrieval where the ceiling is 2.0 s and
  applies only to the embed call, and named three MCP primitives where there are
  six tools plus a resource. `OLLAMA_HOST` was documented as the endpoint
  KennisBank reads; it is not — the `ollama` CLI reads it, so the shell examples
  are correct and only the prose was wrong.
- **A guard against the drift itself.** Documentation here drifts by one
  mechanism: it is updated per enumeration, and whatever is not on the list
  stays. A new lint compares backticked identifiers between each language pair
  and checks code-derived facts. It found two live gaps on its first run.

### Governance

- Four task IDs were claimed by two files each. The tracked file keeps its
  number; the archived or untracked one is renumbered. Nothing was deleted: the
  analysis had claimed one archived task was a duplicate created by another tool,
  and that turned out to be false.
- Eight backlog files the tool had written were never committed, including the
  deliverable of a task already marked Done. A session-start check now warns
  about uncommitted backlog files, and a test enforces unique IDs, filename
  agreement, known statuses and existing milestones.

## [0.19.0] - 2026-07-24

### Added

- **Transcript-stripper for `/destilleer`.** Archived Claude Code transcripts
  can be huge (observed up to ~12 MB), far larger than a single context, while
  the imported raw-session logs are deliberately thin stubs. The new
  `strip-transcript.py` reduces a transcript to plain user and assistant text —
  dropping thinking, tool_use, tool_result and subagent turns, ~10-25x smaller —
  so large sessions become digestible by a fan-out of subagents. The mechanical
  jsonl-to-text logic moved to a shared `_transcript.py` reused by
  `import-cc-history.py`; output goes to stdout/scratch, never the vault, so the
  raw-session stubs stay the index.

### Changed

- **`/destilleer` and `/wiki` command guidance.** `/destilleer` now states that
  raw-session logs are stubs (compile the transcript, not the stub), documents
  the strip-plus-subagent-fan-out workflow for large or numerous transcripts,
  and notes the heavy overlap with an in-session `/sessielog` (expect low
  net-new, avoid duplicate articles). `/wiki` step 4.5 adds a `kb-lint --json`
  recipe to prove a freshly written article is provenance-clean without forcing
  a global exit 0 against pre-existing dangling articles.

## [0.18.1] - 2026-07-24

### Fixed

- **Hard runtime ceiling for UserPromptSubmit retrieval.** The single-embed and
  warm-up path introduced in v0.18.0 still trusted `KB_RETRIEVE_TIMEOUT`
  directly, so a legacy or accidentally high value could consume the client
  hook budget. Interactive prompt embedding now defaults to 2 seconds and is
  clamped by the separate `KB_PROMPT_HOOK_MAX_EMBED_TIMEOUT` ceiling. Running
  longer requires explicitly raising both values. Timeout-budget tests clear
  inherited developer and CI environment variables so this contract remains
  deterministic.

## [0.18.0] - 2026-07-24

### Added

- **Upstream-drift warning at session start.** A new `git-upstream-check`
  notification job, folded into the SessionStart coordinator, warns when the
  git repository in the session working directory has fallen behind its
  upstream (current branch and/or `main`). It is cwd-aware and fail-open —
  silent outside a git repo or when everything is up to date — and inherits the
  coordinator's freshness gate, so it never spams `git fetch`. All clients
  (Claude Code, Codex, Copilot) get it for free from the single registered
  coordinator.
- **Embedding model pre-warm.** The coordinator fires a detached, sentinel-
  guarded warm of the embedding model at session start, independent of the
  index-build freshness gate. The incremental index build does not load the
  model when nothing changed, so without this the first prompt of an otherwise
  "fresh" session paid the full cold-load.

### Fixed

- **Cold-load timeout on the prompt hot path.** The `kb-retrieve`
  UserPromptSubmit hook could time out on the first prompt of a session: the
  embedding model (~8GB) is cold, and the hook could embed twice (wiki miss →
  memory re-embed), stacking two long waits past the harness timeout and
  discarding the injected context. The hook now embeds exactly once per prompt
  (the query vector is computed in `main()` and passed to both the wiki and
  memory blocks), bounds the hot-path embed to a default timeout
  (`KB_RETRIEVE_TIMEOUT`, default 5s), and on a miss injects nothing while
  firing a detached warm so the next prompt is hot. Fully local and fail-open.

## [0.17.1] - 2026-07-19

### Added

- **Cross-client SessionStart coordinator.** Claude Code, Codex, and the
  standalone GitHub Copilot CLI register one `kb-session-start.py` handler
  instead of six to eight independent startup handlers. Independent index jobs
  run concurrently, notifications follow maintenance, rapid startup/resume
  events are freshness-gated, every child has a timeout, and failures remain
  fail-open.
- **Cross-client exit coordinator.** Claude `SessionEnd`, Codex `Stop`, and
  Copilot `sessionEnd` each register one `kb-session-end.py` handler. Capture
  completes first; independent usage attribution and Copilot immediate import
  then run concurrently. Routine output is empty, failures are time-bounded and
  fail-open, and the last aggregate diagnostic is stored locally.
- **Coordinated `/sessielog` follow-up.** Semantic summarization remains an
  agent workflow. One `kb-session-log.py` helper coordinates mechanical
  post-save indexes, sweep launch, and dependent notices.
- **ADR-006 and ADR-007.** ADR-006 formally supersedes the v0.17.0 hookless
  policy in ADR-005; ADR-007 records capture-before-follow-up and the
  semantic/mechanical sessielog boundary.

### Changed

- **Deterministic hook migration.** Setup and upgrade recognize legacy
  start/exit script basenames, replace only those entries, deduplicate the two
  coordinators, and preserve unrelated user hooks plus prompt/presearch
  behavior on Windows, macOS, and Linux.
- **Consolidated reporting.** Progress-only stderr and routine no-change output
  are suppressed. Changes and actions become at most one startup context
  payload; exit remains silent and writes local diagnostics.

## [0.17.0] - 2026-07-19

### Changed

- **Hookless Codex and Copilot integrations.** KennisBank no longer registers
  lifecycle hooks in Codex or the standalone GitHub Copilot CLI, eliminating
  client-rendered `Running ... hook` and `SessionStart hook (completed)` rows.
  Setup and upgrades remove only legacy KennisBank-owned hook entries and
  preserve unrelated user hooks.
- **Native, agent-friendly session commands.** Generated personal skills expose
  `$sessiestart` and `$sessielog` in Codex and `/sessiestart` and `/sessielog`
  in Copilot. The existing Codex `/prompts:*` aliases remain compatible.
- **Current integration contract.** README, configuration, troubleshooting, and
  agent guidance now consistently describe Claude's quiet automatic hooks and
  the explicit skill-plus-MCP model used by Codex and Copilot.

### Fixed

- **Cross-client skill discovery.** Generated skill frontmatter uses an
  explicitly quoted YAML string for `argument-hint`, allowing Copilot to load
  every generated KennisBank command skill.

## [0.16.3] - 2026-07-19

### Fixed

- **Copilot command-skill discovery.** Generated `argument-hint` frontmatter is
  now a quoted YAML string instead of a YAML list, so Copilot loads
  `/sessiestart`, `/sessielog`, and the other generated commands.

## [0.16.2] - 2026-07-19

### Changed

- **Hookless Codex and Copilot integrations.** Setup removes only
  KennisBank-owned lifecycle hooks, preserving unrelated hooks. This
  deterministically suppresses client-rendered hook progress/completion rows.
- **Native command skills.** Every command is installed under
  `~/.agents/skills/`. Copilot exposes `/sessiestart` and `/sessielog`; Codex
  exposes `$sessiestart` and `$sessielog` with `/prompts:*` compatibility.
- **Documented suppression boundary.** README, configuration, integration, and
  troubleshooting docs explain the explicit-session trade-off and upgrade path.
- **Architecture decision.** ADR-005 supersedes the Copilot lifecycle-hook
  requirement in ADR-0003 D3 and its live-hook path in D5.

## [0.16.1] - 2026-07-19

### Changed

- **Relevant, quiet hooks for Claude Code, Codex, and GitHub Copilot CLI.**
  Routine no-change indexing, sweep, archive, telemetry, and capture hooks now
  run silently through a fail-open wrapper. Changed indexes and warnings become
  concise session reports. Existing progress labels are removed during setup
  and upgrades. Retrieval, reports, and actionable notices reach each client
  through its native structured agent-context output.
- **English agent metadata.** All shipped skill descriptions and generated
  Codex prompt descriptions are English for consistent discovery across agent
  clients.
- **Reliable local query and Windows validation paths.** The pinned MCP SDK can
  now register every KennisBank tool under Python's runtime annotation rules,
  safe-edit treats CRLF/LF-equivalent input as a no-op, and Copilot doctor
  tests use Git Bash instead of accidentally crossing into WSL paths.
- **Three-client documentation.** README and integration guides now prominently
  cover Claude Code, OpenAI Codex, and the standalone GitHub Copilot CLI while
  retaining OpenCode support. Obsolete client product references were removed.

## [0.16.0] - 2026-07-19

### Added
- **Human-gated noise signal in the usage loop (yesmem lesson, TASK-17).** `python3 scripts/kb-noise.py <stem> ...` marks injected-but-unhelpful knowledge as noise (`--list` shows current marks). Ranking applies a bounded, deterministic penalty via `_rank.noise_factor` (up to −20% at 100% noise rate, floor 0.8); with zero marks the factor is exactly 1.0, so existing rankings are untouched — verified with an identical before/after `kb-eval` memory-only run (MRR 0.892). The `usage` table gains `noise`/`last_noise` columns via an idempotent in-place migration; marking is strictly human-initiated (no judge, no autonomous down-weighting).
- **GitHub Copilot CLI as a fourth local agent (`--agents copilot`).** The standalone GitHub Copilot CLI (`npm install -g @github/copilot`, invoked `copilot`, v1.0.70+) joins Claude Code, Codex, and OpenCode as a first-class local target, sharing the same vault, stdio MCP server, and local recall. New scripts: `scripts/kennisbank-copilot.py` (wrapper/launcher — a trivial exec, not a proxy), `scripts/_copilot.py` (detect/probe/validate plus install/remove), `scripts/kb-copilot-capture.py` (fail-open capture hook), `scripts/import-copilot.py` (rawlog import), and `scripts/agent-status.py` (multi-agent rollup). `setup.sh --agents copilot` installs, idempotently and login-free, the KennisBank MCP server (`~/.copilot/mcp-config.json`, key `mcpServers.kennisbank`), fail-open cross-platform hooks (`~/.copilot/hooks/kennisbank.json`, each entry with a `bash` and a `powershell` command), a managed personal-instructions block (`~/.copilot/copilot-instructions.md`), and a custom agent profile (`~/.copilot/agents/kennisbank.agent.md`, selected with `copilot --agent kennisbank`); the shared `~/.agents/skills/` set is reused as-is. All user-level paths honor `COPILOT_HOME`.
- **Copilot activity feeds temporal recall.** The capture hook writes redacted JSONL to `<vault>/.claude/copilot-events/`; `import-copilot.py` normalizes it into `01-raw/transcripts/copilot-<sid>.jsonl` with `agent=github-copilot-cli` provenance (idempotent dedupe, active-session skip; `--include-history` adds an opt-in best-effort import of Copilot's own session-state), and `build-activity-index.py` indexes it (`copilot_events`), so `/watdeedik`, `/timeline`, and the MCP temporal tools surface Copilot sessions.
- **Copilot design records and docs.** `docs/adr/0003-copilot-cli-integration.md` (authoritative design) and `docs/copilot-headroom-evaluation.md` (why the wrapper is a trivial exec, not a Headroom-style proxy). Copilot sections added to README, CONFIGURATION (section 14), POST-INSTALL (step 11), AGENTS, TROUBLESHOOTING (section 9), and `docs/agent-integrations.md`.

### Changed
- **Setup and doctor cover Copilot.** `setup.sh` accepts `copilot` in `--agents` (`claude,codex,opencode,copilot,all`); the default target set is unchanged (`claude,codex`). `doctor.sh` gained a read-only Copilot section that reports `copilot integration: not configured` (INFO, 0 FAIL) when unselected and `[PASS]`/`[WARN]`/`[FAIL]` lines when configured, distinguishing optional-missing (`copilot_missing` / `platform_binary_missing` → WARN) from broken config (validate → FAIL). Repair is a re-run of `setup.sh --agents copilot`.
- **Upgrade/migration.** Existing installs are unaffected until they explicitly add `--agents copilot`; no current agent's behavior changes and nothing new reaches the cloud. Copilot is cloud-backed and opt-in — MCP/hook/instruction install and `copilot mcp list` work without a GitHub login; only a live model turn needs a GitHub Copilot subscription and `/login`. The vault and recall stay 100% local, and auth tokens are never stored, logged, or committed.

### Fixed
- **Copilot skill frontmatter.** The `kennisbank-upgrade` and `kennisbank-contribute` descriptions now use valid folded YAML scalars, so Copilot loads both personal skills while preserving their trigger phrases. Regression coverage validates every shipped skill manifest and rejects the original unquoted `Triggers: ` delimiter.

## [0.15.0] - 2026-07-09

### Added
- **Multilingual temporal recall (deterministic locale layer).** The temporal parser now resolves dates and periods in **Dutch, English, German, French, Spanish, and Italian** from a data-only locale table (`scripts/activity-locales.json`), with exact calendar ranges. New phrase categories across all six languages: relative weekdays (`afgelopen zaterdag`, `komende maandag`), weekday-within-a-relative-week (`vorige week maandag`), week parts (`begin/midden/eind vorige week`), weekends (`afgelopen weekend`), "N units ago" in both word orders (`twee weken geleden`, `vor zwei Wochen`, `il y a deux semaines`, `hace dos semanas`), and month-by-name with year inference (`begin april`, `mei 2026`). Matching uses `casefold()` for correct handling of non-ASCII scripts.
- **Optional `dateparser` fallback (200+ languages).** When the deterministic layer does not match, an optional `dateparser`-backed fallback resolves the phrase and snaps its granularity (`week`/`month`/`year`) to a proper calendar range instead of a single day. Gated exactly like the other optional dependencies: it degrades to a clean parse error when the package is absent.
- **Optional local-LLM last resort (off by default).** For exotic or compositional phrasing (for example "het weekend voor afgelopen maandag") a local Ollama model can be used as a final fallback via stdlib `urllib`. Controlled by the new `activity_llm_fallback` setting (default `false`), cached per (phrase, reference-date) so repeats are deterministic and free, and appended to `<vault>/.claude/activity-llm-audit.jsonl`.
- **Temporal parser test set.** `scripts/test_activity_temporal.py` ships 138 deterministic cases pinned to a fixed reference date, runnable standalone and via pytest, including per-language cases, `dateparser`-gated fallback cases (skip-if-absent), and a hermetic stubbed check of the LLM layer.

### Changed
- **Temporal parser refactored to data-driven locale tables.** `scripts/_activity.py` builds language-agnostic regex templates from `activity-locales.json` and merges locales in a fixed order (nl, en first), so all prior Dutch/English behaviour resolves identically.
- **`setup.sh` and `doctor.sh` cover the multilingual fallback.** `setup.sh` installs `dateparser>=1.2,<2`; `doctor.sh` reports whether `dateparser` is present and notes that without it recall covers only the six built-in locales.

## [0.14.0] - 2026-07-08

### Added
- **Local LiteParse document intake.** New `scripts/parse-document.py` and `scripts/_liteparse.py` parse PDFs, Office files, spreadsheets, presentations, and document-like images into citeable markdown under `<vault>/05-bronnen/liteparse/`.
- **Document import command route.** `/import documents <path> [prefix]` batches LiteParse-backed source conversion while keeping imported source material separate from raw session logs.
- **LiteParse intake tests.** `tests/test_liteparse_integration.py` covers supported extensions, frontmatter rendering, lazy dependency loading, intake action routing, and dry-run directory handling.

### Changed
- **Inbox routing now uses LiteParse for source documents.** `/intake` routes PDFs and Office-like documents to `parse_with_liteparse`, while document-like images can use LiteParse OCR or fall back to the existing media description flow.
- **Setup and doctor validate document parsing.** `setup.sh` installs `liteparse>=2.0,<3`, and `doctor.sh` checks the same interpreter used by setup on Windows (`py -3`) so document parsing is validated where it will actually run.
- **OCR is opt-in.** `parse-document.py` defaults OCR off to avoid polluting native-text PDF output with missing Tesseract/tessdata diagnostics; `--ocr` enables OCR explicitly for scans.

## [0.13.0] - 2026-07-08

### Added
- **Temporal Activity Recall.** New local activity-memory layer with canonical activity events, deterministic Dutch/English date parsing, strict period filtering, topic/entity timelines, deterministic daily/weekly rollups, and a derived SQLite index at `<vault>/.claude/kb-activity.db`.
- **New user commands.** `/weeklog`, `/timeline`, and `/watdeedik` build/query the same activity API and always return source refs or a recoverable warning.
- **MCP temporal API.** `kb-mcp.py` now exposes `what_did_i_do`, `timeline`, `weeklog`, and `topic_timeline` alongside the existing `recall` and `capture` tools. Codex/OpenCode validation now requires these tools during the stdio MCP handshake.
- **Temporal eval harness.** `scripts/kb-activity-eval.py` measures date recall, period recall, topic timeline behavior, negative controls, and provenance coverage. The repo ships `kb-activity-eval-set.example.json`.
- **Architecture spec.** `docs/superpowers/specs/2026-07-08-temporal-activity-recall-design.md` records the local SQLite/file-first decision and compares the design with Mem0, Zep/Graphiti, Letta/MemGPT, and ClawMem.

### Changed
- **Setup/doctor now cover temporal recall.** `setup.sh` deploys temporal scripts and commands, builds/refreshed the activity index before the final validation gate, and SessionStart hooks include `build-activity-index.py`. `doctor.sh` reports missing/corrupt/stale activity indexes and checks temporal MCP wrappers when MCP is configured.
- **Agent integrations install temporal aliases.** Codex gets `/prompts:weeklog`, `/prompts:timeline`, and `/prompts:watdeedik`; OpenCode gets matching commands; Claude Code gets slash commands.
- **Progress output is more explicit.** Activity index rebuilds report counts, current source and elapsed time at least every 300 seconds during long backfills.

## [0.12.2] - 2026-07-07

### Fixed
- **Codex/OpenCode MCP startup is now runtime-validated.** `setup.sh` installs `mcp==1.28.1` into the same Python interpreter used by the generated MCP command, and `scripts/install-agent-envs.py` now performs a real stdio MCP initialize/list-tools handshake that requires both `recall` and `capture`.
- **Doctor now catches configured-but-broken MCP installs.** If Codex or OpenCode has a KennisBank MCP server configured, `doctor.sh` verifies that the Python MCP SDK imports successfully and fails the install when it is missing instead of leaving the agent to fail at startup.

## [0.12.1] - 2026-07-07

### Fixed
- **Codex MCP config repair is now TOML-safe.** Re-running setup no longer duplicates `[mcp_servers.kennisbank.env]` in `~/.codex/config.toml`; the replacement now consumes the full KennisBank MCP table plus subtables before writing the refreshed block.
- **Codex validation now catches malformed TOML.** The agent installer validates that Codex has exactly one KennisBank MCP table and env subtable, and parses `config.toml` with `tomllib` where available. This prevents `codex mcp list` from failing after a seemingly successful setup.

## [0.12.0] - 2026-07-07

### Added
- **Multi-agent setup and validation (`setup.sh`, `scripts/install-agent-envs.py`).** Setup now installs and validates selected agent environments with `--agents claude,codex,opencode,all`. Claude Code keeps native commands/skills/hooks, Codex receives shared skills, `/prompts:*` aliases, lifecycle hooks, MCP config and global `AGENTS.md`, and OpenCode receives commands, shared skills, MCP config, global rules and a local plugin.
- **OpenRouter as explicit opt-in LLM backend.** Interactive setup keeps `ollama` as the default and offers `openrouter` as a deliberate cloud option for judge/extraction. The live config stores only provider, model, endpoint and `api_key_env`; optional entered keys are stored user-local in `~/.config/kennisbank/secrets.json`, never in the repo or vault.
- **Post-install model smoke tests.** Setup validates the configured embedding and LLM backends before completing. Ollama uses local model/API smoke checks; OpenRouter uses a minimal authenticated chat-completions smoke check when selected.

### Changed
- **README rewritten as a stronger English product introduction.** The top-level story now presents KennisBank as a sovereign memory layer for Claude Code, Codex, OpenCode and other local agents, with a dedicated `v0.12.0` section for the new setup, validation and OpenRouter behavior.
- **Agent operating contract refreshed (`AGENTS.md`, `CONFIGURATION.md`, `docs/agent-integrations.md`).** The docs now emphasize active vault-path resolution, setup as the single install/upgrade/repair path, Codex/OpenCode behavior, MCP wiring, hooks, model validation and privacy boundaries.
- **Hook registration self-heals the active vault path.** Re-running setup updates stale `KENNISBANK_VAULT` values in Claude Code hook environment blocks instead of leaving hooks pointed at an old vault.

### Fixed
- **Non-default vault handoff no longer points back to `~/KennisBank`.** Setup's final message now reports the active vault path and selected agent targets, preventing confusing follow-up instructions after installs such as `D:/Users/Robert/Documents/Claude/Projects/Kluis`.
- **Release metadata now includes the tracked MIT license in the release narrative.** The repo already ships `LICENSE`; this release keeps README and changelog aligned around that MIT licensing contract.

## [0.11.0] - 2026-07-07

### Added
- **MCP-first toegang buiten Claude Code (`scripts/kb-mcp.py`, `scripts/kb-ask.py`, `docs/agent-integrations.md`, `adapters/registry.json`).** De lokale KennisBank is nu ook bruikbaar door andere agent-clients via een dunne stdio MCP-server met `recall`, `capture` en instructions. `kb-ask.py` biedt een CLI-brug voor handmatige vraag/antwoordflows, de adapter-registry legt client-integraties vast, en `.github/copilot-instructions.md` is de eerste native push-adapter.
- **ChatGPT-export/import (`scripts/import-chatgpt-export.py`).** ChatGPT-conversaties kunnen nu naar raw sessies worden geïmporteerd, zodat de wiki- en memory-laag niet Claude-only blijven.
- **`memory-doctor rejudge` (`scripts/memory-doctor.py`).** Na een LLM/Ollama-outage kunnen oude `unverified` memories opnieuw gejudged worden. Alleen een expliciet `current`-verdict promoveert; twijfel, model-down of exceptions blijven fail-safe op `unverified`.

### Changed
- **Herkomst/trust wordt zichtbaar en licht meegewogen in retrieval (`scripts/_memory.py`, `scripts/kb-retrieve.py`, `scripts/_rank.py`).** Memory-hits krijgen een compacte deterministische herkomst/status-tag in het injectieblok, en de memory-ranking gebruikt een kleine bounded trust-factor op `evidence_basis` (`getypt` > mens-in-lus > agent). Wiki-hits blijven ongetagd.
- **Usage-scan telt alleen load-bearing gebruik (`scripts/kb-usage-scan.py`).** Een losse prose-verwijzing naar een geïnjecteerde stem telt niet langer als `used`; alleen tool-use input geldt als werkelijk geraadpleegd. Dit voorkomt dat de agent zijn eigen injectie terugpraat en daarmee vals-positieve usage-boosts maakt.
- **Testsuite-hardening en CI-dekkingspoort (`tests/__init__.py`, `.github/workflows/ci.yml`, `requirements.txt`).** De suite is hermetischer tegen echte netwerk/model-calls, de CI-run heeft een timeout-vangnet en draait onder `coverage` met een `--fail-under=75` gate.

### Fixed
- **Backfill-cap voor mega-transcripts (`scripts/memory-sweep.py`, `--max-per-transcript`).** De `--all` her-extractie kreeg een per-transcript write-cap zodat een grote source_session niet onbeperkt facetten dumpt. De normale per-sessie sweep blijft ongewijzigd; dit raakt alleen het aantal geschreven memories per transcript in de backfill-route.
- **Deterministische exacte-body dedup vóór embeddings (`scripts/_sweeputil.py`, `scripts/memory-sweep.py`).** Exacte re-extracties worden nu op body-hash gevangen voordat cosine/embedding nodig is, zodat een tijdelijke vectorloze bestaande memory geen duplicate-escape meer veroorzaakt.
- **Embed-retry bij tijdelijke embedding-hikjes (`scripts/memory-sweep.py`).** Kandidaten waarvan `emb.embed(body)` tijdelijk `None` teruggeeft worden nu kort opnieuw geprobeerd voordat `embed_failed` telt. De route blijft fail-soft na de maximale retries en introduceert geen per-kandidaat herverwerking of extra watermark-risico.

## [0.10.0] - 2026-07-03

### Added
- **LLM-backend example + documentatie (`kennisbank-llm.example.json`, CONFIGURATION sectie 4a).** De embedding-backend had een voorbeeld-config en documentatie, maar de LLM-backend voor de memory judge/extractie (`scripts/_llm.py`) stond nergens in CONFIGURATION.md en had geen voorbeeld. Nu beide: een voorbeeld-config (default ollama/gemma4:latest, opt-in cloud openrouter/claude-cli, per-provider model-overrides, ordered local-then-cloud fallback-chain) en sectie 4a (provider-keten, `KB_LLM_*` env-vars, config-precedentie, en de noot dat dit bestand niet auto-gedeployed wordt). Met de 'pin your model'-gotcha: de code-default is de tag `gemma4:latest`; heeft je lokale Ollama een andere tag (bv. `gemma4:12b`) dan faalt de sweep-probe stil en meldt de heartbeat `model_unreachable: true` terwijl Ollama draait — capture produceert dan niets. Check `ollama list` en pin de tag.
- **Provenance met tanden: fail-closed op niet-herleidbare herkomst (`kb-lint.py --strict`, doctor 13d FAIL-tier, `/wiki` stap 4.5).** Tot nu toe was elke provenance-poort zacht: `/wiki` stap 4.5 was een model-prompt met ontsnapping ("waarschuwingen mag je laten staan") en doctor 13d mapte alles naar WARN. Een destillatie-hallucinatie die een `[[raw-sessie]]`-link sloopt (missing/dangling artikel) kon zo ongezien landen. kb-lint onderscheidt nu HARD findings (missing/dangling = niet-auditeerbaar) van advisory (path-only): `--strict` geeft exit 2 alleen op HARD (path-only blijft exit 0), het JSON-rapport draagt een `hard`-teller, doctor 13d promoveert HARD naar FAIL (path-only blijft WARN), en `/wiki` stap 4.5 draait `--strict` als harde stop vóór afronden. Deterministisch, nul LLM-kosten, werkt op elke topologie (geen git-hook/CI, geen cloud-push). Bewust NIET als green-CI merge-gate (vault staat buiten de repo; zou soevereiniteit schenden) — governance-hardening binnen de bestaande hook/command-laag. TASK-13.

### Fixed
- **kb-eval fidelity: per-laag meten i.p.v. gefuseerde ranking (`scripts/kb-eval.py`).** Het harnas fuseerde wiki+memory in één ranked lijst, maar de UserPromptSubmit-hook injecteert die lagen als TWEE gescheiden, gelabelde blokken (`_wiki_block` via wiki_hits, `_memory_block` via memory_hits) en fuseert nooit. De gefuseerde meting scoorde daardoor een topologie die de hook niet gebruikt en gaf vals signaal: op een vault met een gevulde geheugenlaag kelderde de gerapporteerde wiki-recall@1 van 0.914 naar 0.314 doordat memories in de gefuseerde lijst wiki-artikelen verdrongen — een "regressie" die in productie niet bestaat (de blokken staan los). kb-eval meet nu per laag (wiki-set wiki-only, geheugen-set memory-only) en draait zonder `--set` beide sets in één run, elk tegen zijn eigen laag. `--layer wiki|memory` voor een custom set.

### Added
- **Geheugen-eval-set (`06-claude/kb-memory-eval-set.json`, `kb-memory-eval-set.example.json`).** Aparte eval-set met geheugen-verwachte antwoorden, zodat de nuttigheid van het geheugen-blok meetbaar is i.p.v. als ruis geteld te worden tegen de wiki-set. Eerste baseline op de Kluis-vault (588 memories na backfill, qwen3): memory recall@1 0.529, recall@3 0.882, MRR 0.686 — de over-extractie van de mega-sessies (148 memories uit één transcript) verdunt de rang-1-precisie meetbaar, terwijl top-3 gezond blijft.

## [0.9.0] - 2026-07-02

### Added
- **Usage-telemetrie: de retrieval-feedbackloop (`scripts/_usage.py`, `scripts/kb-usage-scan.py`).** Het grootste gat uit de externe review gedicht: het systeem leert nu welke kennis daadwerkelijk hielp. kb-retrieve registreert per injectie welke stems het injecteerde (pending in eigen `kb-usage.db`, bewust los van kb-index.db zodat gebruiksgeschiedenis modelwissels en index-rebuilds overleeft); een nieuwe SessionEnd-hook scant het transcript en markeert stems die in assistant-tekst of tool-calls voorkwamen als gebruikt (de injectie zelf, in user-berichten, telt niet mee). Het signaal voedt: (1) een gebruiks-boost in de ranking (`_rank.usage_factor`: ×1.10 bij gebruik ≤30d, ×1.05 ≤90d, voor beide lagen — een warm wiki-artikel is bewezen nuttig); (2) gebruiksdecay in `stale-check.py`: een recent gebruikt artikel is niet staal, hoe oud zijn `updated` ook is. Gegate op de `usage_telemetry`-toggle (default aan), fail-open op elke route.
- **Drempel-kalibratie-harnas (`scripts/kb-calibrate.py` + `kb-calibrate-set.example.json`).** Alle cosine-drempels (dedup 0.92, rewrite 0.83, reconcile 0.75, conflict 0.62, retrieve 0.60) zijn getuned op qwen3-embedding:8b; een modelwissel maakte die kalibratie stilletjes ongeldig. Het harnas embedt een handgelabelde parenset (duplicate/related/unrelated, `<vault>/06-claude/kb-calibrate-set.json`) met het actieve model en stelt per drempelklasse een grens voor, met separatiemarge en een OK/HERIJK-oordeel per huidige knop. Schrijft niets: de mens beslist. Nulmeting op qwen3 (24 paren): duplicate-grens schoon op 0.786 (alle huidige knoppen OK), related-grens toont overlap (exit 2) — het harnas meldt eerlijk wanneer de set of het model de klassen niet scheidt.
- **Memory-typering (`memory_type: feit|voorkeur|procedure|beslissing`).** De extractie typeert elke kandidaat (CrewAI/Cognee-les: verschillende kennistypes verouderen verschillend); `_memory.render` schrijft het veld, onbekende types vallen terug op `feit`. Bestaande memories zonder veld gedragen zich als `feit`.
- **Retrieval-scoring: relevance × recency × importance (`scripts/_rank.py`, Generative-Agents-patroon).** De judge kent bij capture een `importance` (1-5) toe; de recall-route herweegt memory-hits met een recency-verval (halfwaardetijd per memory_type: voorkeur 180d, feit/procedure 365d, beslissing 730d; vloer 0.6 zodat oud-maar-relevant nooit verdwijnt) en een importance-factor (0.9-1.1). De wiki-laag blijft ongewogen (gecureerd; stale-check bewaakt veroudering daar). Eval-hermeting op de Kluis-vault: identiek aan de nulmeting (recall@1 0.971, MRR 0.986) — geen regressie.
- **Derde retrievalsignaal: één-hop graafbuur-expansie (`_rank.one_hop_neighbor`, kb-recall/kb-retrieve).** Na de directe wiki-hits wordt de meest-verwezen wikilink-buur van die hits als extra entry toegevoegd (gemarkeerd `(buur)`), zodat de evidence pack een coherente kennisbuurt wordt in plaats van losse hits. Buren verdringen nooit directe hits. Default aan in de UserPromptSubmit-hook; uit te zetten met `KB_RETRIEVE_EXPAND=0` of `"retrieve_expand": 0`.
- **Recall-eval-harnas (`scripts/kb-eval.py` + `kb-eval-set.example.json`).** Meet recall@1/3/5 en MRR van de retrieval-route (dezelfde hybride cosine|FTS5-route als de UserPromptSubmit-hook) tegen een persoonlijke eval-set van vragen met verwachte documenten (`<vault>/06-claude/kb-eval-set.json`). Per-type breakdown (single-hop, keyword, paraphrase, oblique, temporal, multi-hop), `--json` en `--verbose`, injecteerbare `hits_fn` voor tests. Zonder meting is elke retrieval-wijziging gevoelsmatig; draai dit voor en na elke wijziging aan drempels, embeddingmodel of ranking. Nulmeting op de Kluis-vault (35 vragen, qwen3-embedding:8b): recall@1 0.971, recall@3 1.0, MRR 0.986; sabotage-run (onzin-vragen) scoort 0.0, dus het harnas kan falen.
- **Bi-temporeel geldigheidsmodel voor memories (`scripts/_memory.py`).** Elke memory krijgt `valid_from` (event-tijd: wanneer het feit ging gelden; default = `created`) naast `created` (capture-tijd), en optioneel `valid_until` (sluiting). De sweep zet `valid_from` op de sessiedatum uit de transcriptnaam, zodat een laat geïmporteerd transcript een feit op zijn echte ingangsdatum plaatst. Superseden en expiren stempelen `valid_until` (oud feit gold tot het nieuwe inging, resp. tot de expires-datum). Geïnspireerd op Zep/Graphiti's temporele kennisgraaf (LongMemEval-gat van 15 punten tegen niet-temporele systemen), gemodelleerd in markdown-frontmatter plus sqlite — geen graph-database nodig.
- **Write-time invalidatie in de capture-sweep (`scripts/_reconcile.py`, Mem0-patroon).** Nieuwe kandidaat-memories worden op schrijfmoment gereconciled tegen de meest gelijkende bestaande memories (current + unverified): per buur beslist een LLM-seam tussen ADD (echt nieuw), SUPERSEDE (nieuw feit vervangt/weerlegt oud; oude memory wordt gesloten met `superseded_by` + `valid_until`) en NOOP (al afgedekt; kandidaat wordt niet geschreven). Fail-safe-to-ADD: een dode of onparseerbare judge is nooit destructief. Deterministische temporele guard: een kandidaat uit een ouder transcript kan een nieuwer feit nooit invalideren (beschermt `--all`-rebuilds). Drempel-interplay gedocumenteerd: dup-skip (>0.92) blijft vóór reconcile voor idempotentie; de reconcile-band is 0.75-0.92 (top-2 buren); de bestaande supersede-pass (0.85, current-only) blijft als vangnet. Heartbeat/samenvatting tellen `reconciled_superseded` en `reconcile_noop`.
- **Guardrails uit de adversariële verificatie (32-agent review op bovenstaande).** Vier gedragsregels die de eerste implementatie miste, elk met regressietest: (1) `supersede_pass` ordent nieuwer/ouder op event-tijd (`valid_from`, fallback `created`) zodat een laat gecaptured oud feit een nieuwer feit niet kan sluiten met een geïnverteerd geldigheidsinterval; (2) de dedup is era-bewust (`_dup_skip`): een her-assertie van een eerder gesloten feit met latere `valid_from` (flip-back: "Jim zoekt weer een baan") is géén duplicaat en bereikt de reconcile-laag, terwijl her-captures uit hetzelfde tijdperk duplicaat blijven; (3) een kandidaat die zelf `unverified` landt mag geen `current` memory superseden (quarantaine sluit geen geverifieerde kennis; de supersede-pass pakt het paar op zodra beide current zijn), en een NOOP-verdict tegen een unverified buur telt niet; (4) `set_status` schrijft replacement-waarden literal (lambda i.p.v. string-replacement; geen `re.PatternError` op backslashes) en de expire-pass is fail-soft gewrapt. Bekende, gedocumenteerde beperking: een tegenspraak die >0.92 embedt tegen een open memory wordt als duplicaat geskipt — prijs van LLM-vrije idempotentie.
- **Provenance-lint (`scripts/kb-lint.py` + doctor-sectie 13d).** Valideert dat elk wiki-artikel in `02-wiki/` herleidbare sessie-herkomst heeft: minstens één resolvende `[[raw-sessie-...]]`-wikilink naar `01-raw/sessies/` of `08-archive/`. Drie finding-types: `missing` (geen enkele sessieverwijzing), `dangling` (dode wikilink), `path-only` (herkomst alleen als backtick-pad of proza, onzichtbaar voor backlinks en de kennisgraaf). Exit-conventie 0/1/2 (schoon/fout/waarschuwingen), `--json` voor machine-leesbare uitvoer; `doctor.sh` rapporteert de samenvatting als PASS/WARN. Rationale: een gecompileerd artikel zonder werkende link naar zijn raw-sessie is niet auditeerbaar — een hallucinatie tijdens destillatie wordt dan een duurzaam "feit" dat nooit meer tegen de bron te checken is.
- **Per-kernpunt sessie-herkomst in template en `/wiki` (`templates/tpl-wiki-artikel.md`, `commands/wiki.md`).** De `## Sessie-herkomst`-sectie krijgt een verplicht, machine-leesbaar formaat: `- <kernpunt, kort>: [[raw-sessie-YYYY-MM-DD-slug]]` — herkomst per claim in plaats van per artikel, altijd als wikilink (nooit backtick-pad). `/wiki` legt de koppeling op destillatiemoment (stap 4), valideert direct met kb-lint (stap 4.5), en bewaart bestaande herkomst-regels bij rewrites (stap 3.5). `## Bronnen` is voortaan exclusief voor externe bronnen (APA7).
- **Idempotent-veilige setup/upgrade (`setup.sh`, `scripts/_migrations.py`).** `setup.sh` is nu veilig om opnieuw uit te voeren voor zowel nieuwe als bestaande vaults: het ververst de tooling (scripts, templates, commands) zonder user-data te overschrijven of aanpassingen te verliezen. Idempotent via schema-version-stamp `<vault>/.claude/.kennisbank-schema-version` (v0.9.0), bewust los van de `.kennisbank-version` release-tag-stamp van de upgrade/contribute-skills.
- **Volledige hookset-registratie via `register-hooks.py --manifest` (`scripts/register-hooks.py`).** Registreert niet langer slechts twee retrieval-hooks, maar de volledige set: SessionStart (build-embed-index, distill-notify, build-kb-index, sweep-launch), SessionEnd (archive-transcript), UserPromptSubmit (kb-retrieve), en PreToolUse matcher WebSearch|WebFetch (kb-presearch). Alle hooks samen in één atomaire operatie.
- **Interpreter-aware hook-registratie (`scripts/register-hooks.py`).** Detecteert het platform en gebruikt `py -3` op Windows, `python3` elders; een self-heal op stale paden behoudt de originele interpreter zodat opnieuw registreren het platform niet verwisselt.
- **`scripts/_migrations.py` version-stamp + runner.** Beheert `<vault>/.claude/.kennisbank-schema-version` (apart van de upgrade-skill's `.kennisbank-version` release-tag-stamp), voert version-gated migraties uit (momenteel: geheugen-dirs, volledige hookset, toggle-migratie), en houdt de vault actueel over releases. De `kennisbank-upgrade`-skill delegeert z'n deploy nu aan `setup.sh` zodat upgrades de hooks/migraties/deps krijgen. Fail-soft per migratie; alles draait bij setup en upgrade.
- **Settings-migrate (`scripts/_settings.py.migrate()`).** Aanvullende helper voor het stellen van ontbrekende toggle-defaults in `kennisbank-settings.json`, inclusief backward-compatibility voor oude installs.
- **Learnings-file standaard AAN (`CLAUDE.md.template`, `commands/sessielog.md`, `POST-INSTALL.md`).** De `LEARNINGS_FILE`-regel is nu een actieve, ongecommente default-regel (`LEARNINGS_FILE=~/Claude/learnings.md`) i.p.v. een fenced voorbeeld; comment de regel uit of verwijder 'm om uit te zetten. `/sessielog` leest deterministisch de eerste ongecommente `LEARNINGS_FILE=`-regel, expandeert `~`, en maakt het bestand aan als het ontbreekt. Voorheen werd de stap stil overgeslagen als de regel in een code-fence stond. Complementair aan de automatische `09-memory/`-laag.
- **Hybrid wiki-recall in UserPromptSubmit-hook (`scripts/kb-recall.py`, `scripts/kb-retrieve.py`).** Dual-gate cosine|FTS5 + cosine-fallback — exacte termen vinden nu ook wiki-artikelen. Eval-helper `scripts/eval-wiki-recall.py` demonstreert before/after via `has_fts_match` + `wiki_hits`.
- **Cross-memory onderhoud v2 (`scripts/memory-sweep.py` + `scripts/_maintenance.py`).** De sweep draait na elke capture-loop drie onderhoudspassen: supersede (nieuwer spreekt ouder tegen → status superseded + link), 2e-lijn-hercontrole (her-judge current → retract bij non-current), en cluster-promotie (markeer `promote_candidate: true` voor /wiki bij ≥2 verwante buren). Gegate op `memory_capture`, fail-soft per pass; samenvatting in de heartbeat (`superseded`, `rechecked_retracted`, `promote_marked`).
- **Presearch hook (`scripts/kb-presearch.py`, PreToolUse).** Injecteert geheugen+wiki voor WebSearch/WebFetch vóór externe zoekactie (matcher `WebSearch|WebFetch`), niet-blokkerend, gegate op `memory_recall`.
- **CC transcript-archief (`scripts/archive-transcript.py`, SessionEnd-hook).** Archiveert elk transcript naar `01-raw/transcripts/`, fail-open en idempotent. Overleeft `cleanupPeriodDays`.
- **`/destilleer`-commando + `scripts/distill-notify.py` (SessionStart).** Piggyback-destillatie: melding van openstaande transcripts plus een commando dat ze via `import-cc-history.py --source` naar `/wiki` ketent. Watermark in `.distilled`.
- **`import-cc-history.py --source <dir>`.** Importeert een platte transcript-archiefmap.
- **Settings-store (`scripts/_settings.py`, `kennisbank-settings.json`).** Vier achtergrond-automatieken (auto-archive, distill-notify, embed-index, daily-graphify) zijn individueel aan/uit via een platte JSON-store. Gedeelde `get/set/init`-helper plus CLI; enige lezer/schrijver, geen key-drift.
- **`/kennisbank:settings`-commando.** Toont de toggles met huidige staat en zet ze aan/uit (genamespacet, deployt naar `~/.claude/commands/kennisbank/settings.md`).
- **Settings-bootstrap in `setup.sh` en de `kennisbank-upgrade`-skill.** Verse setup schrijft defaults (of vraagt interactief); upgrade vraagt ontbrekende toggles uit.
- **Memory-toggles (`memory_capture`, `memory_recall`, default aan) + `09-memory/`-fundament.** Twee nieuwe opt-in-knopen voor automatische memory-extractie en -injectie; `_memory.py`, frontmatter-contract en settings-defaults zijn aanwezig.
- **Geheugen-recall (`scripts/kb-recall.py`, `scripts/kb-retrieve.py`-hook, SessionStart-indexbouw).** `kb-recall.py` injecteert additief memory-fragmenten (`09-memory/`) in de retrieval-hook; gegate op `memory_recall`. `build-kb-index.py` draait als extra SessionStart-hook naast `build-embed-index.py` om `kb-index.db` vers te houden.
- **Autonome capture-sweep + detached launcher (`scripts/memory-sweep.py` + `scripts/sweep-launch.py`, SessionStart).** `memory-sweep.py` orchestreert de extract -> dedup -> judge -> schrijf pipeline over pending transcripts. `sweep-launch.py` spawnt de sweep DETACHED (niet-blokkerend) met een single-flight lockfile, gevolgd door `build-kb-index.py` (sweep-voor-index-ordening); gegate op `memory_capture`; exit 0 fail-open.
- **Upgrade-backfill (eenmalig memory-sweep over transcript-archief).** De `kennisbank-upgrade`-skill draait bij upgrade naar deze versie eenmalig `memory-sweep.py --all` over de bestaande transcript-backlog (idempotent via dedup), na bevestiging als `memory_capture` aan staat. Voltooit het geheugen-subsysteem: rebuild-memory, health-doctor, backfill.
- **Lokale stdio MCP-server (`scripts/kb-mcp.py`, optioneel).** Exposeert geheugen + wiki als `recall`-tool aan compatibele lokale MCP-clients via stdio; read-only via `kb-index.db` en lokale Ollama-embeddings. Vereist eenmalig `pip install mcp`; zonder de dep meldt het script dit netjes en de rest van KennisBank (hooks, sweep) werkt onafhankelijk.

### Changed
- **Hooks gaten zichzelf op hun toggle.** `archive-transcript.py` (auto_archive), `distill-notify.py`-meldpad (distill_notify) en `build-embed-index.py` (embed_index) eindigen fail-open als hun toggle uit staat. De daily-graphify-batch in `sessielog`/`wiki`/`destilleer` respecteert `daily_graphify`.
- **`setup.sh` deployt nu ook genamespacede commands** (`commands/*/*.md`) met behoud van de subdir-structuur.
- **`setup.sh` en `register-hooks.py` volledig geïntegreerd voor idempotent upgraden.** Setup.sh voert `_migrations.py` uit na registratie van hooks, dus existing installs krijgen toggle-defaults en version-stamp in één stap. Oude upgrades hoeven alleen `bash setup.sh` opnieuw te draaien.

### Behaviour change
- **`auto_archive` is default UIT.** Bestaande installaties stoppen na deze update met automatisch archiveren tot `auto_archive` expliciet aan wordt gezet. De `kennisbank-upgrade`-skill vraagt dit actief uit. Reden: opt-in, conform de wens "kan inschakelen".
## [0.8.2] - 2026-06-22

Retrieval hooks are now registered automatically, closing the cold-cache footgun
where `/uitdaag`, `/brug`, and `/wiki` self-rewrite silently found nothing on a
fresh install.

### Added

- **`scripts/register-hooks.py`** -- an idempotent, non-destructive merger that
  registers KennisBank hooks in `~/.claude/settings.json`. Existing hooks,
  permissions, env, and other settings are preserved; re-running is a no-op; a
  stale script path self-heals; an unparseable settings file is refused rather
  than clobbered.
- **`setup.sh` registers the retrieval hooks**: `SessionStart` -> `build-embed-index.py`
  (warms the wiki embed cache) and `UserPromptSubmit` -> `kb-retrieve.py` (injects
  matching wiki snippets). Skip with `--no-hooks`.
- **`doctor.sh` check #13** verifies both hooks are registered, warning (never
  failing) when they are missing or the settings file is absent/unparseable.

## [0.8.1] - 2026-06-22

Slash-command launchers voor de lifecycle-skills en vault-pad-consistentie voor de
v0.8.0-commands.

### Added

- **`/kennisbank-upgrade`** en **`/kennisbank-contribute`** — slash-command launchers
  voor de gelijknamige lifecycle-skills, zodat upgrade en contribute direct als
  commando aanroepbaar zijn (de skills bleven anders alleen model-getriggerd).

### Changed

- **Vault-pad-resolutie in de v0.8.0-commands.** `wiki.md`, `reconcile.md`,
  `uitdaag.md`, `brug.md` en `sessiestart.md` roepen scripts nu aan via
  `VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"` in plaats van een hardcoded
  `~/KennisBank`-pad, in lijn met de repo-brede env-var-fix (PR #11) die deze
  nieuwere commands nog niet dekte. Een regressie-guard
  (`NoHardcodedVaultInCommandsTest`) bewaakt dit voortaan.

## [0.8.0] - 2026-06-21

Vault-onderhoud en denkgereedschap layer: self-rewriting `/wiki` with hybrid-autonomy
guards, contradiction detection and reconciliation, adversarial thinking tools, and
progressive context budgets.

### Added

- **Self-rewriting `/wiki` via `safe-edit.py`** (hybrid-autonomy edit engine). Guards
  every automated wiki rewrite by line-change count (`KB_EDIT_MAX_LINES`, default 20),
  heading removal, and deletion count (`KB_EDIT_MAX_DROP`, default 3). Edits that
  exceed any guard are held back and proposed for human review instead of being applied
  silently. (Similarity-based rewrite matching is handled by `find-similar.py` via
  `KB_REWRITE_THRESHOLD`, not by `safe-edit.py`.)
- **`scripts/find-similar.py`** — candidate match finder: returns the most
  semantically similar wiki articles for a query or article, powering `/wiki`'s
  de-duplication awareness.
- **`scripts/kb-search.py`** — query retrieval CLI: search the vault by
  natural-language query and return ranked results, usable standalone or wired into
  commands.
- **`scripts/conflict-scan.py`** — contradiction detection: compares wiki passage
  pairs and flags semantically similar but factually diverging claims. Threshold
  `KB_CONFLICT_SIM` (default 0.62).
- **`scripts/context-budget.py`** — progressive L0-L3 context layers: selects how
  much vault context to load at session start based on `KB_CONTEXT_LEVEL` (default
  1 = L1). L0 = bare minimum, L1 = default, L2 = extended, L3 = full.
- **`commands/reconcile.md`** (`/reconcile`) — surfaces contradictions detected by
  `conflict-scan.py` and produces a reconciliation audit trail.
- **`commands/uitdaag.md`** (`/uitdaag`) — adversarial thinking tool: challenges a
  claim or article for weak reasoning, missing evidence, or overgeneralization.
- **`commands/brug.md`** (`/brug`) — thinking tool: finds conceptual bridges and
  shared principles between two topics or articles.

### New env vars

| Variable | Default | Controls |
|----------|---------|---------|
| `KB_EDIT_MAX_LINES` | `20` | Max lines changed per automated `/wiki` edit pass |
| `KB_EDIT_MAX_DROP` | `3` | Max non-blank lines deleted per automated edit pass |
| `KB_REWRITE_THRESHOLD` | `0.62` | Min cosine similarity for auto-apply of a rewrite |
| `KB_CONFLICT_SIM` | `0.62` | Min cosine to classify passage pair as potential contradiction |
| `KB_CONTEXT_LEVEL` | `1` | Progressive context layer loaded at session start (0-3) |

## [0.7.0] - 2026-06-21

Swappable embedding backend and push-based wiki retrieval, plus cost-gated
graph upkeep and two contribute-skill safeguards.

### Added

- **Swappable embedding provider (`scripts/_embeddings.py`).** Config-driven
  backend (`ollama` | `openai` | `voyage`) behind a single `embed()` interface,
  so the embedding model is a one-file choice instead of a code change. Cross-
  model-safe cache keying via `embed_id()` (provider:model) plus dimension; a
  model switch invalidates the cache by design. Length-guarded `cosine()`,
  shared cache. Config via `kennisbank-embed.json` or `KB_EMBED_*` env; API key
  referenced by env-var NAME only, never stored.
- **Prompt-time wiki retrieval hook (`scripts/kb-retrieve.py`).** UserPromptSubmit
  hook embeds the prompt once and injects the top-N matching wiki articles above
  a threshold as `additionalContext` — push, not pull. Fail-open always: any
  error, missing backend, empty cache, or trivial prompt yields no output and
  exit 0. Cheap pre-filter skips short/slash/trivial prompts before the embed.
  Tuned threshold 0.60 for `qwen3-embedding:8b` (real match 0.73-0.80,
  noise <= 0.51).
- **Embedding index builder (`scripts/build-embed-index.py`).** SessionStart
  hook that warms/refreshes the wiki embedding cache off the per-prompt path.
  Self-locating, incremental, prunes vanished files.
- **`kennisbank-embed.example.json`** — sanitized default (ollama/qwen3, empty
  `api_key_env`), deployed by `setup.sh` (skips if a live config is present
  unless `--force`).

### Changed

- **`scripts/semantic-tiling.py` refactored onto `_embeddings`** — shares the
  cache and keeps the same thresholds/behaviour.
- **`/sessielog` wires incremental `/graphify --update` into Step 2** (before
  auto-crosslink), so new article nodes exist when crosslinks are added — fixes
  the stale-graph "geen nodes gevonden in graph.json" miss.
- **`/sessielog` daily-batch graph gate (cost control).** `--update` runs only
  on the first session where `graph.json` is >20h old; every session still
  appends changed paths to `.needs-rebuild` for free. auto-crosslink runs only
  when `--update` ran. Self-pacing off `graph.json` mtime, no cron.
- **`CONFIGURATION.md`** section 4 rewritten for the `_embeddings.py` backend
  (`KB_EMBED_*`), the retrieval hook, and the index builder (`KB_RETRIEVE_*`).
- **`tests/test_setup_deploy.py`** asserts the new scripts and config deploy.

### Fixed

- **`kennisbank-contribute`: branch-first gotcha.** Documents the failure mode
  where contribute edits committed to local `$DEFAULT` make a branch-off-DEFAULT
  PR show no diff and leave `$DEFAULT` ahead of origin with PR-bound commits a
  stray push would leak — plus the recovery (branch at HEAD, reset `$DEFAULT`
  to origin) and the rule.
- **`kennisbank-contribute`: localization auto-skip.** The scan now normalizes
  deploy-localized path/vault-name rewrites back to portable form and re-diffs;
  pure-localization files (symmetric `+N -N` diffstat) are skipped, so a
  contribute run over a long-deployed vault no longer surfaces every path-
  localized file as a candidate (which "default: all" would ship as a broken,
  path-leaking PR).

## [0.6.1] - 2026-06-20

Tooling self-update: the lifecycle skills now manage every skill, not just
autoresearch. Plus a test-coverage tightening.

### Changed

- **Skills deploy map generalized to `skills/*/`.** `kennisbank-upgrade` now
  refreshes every installed skill (including `kennisbank-upgrade` and
  `kennisbank-contribute` themselves), backing up each skill it overwrites;
  `kennisbank-contribute` can isolate and PR improvements to any repo-known
  skill. Personal/local-only skills (no `skills/<name>/` counterpart in the
  repo at BASE) are gated out via `git cat-file -e` and are never contributed.
- `tests/test_setup_deploy.py` also asserts `autoresearch` is installed, making
  the deploy test a complete guard for all three skills.

## [0.6.0] - 2026-06-20

Multilingual embedding default, configurable tiling thresholds, a deploy-gap
fix, and two new lifecycle skills for upgrading a vault and contributing
improvements upstream.

### Added

- **`kennisbank-upgrade` skill** — upgrades a deployed vault to the latest
  official release tag: checks the upstream tag, shows the changelog, guards
  against clobbering local edits, backs up the current deploy, copies the new
  tooling, stamps `$VAULT/.claude/.kennisbank-version`, and verifies with
  `doctor.sh`.
- **`kennisbank-contribute` skill** — isolates local tooling edits in a
  deployed vault (scripts, templates, commands, skill), filters out personal
  vault content, and opens an upstream PR.
- **`qwen3-embedding:8b` as the default embedding model** (multilingual, 119
  languages) with `nomic-embed-text` as the lighter English-only fallback via
  `OLLAMA_EMBED_MODEL`.
- **Configurable tiling thresholds** `TILING_THRESHOLD_ERROR` /
  `TILING_THRESHOLD_REVIEW`, with robust NL-decimal parsing and a safe fallback
  instead of a crash on bad input.

### Fixed

- **`setup.sh` now deploys `scripts/*.sh`**, so `doctor.sh` ships with every
  install instead of relying on a manual copy.
- **`doctor.sh` respects `OLLAMA_EMBED_MODEL`** and reports the actual default
  (`qwen3-embedding:8b`) instead of hardcoding `nomic-embed-text`.

## [0.5.0] - 2026-06-14

Second review round: regression tests + CI, configurable taxonomy, an env var that points every script at the vault, a documentation-drift sweep, and a code-duplication cleanup.

### Added

- **Test suite (stdlib `unittest`, no third-party dependency).** `tests/` covers `split_frontmatter`/`parse_frontmatter` (`test_frontmatter.py`), `slugify` (`test_slugify.py`), `categorize` (`test_categorize.py`), the `categories.json` loader (`test_categories_json.py`), the zip-slip/symlink guard (`test_zip_guard.py`), `_vaultpath` resolution (`test_vaultpath.py`) and the shared `_common.py` helpers (`test_common.py`). Hyphenated scripts are loaded via `tests/_loader.py`. Run with `python3 -m unittest discover -s tests`.
- **GitHub Actions CI** (`.github/workflows/ci.yml`): on every push and pull request it compiles all scripts (`python3 -m py_compile scripts/*.py`), syntax-checks the shell (`bash -n setup.sh scripts/doctor.sh`) and runs the unittest suite. Free for public repos, pure standard library, no install step.
- **Configurable taxonomy for `build-karpathy-index.py`.** The category rules, prefix hints, generic-tag set and "Overig/Other" labels load from a `categories.json` placed next to the script or in the vault root; the built-in set is the fallback. `categories.example.json` ships the current set as a documented template so an outsider can define their own categories without editing the Python.
- **`KENNISBANK_VAULT` environment variable** via the new `scripts/_vaultpath.py` (single `vault_root()` source of truth). `stale-check.py`, `semantic-tiling.py`, `intake-scan.py` and `doctor.sh` now resolve the vault through it instead of hardcoding `~/KennisBank`, with the same default. Point the whole script layer at another vault with one variable, e.g. `KENNISBANK_VAULT=/tmp/test python3 scripts/stale-check.py`. The `--dry-run` flag was added to `auto-crosslink.py`, the last writing script that lacked an escape hatch.
- `scripts/_common.py`: shared `slugify`, `_utcnow_iso`, `_today_iso` and `print_summary` helpers for the three importers.

### Changed

- **`build-karpathy-index.py` now uses the shared `_frontmatter.py` parser** instead of its own private frontmatter parser (and the optional PyYAML path). One parser, one regex (`_frontmatter.py`'s anchored `^---\s*$`), consistent with the rest of the script layer. Index and log output are unchanged. `categorize()` is untouched.
- **De-duplicated the three importers.** `slugify`, `_utcnow_iso`/`_today_iso` and the summary/dry-run print block were defined identically in `import-folder.py`, `import-claudeai-export.py` and `import-cc-history.py`; they now import from `scripts/_common.py`. Now-unused imports (`json`, `timezone`) were dropped where the dedup left them dangling. Behaviour is identical.

### Fixed

- **Documentation-drift sweep** of the six points found in the review: `AGENTS.md` "every check line ends in OK" corrected to the `[PASS]`/`[FAIL]` format, "four new slash commands" corrected to six, the stale `THRESHOLD_DAYS` reference replaced by the actual `--days` flag; `TROUBLESHOOTING.md` dropped the removed `ollama embed` CLI path in favour of the HTTP API; `POST-INSTALL.md` "four Python utility scripts" corrected to nine; `CONFIGURATION.md` replaced the brittle `setup.sh` line-number references with variable names.
- `scripts/semantic-tiling.py`: removed the unused `import subprocess` (leftover from the CLI era) and now skips the auto-generated `log.md` (in addition to `index.md`) so generated index content is no longer fed into the near-duplicate embeddings.
- `scripts/stale-check.py`: dropped the dead second date format (`%Y-%m-%dT%H:%M:%S`, unreachable because the value is sliced to `[:10]`) and the no-op `fmt[:len(fmt)]`.

## [0.4.0] - 2026-05-14

Release after a full multi-agent code review of v0.3.0. Two CRITICAL fixes (broken `semantic-tiling.py` and a silent `doctor.sh` false-green), four HIGH fixes (`setup.sh` hardening, importer security, frontmatter parser correctness), plus a quick-wins bundle.

### Added

- `setup.sh --force` (`-f`) flag. Default behavior is now no-clobber: existing scripts, templates, commands, skill files and `CLAUDE.md` are kept and reported (`behouden:`). With `--force` they are overwritten (`gekopieerd:`), with a loud warning when an existing customised `CLAUDE.md` is replaced.
- `scripts/_frontmatter.py`: shared helper with `split_frontmatter` and `parse_frontmatter`, used by `import-folder.py`, `stale-check.py` and `semantic-tiling.py`. Anchored multiline regex avoids the previous horizontal-rule false positive.
- `commands/sessielog.md` Stap 1 now invokes `scripts/build-karpathy-index.py` so the Karpathy index in `02-wiki/log.md` is rebuilt after every sessie-log. Previously the script was installed by `setup.sh` but never called by any command.
- README now documents the four `/import` variants (`cc`, `claudeai <path>`, `folder <path>`, `cowork`) inline in the commands table.

### Changed

- `setup.sh` runs from any working directory via `SCRIPT_DIR` detection (was: required CWD to be the repo root).
- `setup.sh` enables `shopt -s nullglob` so empty source globs no longer fail under `set -e`.
- Importer filenames in `import-cc-history.py` and `import-claudeai-export.py` now include an 8-character stable-id suffix (derived from `session_id`/`uuid`, with `sha1` fallback). Same-day same-title sessions no longer overwrite each other silently. **Migration note**: re-running an import after upgrade produces new filenames; old files from earlier runs remain in `01-raw/sessies/` and may need manual cleanup or a one-time rename.
- `commands/import.md` removed a dead reference to a non-existent `/sessielog --force` flag.
- `templates/tpl-wiki-artikel.md` default status is now `concept` (was `actief`), matching the "bij twijfel: status concept" rule in `commands/wiki.md`.
- `scripts/build-karpathy-index.py` emits `## [YYYY-MM-DD] OPERATION | Title` (was `SESSION`), aligning the script with README, `POST-INSTALL.md`, `CHANGELOG.md` and the module docstring.

### Fixed

- **CRITICAL** `scripts/doctor.sh` now verifies all six installed commands (`sessielog`, `wiki`, `intake`, `stale`, `sessiestart`, `import`). Previous versions checked only four and silently reported PASS when `sessiestart` or `import` failed to install. Doctor's PASS count grows from 32 to 34.
- **CRITICAL** `scripts/semantic-tiling.py` uses the Ollama HTTP API (`POST http://localhost:11434/api/embeddings`) instead of the removed `ollama embed` CLI subcommand. The previous implementation always returned `None` on current Ollama releases, producing zero near-duplicate matches without any error.
- **HIGH** `scripts/import-claudeai-export.py` validates every zip member before `extractall`. Absolute paths, `..` traversals and symlink-typed entries (`S_IFLNK`) are rejected; a malicious zip yields a clean `[error]` line on stderr with exit code 2 instead of a Python traceback.
- **HIGH** Frontmatter parsers in three scripts no longer truncate body content at a `---` horizontal rule. Anchored regex `^---\s*$` (multiline) replaces the previous `text.find("\n---", 3)` pattern.
- **HIGH** `scripts/intake-scan.py` boolean was `or` where `and` was intended in `detect_type`. Binary files (`.exe`, `.zip`, etc.) no longer fall through to `read_text` attempts.
- `AGENTS.md`, `POST-INSTALL.md`, `CONFIGURATION.md` docs-sync: "four global slash commands" updated to "six"; obsolete "once `--yes` is merged" qualifier dropped (already merged in 0.2.0); a stale `THRESHOLD_DAYS` discrepancy callout removed from `CONFIGURATION.md`.
- `POST-INSTALL.md` em dashes converted to hyphens (project style: no em dashes).
- `.gitignore` covers `graphify-out/`, `.venv/`, `.idea/`, `.vscode/`, `*.egg-info/`.

### Background

This release packages ten commits from a single review-and-fix pass driven by a multi-agent code review pipeline. The doctor false-green and the broken `semantic-tiling.py` are the two findings users were most likely to hit silently on a fresh install. The importer security fix protects against malicious zip exports (low real-world risk for trusted exports, but the script accepts arbitrary `--input`). The frontmatter parser unification eliminates a class of silent body-truncation bugs that would only show up on long-form wiki articles containing horizontal rules.

## [0.3.0] — 2026-05-09

### Added

- `scripts/build-karpathy-index.py` builds `02-wiki/index.md` and `02-wiki/log.md` in the format that Understand-Anything's `parse-knowledge-base.py` requires (`## Section` headings + `[[wikilink]]` rows for index, `## [YYYY-MM-DD] OPERATION | Title` rows for log). It scans `02-wiki/` frontmatter (using PyYAML when available, with a minimal fallback parser) and clusters articles into 5–12 categories via, in priority order: a `category` frontmatter field, the first non-generic tag, or the `wiki-<domain>-...` filename prefix. `wiki-memory` types are pinned to a trailing `Memory-snapshots` section. Log entries come from `01-raw/sessies/raw-sessie-YYYY-MM-DD-*.md` filenames, with titles read from frontmatter when present. Flags: `--dry-run`, `--force` (writes `.bak` before overwrite), `--vault-root`, `--wiki-dir`, `--sessies-dir`. Refuses to overwrite without `--force`; honours dry-run.
- README and POST-INSTALL document the optional `/understand-knowledge` (Understand-Anything plugin) workflow as Step 8: install plugin, build index, run skill, browse dashboard. Existing graphify integration stays unchanged; the two are complementary (graphify uses semantic embeddings + hyperedges, Understand-Anything uses wikilinks + per-batch LLM analysis with categorised layers and a guided tour).

### Changed

- `POST-INSTALL.md` step numbering shifted: graphify stays at Step 7, the new knowledge-graph dashboard step is Step 8, autoresearch is Step 9, backfill is Step 10.

### Background

The integration grew out of a hands-on test of Understand-Anything against a real KennisBank vault. The detector requires `index.md` and `log.md` and does not generate them itself; `/wiki` does not write a centralised index either. `build-karpathy-index.py` closes that gap so users do not run into the same `Not a Karpathy-pattern wiki` error during their first `/understand-knowledge` invocation.

## [0.2.0] — 2026-05-08

### Added

- `AGENTS.md`, `TROUBLESHOOTING.md`, `POST-INSTALL.md`, `CONFIGURATION.md`, `OBSIDIAN.md` — install, troubleshooting, post-install walkthrough, configuration reference, Obsidian setup.
- `scripts/doctor.sh` — 12-check health verifier for vault, scripts, templates, commands, skill installation.
- `commands/import.md` (`/import` slash command) plus three importers: `scripts/import-cc-history.py`, `scripts/import-claudeai-export.py`, `scripts/import-folder.py` (with `--list-cowork-candidates`).
- `commands/sessiestart.md` (`/sessiestart` slash command) — briefing flow at session start.
- `setup.sh` flags: `--yes`, `--no-commands`, `--no-skill`, `--help` for non-interactive install.

### Fixed

- Documentation discrepancies surfaced by the publish-check: `THRESHOLD_DAYS` removed (never existed), `MIN_CONFIDENCE` and `MAX_NEW_LINKS` documented, `LEARNINGS_FILE` clarified as a convention not a config, doctor's Python warning relaxed, README numbering repaired.

## [0.1.0] — 2026-04-26

### Added

- Initial release. Core slash commands (`/sessielog`, `/wiki`, `/intake`, `/stale`), four utility scripts (`auto-crosslink.py`, `intake-scan.py`, `semantic-tiling.py`, `stale-check.py`), session-log and wiki-article templates, vault scaffolding via `setup.sh`, `/autoresearch` skill, `CLAUDE.md.template`.

[Unreleased]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.34.0...HEAD
[0.34.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.33.0...v0.34.0
[0.33.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.32.0...v0.33.0
[0.32.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.31.1...v0.32.0
[0.31.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.31.0...v0.31.1
[0.31.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.30.0...v0.31.0
[0.30.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.29.0...v0.30.0
[0.29.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.28.0...v0.29.0
[0.28.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.27.0...v0.28.0
[0.27.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.26.1...v0.27.0
[0.26.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.26.0...v0.26.1
[0.26.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.25.0...v0.26.0
[0.25.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.24.1...v0.25.0
[0.24.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.24.0...v0.24.1
[0.24.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.23.0...v0.24.0
[0.23.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.22.0...v0.23.0
[0.22.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.21.0...v0.22.0
[0.21.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.20.0...v0.21.0
[0.20.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.19.0...v0.20.0
[0.19.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.18.1...v0.19.0
[0.18.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.18.0...v0.18.1
[0.18.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.17.1...v0.18.0
[0.17.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.17.0...v0.17.1
[0.17.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.16.3...v0.17.0
[0.16.3]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.16.2...v0.16.3
[0.16.2]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.16.1...v0.16.2
[0.16.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.16.0...v0.16.1
[0.16.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.12.2...v0.13.0
[0.12.2]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.12.1...v0.12.2
[0.12.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.8.2...v0.9.0
[0.8.2]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.6.1
[0.6.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.6.0
[0.5.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.5.0
[0.4.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.4.0
[0.3.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.3.0
[0.2.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.2.0
[0.1.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.1.0

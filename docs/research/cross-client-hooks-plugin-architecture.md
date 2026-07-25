# KennisBank across coding-agent environments

Status: research and implementation direction  
Date: 2026-07-19  
Scope: KennisBank retrieval, capture, session durability, wiki publication,
plugin packaging, installation, updates, and diagnostics

## Executive conclusion

KennisBank should remain one local knowledge engine with thin adapters for
coding-agent clients. It should not become a collection of client-specific
memory implementations. Skills, commands, hook manifests, configuration paths,
and native event envelopes differ by client; retrieval, redaction, transcript
normalization, indexing, distillation, provenance, and wiki behavior remain
canonical.

The correct lifecycle is not “do all knowledge work at SessionStart and Stop.”
KennisBank needs three execution temperatures:

- **Hot path:** synchronous cached context reads and append-only watermarks.
- **Warm path:** prompt-specific local retrieval over prebuilt lexical and
  semantic indexes.
- **Cold path:** queued transcript normalization, extraction, independent
  judgment, deduplication, reconciliation, and wiki proposals.

SessionStart must stay fast. It should validate the explicit vault, recover
unfinished session state, and inject a small prepared project handoff. The
first task prompt is the best relevance signal, so UserPromptSubmit should run
the bounded memory query and then search the linked wiki neighborhood.
SubagentStart should reuse the parent turn’s already prepared context instead
of starting another embedding or model call.

PreCompact, Stop, SubagentStop, Interrupt, and SessionEnd are durability
boundaries. They should write an idempotent watermark or queue record, never
run distillation or mutate a wiki article synchronously. A hard kill cannot
invoke any hook; durable recovery therefore depends on write-ahead checkpoints
and a next-start recovery scan.

## Product boundaries

This report belongs to KennisBank. It does not define ADR Kit packaging,
decision enforcement, ADR instruction files, or ADR lifecycle behavior.

The shared research is still useful because both products integrate with the
same client plugin systems. Shared knowledge about native manifests, hook
envelopes, installation paths, trust, updates, and doctor probes may be reused
as implementation technique. Runtime behavior and product data stay separate:

```text
client event
  -> KennisBank client adapter
  -> KennisBank normalized lifecycle protocol
  -> KennisBank vault, indexes, queue, and workers
```

On this machine every hook, skill, MCP server, command, setup action, and doctor
probe must preserve:

```text
KENNISBANK_VAULT=D:/Users/Robert/Documents/Claude/Projects/Kluis
```

Missing Ollama, embeddings, a transcript, or an adapter script must fail open.
KennisBank may omit context; it must not prevent the coding agent from working.

## Admission rule

A client is eligible for first-class KennisBank support only when setup and
doctor can verify:

1. a reusable skill or equivalent on-demand instruction surface;
2. a user-invocable command, prompt, workflow, or skill;
3. persistent project or global guidance;
4. model-visible session or prompt context injection;
5. pre/post tool events or an equivalent evidence surface;
6. a local MCP or in-process tool bridge;
7. enough lifecycle coverage to durably capture turns, subagent work, and
   compaction, or a documented write-ahead/recovery equivalent;
8. versioned install, update, disable, and uninstall behavior;
9. inspectable state for `doctor.sh` and `agent-status.py`; and
10. supported Windows behavior plus testable macOS/Linux behavior.

For community/open-source clients, use 2,000 GitHub stars, recent maintenance,
and a credible security/update story as an adoption gate. Closed-source clients
must instead have material ecosystem impact and a complete official contract.
Popularity never compensates for missing lifecycle or privacy controls.

## Normalized lifecycle protocol

Each adapter should translate native payloads into a small stable envelope:

```text
schema_version
client, client_version, event
session_id, turn_id, agent_id, parent_agent_id
workspace, cwd
transcript_path, transcript_offset, transcript_size, transcript_hash
timestamp, trigger, stop_reason
tool_name, file_paths
redaction_profile, vault_id
```

Only fields required by the event are mandatory. Unknown native fields are
ignored unless the adapter archives the opaque source payload under a versioned
format. Native transcript formats are not stable APIs.

Recommended normalized events:

```text
session.start
prompt.submit
tool.before
tool.after
tool.failure
agent.start
agent.stop
compact.before
compact.after
turn.stop
session.interrupt
session.end
```

Every event handler must be idempotent. Prefer keys based on:

```text
(client, session_id, event, turn_id, agent_id, transcript_offset, content_hash)
```

## Recommended latency budgets

These are KennisBank design targets, not vendor guarantees:

| Path | p50 target | p95 target | Hard timeout | On timeout |
|---|---:|---:|---:|---|
| SessionStart | 50 ms | 150 ms | 500 ms | inject cached minimum or nothing |
| UserPromptSubmit quick recall | 75 ms | 250 ms | 500 ms | lexical results only |
| SubagentStart | 30 ms | 100 ms | 250 ms | parent retrieval bundle only |
| PreToolUse / PostToolUse signal | 10 ms | 25 ms | 100 ms | no-op |
| PreCompact checkpoint | 30 ms | 100 ms | 500 ms | defer to recovery scan |
| Stop / SubagentStop checkpoint | 50 ms | 200 ms | 750 ms | defer to recovery scan |
| SessionEnd archive | 100 ms | 500 ms | 1 s | recover next start |

Local prompt embeddings have previously taken roughly 2.1–2.5 seconds on the
active machine. That is too slow for an unconditional interactive hook. The
prompt path should:

1. query the local prebuilt FTS, recency, project, and entity indexes;
2. immediately form a small memory shortlist;
3. use a cached query embedding when available;
4. attempt a bounded semantic rerank only when the embedding service is warm
   and the remaining deadline permits it; and
5. search only the shortlist’s linked wiki neighborhood.

No hook should start Ollama, download a model, rebuild an index, sweep memory,
or wait for a cold model load.

## Hook-by-hook evaluation

### SessionStart

Use SessionStart for:

- validating the explicit vault path and read-only index availability;
- loading a cached project handoff and recent-session pointer;
- recovery-scanning unfinished journal records;
- injecting the small KennisBank operating contract; and
- loading a prepared context bundle on resume.

Do not embed, sweep, distill, rebuild, or publish. A new session often has no
task prompt, so broad relevance retrieval here wastes latency and context.

KennisBank value: **5/5 for bootstrap, 2/5 for relevance**.

### UserPromptSubmit / beforeSubmitPrompt / chat.message

This is the primary relevance hook. The task text is available, so KennisBank
can filter trivial prompts, run the fast local query, apply privacy rules, and
inject the bounded result. Cache the selected memories and wiki references
under the session and turn so later subagents reuse them.

KennisBank value: **5/5**.

### SubagentStart / task delegation

Subagents commonly have isolated context. Inject:

- the parent turn’s task and selected memory bundle;
- the exact delegated scope;
- a few relevant memory summaries;
- pointers to source wiki articles and raw provenance; and
- any explicit contradictions or uncertainty markers.

Do not run a second general search merely because a subagent started. If the
subagent receives a materially different task prompt, a bounded task-specific
rerank is acceptable.

KennisBank value: **5/5 when native, 3/5 through a task-tool adapter**.

### PreCompact

PreCompact occurs before lossy context reduction. Record:

- the transcript identity and current byte/record offset;
- the source hash and observed format version;
- pending capture identifiers;
- the current retrieval bundle identifier; and
- an atomic compact watermark.

Copy only the known delta. Never block compaction to finish extraction or wiki
work. If the native transcript can lag asynchronous writes, the next hook or
SessionStart recovery scan completes the range.

KennisBank value: **4/5 for durability, 1/5 for publication**.

### PostCompact

When the client exposes the generated compact summary, store it as an
additional lossy candidate summary. It never replaces the raw transcript.
When the payload contains only an event marker, no action is required beyond
updating the compact watermark.

KennisBank value: **3/5 with a summary, 1/5 without one**.

### Stop / agentStop / session.idle

Stop is usually a turn boundary, not a guaranteed session end. It may fire
repeatedly, especially when a hook can force continuation. Use it to:

- append the transcript delta or latest watermark;
- record which injected items were visible;
- enqueue candidate insights;
- record lightweight usage signals; and
- mark the turn complete idempotently.

Never force another turn to complete housekeeping.

KennisBank value: **4/5 for checkpointing, 2/5 for finalization**.

### SubagentStop

Capture delegated findings before they collapse into a short parent-facing
answer:

- delegated scope;
- evidence and source paths;
- decisions, contradictions, and unresolved questions;
- files touched;
- the last agent message; and
- parent session/turn linkage.

Queue this as session insight material. Do not let the capture hook decide that
the subagent must continue.

KennisBank value: **4/5**.

### SessionEnd

SessionEnd is the best graceful raw archive boundary. The handler should only
write the final watermark, atomically preserve a transcript reference or
delta, and enqueue normalization. Vendor exit budgets are short and may be
shared by multiple hooks.

KennisBank value: **5/5 for archive, 1/5 for synchronous distillation**.

### PreToolUse

General memory retrieval before every tool would be slow and noisy. Restrict
KennisBank use to:

- cached rules relevant to a target file;
- a pre-search hint before selected web/search tools;
- redaction or data-boundary warnings; and
- tool-specific memory explicitly selected at prompt time.

KennisBank hooks must never deny a tool call. In clients where a crashing
PreToolUse handler fails closed, the wrapper must catch every internal error
and return the native allow/empty result.

KennisBank value: **2/5 generally, 4/5 for carefully selected tools**.

### PostToolUse and failures

Filter aggressively. Record evidence pointers such as changed files, test
failures, or search result identifiers. Do not copy or summarize every tool
result synchronously. Debounce repeated file signals.

KennisBank value: **3/5**.

### Interrupt, StopFailure, errors, and retry

Write an unfinished-session marker and flush only already prepared journal
state. Retry and model-call hooks should not duplicate full prompts and
responses already present in transcripts.

KennisBank value: **4/5 for recovery markers**.

### Permission and notification events

Permission hooks are not knowledge boundaries and must never make authorization
decisions for KennisBank. Notifications can trigger optional non-blocking idle
work, but are not portable enough to anchor the architecture.

KennisBank value: **1/5**.

## Hard exits

No in-process hook runs reliably after an operating-system kill, crash, power
loss, or destroyed terminal. “Capture on hard exit” therefore means:

1. write ahead at prompt submission and every completed turn;
2. checkpoint selected tool and compaction boundaries;
3. store offsets and hashes atomically under the vault-owned spool;
4. preserve immutable raw transcript fragments or stable source references;
5. omit the final marker until graceful finalization succeeds;
6. scan unfinished records at the next SessionStart; and
7. replay idempotently.

A permanent watcher is not required. It can be offered as an explicit advanced
option when lower recovery latency justifies the privacy and resource cost.

## Capture, distillation, and wiki publication

Raw capture and knowledge publication are different operations:

- Capture is objective, append-only, redacted, source-preserving, and
  idempotent.
- Distillation is interpretive and model-bearing.
- Memory promotion requires independent judgment and deduplication.
- Wiki publication can conflict with existing articles and may need review.

The cold worker should:

1. normalize archived session ranges;
2. extract candidate facts, decisions, preferences, and lessons;
3. retain raw-session and agent provenance;
4. run the independent judge;
5. deduplicate and reconcile against accepted memory;
6. search the relevant wiki neighborhood;
7. classify each proposal as no-op, append, reconcile, supersede, or new
   article; and
8. publish atomically or queue review according to policy.

Synchronous hooks enqueue work. They never rewrite wiki articles.

## Client assessment

Legend: Y = native; A = adapter; D = documented degradation; N = absent or not
documented.

| Client | Prompt context | Tool events | Subagents | Compact | Stop/end | Plugin/update | KennisBank status |
|---|---:|---:|---:|---:|---:|---:|---|
| Claude Code | Y | Y | Y | Y | Y | Y | supported reference |
| Codex | Y | Y | Y | Y | D no SessionEnd | Y | supported with recovery |
| Copilot CLI | Y | Y | Y | Y | Y | Y | supported opt-in |
| OpenCode | A | Y | D task-tool | A experimental | A idle/status | Y | supported composite adapter |
| Kimi Code | Y | Y | Y | Y | Y plus Interrupt | Y | highest-priority expansion |
| Kilo Code | Y `chat.message` | Y | A event/task | A experimental | A event/idle | Y | high-priority expansion |
| Qwen Code | Y | Y | Y | Y | Y | Y | high-priority candidate |
| Gemini CLI | Y | Y | Y | Y | Y | Y | candidate/transition |
| Cursor IDE/local | Y | Y | Y | Y | Y | Y | candidate |
| VS Code Agent Plugins | Y | Y | Y | Y | D | Y preview | candidate |
| OMP | A | Y | A | Y | A | Y | candidate |
| Pi | A | Y | extension-owned | Y | A | Y | candidate |
| Hermes | A pre-model | Y | Y | context-engine bridge | Y | Y | contract test |
| goose | Y | Y | N hooks | N | Y | Y | partial lifecycle |
| Kiro CLI | Y | Y | N hooks | N | Stop only | Y | partial lifecycle |
| Antigravity | D PreInvocation | Y | N | N | Stop only | ? | partial lifecycle |
| Warp | N hooks | N hooks | N hooks | N hooks | N hooks | N user plugin | skills/MCP only |
| Crush | N | D pre only | N | N | N | preliminary | insufficient |

### Kimi Code

[Kimi Code](https://www.kimi.com/code/docs/en/) is the closest native match.
Its plugin manager installs local directories, archives, GitHub repositories,
and marketplace packages. Plugins can bundle skills, slash commands, MCP,
session instructions, and hooks. Its
[hook contract](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/hooks.html)
includes SessionStart/End, UserPromptSubmit, Pre/PostToolUse, failures,
PermissionRequest/Result, Stop/StopFailure, Interrupt,
SubagentStart/SubagentStop, and PreCompact/PostCompact. Hook errors fail open.

Kimi should be the reference implementation for the complete normalized
KennisBank lifecycle. Setup must detect the legacy Kimi CLI layout and migrate
or remove it without leaving duplicate hooks or MCP registrations.

### Kilo Code

[Kilo Code](https://github.com/kilo-org/kilocode) passes the adoption and
maintenance gates. Its
[plugin API](https://kilo.ai/docs/automate/extending/plugins) works in both CLI
and VS Code and provides:

- `chat.message`, command, pre/post-tool, configuration, and event-bus hooks;
- session created/updated/idle/error/compacted/status events;
- message, permission, file, shell, installation, and LSP events;
- experimental pre-compaction context injection;
- npm-versioned or local plugins with deterministic load order;
- portable [Agent Skills](https://kilo.ai/docs/customize/skills);
- Markdown [slash workflows](https://kilo.ai/docs/customize/workflows);
- `AGENTS.md`, custom instructions, MCP, custom agents, and subagents; and
- `kilo plugin`, `kilo upgrade`, `kilo uninstall`, `/reload`, export/import,
  and cross-platform binaries.

Kilo is a high-priority first-class target after native certification. The
adapter can share TypeScript event translation with OpenCode, but Kilo needs
its own paths, version probes, fixtures, and doctor checks. Doctor must report
`KILO_PURE=1`, because that setting suppresses external plugins.

Kilo’s experimental compaction hook can inject prepared context, while
`session.compacted` confirms the event afterward. Subagent work may need
correlation through task tools and event metadata rather than a dedicated
SubagentStart/SubagentStop pair. That is acceptable only after a fixture proves
parent/child attribution and raw-session completeness.

### Warp

Warp has high adoption and supports skills, project rules, slash commands, and
MCP. Its official documentation does not expose an end-user lifecycle-hook
contract. MCP cannot observe prompt, tool, subagent, compaction, Stop, or
session-end boundaries.

Warp can receive portable KennisBank skills, instructions, commands, and MCP,
but not full automatic capture. It must be labelled compatibility-only.

## Plugin architecture

Keep the current local Python engine and generate thin client payloads:

```text
adapters/
  capabilities.json
  claude/
  codex/
  copilot/
  opencode/
  kimi/
  kilo/
  qwen/
  gemini/
  cursor/
  vscode/
  omp/
  pi/
scripts/
  kb-hook.py
  install-agent-envs.py
  doctor.sh
  agent-status.py
commands/                  canonical workflows
skills/                    canonical Agent Skills
templates/                 managed instruction/config fragments
```

`capabilities.json` should record:

- native event names and required input/output fields;
- whether context injection is model-visible;
- failure semantics and explicit allow/empty results;
- plugin, skill, command, instruction, MCP, and transcript paths;
- native install/list/update/remove commands;
- client/version feature gates;
- remote/cloud data-boundary constraints; and
- doctor probes and known degradations.

TypeScript adapters contain no retrieval or capture policy. They validate the
native payload, call the bounded Python hook core, and translate the response.

## Installer, updates, and migration

`setup.sh` remains the supported entrypoint and should delegate client desired
state to `scripts/install-agent-envs.py`.

Detection must be read-only and collect:

- executable path and version;
- config/home overrides;
- installed KennisBank plugin and payload version;
- legacy layouts and duplicate files;
- hook enabled/trusted/suppressed state;
- MCP registration and resolved command;
- selected vault path embedded in every installed launcher;
- client cloud/remote mode; and
- supported, experimental, partial, or unsupported classification.

For each selected client:

1. validate source artifacts and versions;
2. resolve the explicit vault;
3. prepare one immutable platform-local payload;
4. acquire a per-client lock;
5. inspect previous and legacy installs;
6. no-op when hashes, version, vault, hooks, MCP, skills, and commands match;
7. use the native plugin API where available;
8. patch only KennisBank-owned keys or marker blocks;
9. validate hook fixtures and MCP handshake;
10. retain the previous healthy version for rollback; and
11. remove only KennisBank-owned stale artifacts after success.

Recommended update policy:

- automatically apply verified stable patch/minor updates;
- require confirmation for incompatible migrations;
- run doctor before switching the active payload;
- roll back when hook smoke or MCP initialization fails;
- preserve offline and pinned modes; and
- never mutate the source checkout with machine-local paths.

## Doctor requirements

Common checks:

- explicit vault resolution and writable/readable owned paths;
- Python, scripts, indexes, queue, and schema versions;
- Ollama/embedding availability as advisory unless explicitly required;
- canonical adapter and installed payload hashes;
- duplicate/stale plugin roots;
- MCP initialize/list-tools/call smoke;
- hook fixture input/output, fail-open behavior, and latency;
- instruction marker integrity;
- raw spool permissions, redaction policy, and retention;
- unfinished session recovery candidates; and
- background queue and cold-worker health.

Client checks:

- executable and version;
- plugin listed, loaded, trusted, and not suppressed;
- skill and command discovery;
- MCP resolved to the current vault and payload;
- required lifecycle events active;
- transcript/session source readable where applicable;
- native update source valid;
- disabled, stale, partial, or unsupported state reported plainly; and
- remote/cloud mode never receives local vault data without explicit consent.

Machine-readable doctor output should identify every client independently so
one broken adapter does not hide healthy clients.

## Phased plan

### Phase 0: architecture decision

Record the normalized lifecycle protocol, hot/warm/cold boundaries, privacy
model, support admission rule, and TypeScript-adapter exception in a KennisBank
ADR. Keep the explicit vault and local-first decisions authoritative.

### Phase 1: normalize current clients

Move Claude, Codex, OpenCode, and Copilot hook parsing behind `kb-hook.py`.
Create versioned fixtures for every currently installed event and preserve the
existing fail-open behavior.

Acceptance:

- identical retrieval and capture outcomes across equivalent events;
- explicit vault in every generated command;
- no hook denial on internal error;
- duplicate/repeated events are idempotent; and
- existing setup/doctor/e2e tests stay green.

### Phase 2: performance and durability

Implement the bounded prompt path, parent-turn bundle cache, append-only
watermarks, compaction checkpoints, and next-start recovery scan.

Acceptance:

- latency budgets pass on warm and degraded local backends;
- no network or model startup on the hot path;
- hard-kill fixture recovers exactly the missing range;
- repeated recovery produces no duplicate raw records; and
- progress is visible for cold work.

### Phase 3: Kimi Code

Build the reference full-lifecycle Kimi plugin with skills, commands, MCP,
instructions, hooks, native update, legacy migration, and doctor.

### Phase 4: Kilo Code

Build the shared OpenCode/Kilo TypeScript bridge and Kilo-native payload. Test
CLI and VS Code independently, including `KILO_PURE=1`, npm pinned versions,
local plugin directories, `/reload`, update, uninstall, and session export.

### Phase 5: Qwen/Gemini and OpenPlugin families

Generate Qwen/Gemini and Cursor/VS Code payloads from shared canonical source.
Keep client-specific fixtures and privacy boundaries.

### Phase 6: contract-test candidates

Prototype OMP, Pi, Hermes, goose, Kiro, and Antigravity. Do not advertise
support until native install, prompt injection, tool capture, session
durability, update, rollback, and doctor tests all pass.

## Decisions requiring user policy

Most deterministic behavior can default on for detected supported clients.
These controls require an explicit policy:

1. raw transcript retention duration and size limits;
2. automatic wiki publication versus review queue;
3. cost-bearing local/cloud model use;
4. stable auto-update, notify-before-update, or pinned/offline mode;
5. background watcher/worker enablement;
6. cloud/remote client access to the local vault; and
7. per-client capture and redaction scope.

Recommended defaults:

- enable fail-open hooks, skills, commands, MCP, and managed instructions;
- keep all retrieval and capture local;
- retain redacted raw sessions under the configured policy;
- queue wiki proposals for review;
- keep cloud model use off;
- apply verified stable updates with rollback;
- use next-start recovery instead of a permanent watcher; and
- never expose the vault to remote agents without explicit consent.

## Primary sources

- [Codex hooks](https://learn.chatgpt.com/docs/hooks)
- [Claude hooks](https://code.claude.com/docs/en/hooks)
- [Claude plugins](https://code.claude.com/docs/en/plugins)
- [Copilot CLI hooks](https://docs.github.com/en/copilot/reference/hooks-reference)
- [Copilot plugin creation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-creating)
- [OpenCode plugins](https://opencode.ai/docs/plugins/)
- [Kimi Code documentation](https://www.kimi.com/code/docs/en/)
- [Kimi Code plugins](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/plugins.html)
- [Kimi Code hooks](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/hooks.html)
- [Kilo Code source](https://github.com/kilo-org/kilocode)
- [Kilo Code plugins](https://kilo.ai/docs/automate/extending/plugins)
- [Kilo Code skills](https://kilo.ai/docs/customize/skills)
- [Kilo Code workflows](https://kilo.ai/docs/customize/workflows)
- [Kilo Code CLI](https://kilo.ai/docs/code-with-ai/platforms/cli)
- [Qwen Code extensions](https://qwenlm.github.io/qwen-code-docs/en/users/extension/introduction/)
- [Qwen Code hooks](https://qwenlm.github.io/qwen-code-docs/en/users/features/hooks/)
- [Gemini CLI extensions](https://geminicli.com/docs/extensions/reference/)
- [Cursor plugins](https://cursor.com/docs/reference/plugins)
- [Cursor hooks](https://cursor.com/docs/hooks)
- [VS Code Agent Plugins](https://code.visualstudio.com/docs/agent-customization/agent-plugins)
- [VS Code hooks](https://code.visualstudio.com/docs/agent-customization/hooks)
- [OMP](https://github.com/can1357/oh-my-pi)
- [Pi](https://pi.dev/)
- [Hermes plugins](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins)
- [goose hooks](https://goose-docs.ai/docs/guides/context-engineering/hooks/)
- [Kiro CLI hooks](https://kiro.dev/docs/cli/hooks/)
- [Antigravity plugins](https://antigravity.google/docs/plugins)
- [Antigravity hooks](https://antigravity.google/docs/hooks)
- [Warp source](https://github.com/warpdotdev/Warp)

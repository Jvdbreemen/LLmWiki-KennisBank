# ADR-0003: GitHub Copilot CLI as a local-first KennisBank agent integration

- **Status**: Accepted
- **Date**: 2026-07-11
- **Deciders**: Robert van den Breemen
- **Epic**: TASK-26 (child task TASK-26.1)

## Context

KennisBank already treats Claude Code, Codex, and OpenCode as first-class local
agent environments: each points at the same vault and the same stdio MCP server
(`<vault>/.claude/scripts/kb-mcp.py`), receives the KennisBank skills, an
`AGENTS.md` managed block, lifecycle hooks, and feeds rawlog/activity capture
(see `docs/agent-integrations.md`, `scripts/install-agent-envs.py`). TASK-26 adds
**GitHub Copilot CLI** — the standalone `@github/copilot` terminal agent — as a
fourth environment, without regressing the other three and without taking on a
cloud-memory or Headroom runtime dependency.

This ADR is the contract every child task of TASK-26 references. All surface
facts below were **verified against the real CLI** (`copilot` v1.0.70, win32-x64,
probed on the maintainer's machine 2026-07-11) and cross-checked against the
current GitHub Copilot CLI documentation and the Headroom source
(`headroomlabs-ai/headroom`, read via the GitHub API + raw file fetches). Where
the docs and the installed binary agreed, the fact is treated as solid; where
only the docs state something (e.g. Windows path resolution, agent frontmatter
schema) it is flagged as **doc-only, verify-before-hardcode**.

### The two Copilot CLIs — we target the standalone one

"GitHub Copilot CLI" is ambiguous. There is the older `gh copilot` gh-extension
and the newer **standalone** terminal agent installed as `npm i -g @github/copilot`
and invoked as `copilot`. Every surface this epic uses (`copilot mcp add`,
`~/.copilot/mcp-config.json`, hooks under `~/.copilot/hooks/`, custom agents,
`COPILOT_CUSTOM_INSTRUCTIONS_DIRS`) belongs to the **standalone** CLI. The
gh-extension is out of scope.

### Verified Copilot CLI surface (v1.0.70)

**Config home.** `~/.copilot` (Windows: `%USERPROFILE%\.copilot`). The
`COPILOT_HOME` environment variable overrides it. Verified: running
`copilot mcp add` under a temporary `COPILOT_HOME` wrote **only** the expected
file there and never touched the real home. `COPILOT_HOME` is therefore the key
to hermetic tests for MCP, hooks, agents, and instructions.

**Skills — already discoverable.** `copilot skill` discovers skills from, among
others, `~/.agents/skills/` and `~/.claude/skills/`. KennisBank already installs
its shared skills into `~/.agents/skills/` for Codex/OpenCode, so Copilot picks
them up with **no new install step**. `copilot skill add|list|remove` exist.

**Local model provider (BYOK).** `COPILOT_PROVIDER_TYPE=openai` +
`COPILOT_PROVIDER_BASE_URL=<endpoint>` targets any OpenAI-compatible endpoint
"including Ollama", and `COPILOT_OFFLINE=true` disables all network access
(requires a local provider). This aligns with KennisBank's "Lokaal, altijd"
principle, but it is **out of scope for this epic** — we integrate KennisBank
retrieval; we do not reroute Copilot's model traffic (that is exactly the
Headroom pattern we reject below). It is documented here only as future headroom.

**Built-in memory.** Copilot has its own `memory` setting (cross-session fact
recall, default on). This is a *different layer* from KennisBank recall; they
coexist without conflict. Noted so the ADR does not silently assume KennisBank
is Copilot's only memory.

## Decision

**Add Copilot as a fourth agent in the existing cross-agent layer, mirroring the
Codex/OpenCode integration, local-first, with no Headroom runtime dependency and
no forced GitHub login.** Concretely:

### D1 — MCP registration (TASK-26.5): idempotent JSON merge

Write `mcpServers.kennisbank` into `~/.copilot/mcp-config.json` (respecting
`COPILOT_HOME`) via a key-scoped read-modify-write, exactly as
`_ensure_opencode_config` does for `opencode.json`. Do **not** shell out to
`copilot mcp add` for the mutation: direct JSON merge is login-free, fully
idempotent, and drift-proof. `copilot mcp list`/`get` (login-free) are used by
doctor to prove Copilot *sees* the server.

Verified schema (top-level `mcpServers`, Claude-Desktop style; `type: "local"`
for stdio; no `${VAR}` interpolation — literal env values):

```json
{
  "mcpServers": {
    "kennisbank": {
      "type": "local",
      "command": "py",
      "args": ["-3", "<vault>/.claude/scripts/kb-mcp.py"],
      "env": {
        "KENNISBANK_VAULT": "<vault>",
        "KB_LLM_PROVIDERS": "ollama",
        "KB_LLM_MODEL": "gemma4:12b",
        "KB_LLM_ENDPOINT": "http://localhost:11434"
      },
      "tools": ["*"]
    }
  }
}
```

`command`/`args` follow the existing `_mcp_server_argv` (Windows `py -3`, POSIX
`python3`). Runtime validity is already proven by
`install-agent-envs.validate_mcp_runtime` (a real initialize + list-tools
handshake against `kb-mcp.py`), which is login-independent and reused unchanged.

### D2 — Instructions & custom agent profile (TASK-26.4)

- **AGENTS.md**: Copilot reads `AGENTS.md` (repo root, cwd, or any dir in
  `COPILOT_CUSTOM_INSTRUCTIONS_DIRS`). The existing `_agent_block()` managed
  block already works for Copilot — no Copilot-only assumptions that would break
  Claude/Codex/OpenCode. Install a `Client: Copilot` managed block in the
  Copilot AGENTS.md surface the same way Codex/OpenCode get theirs.
- **Global personal instructions**: write a KennisBank managed block into
  `~/.copilot/copilot-instructions.md` (marker-delimited, never clobbering user
  content).
- **Custom agent profile**: `~/.copilot/agents/kennisbank.agent.md`. The file
  extension **must** be `.agent.md` (doc-verified; a plain `.md` is silently
  ignored). Home-dir agents win over repo `.github/agents/` on name collision.
  Selected with `copilot --agent kennisbank`. The only doc-confirmed frontmatter
  field is optional `tools`; `name`/`description`/`model` are **not** documented,
  so the profile body carries vault path, MCP tool names, temporal recall
  commands, and fail-open behavior in Markdown prose rather than relying on
  undocumented frontmatter.
- Repo-local `.github/copilot-instructions.md` is left to the user / `copilot
  init`; KennisBank does not overwrite it (the adapters/registry.json
  `copilot-instructions` entry stays a documented push-inject opt-in, not an
  auto-clobber).

Instructions **combine** (no hard override) and conflict resolution is
non-deterministic, so KennisBank content is authored to *add* guidance, never to
fight a user's existing instructions.

### D3 — Hooks (TASK-26.6): native Copilot hooks, fail-open

> **Refined by ADR-006 (2026-07-19).** The native hook and fail-open decision
> remains accepted, but the independent `sessionStart` fan-out is replaced by
> one coordinator. Prompt/tool/session-end capture hooks remain separate.

Copilot CLI **does** support hooks (shipped v1.0.21, hardened in the installed
v1.0.70). They are configured by JSON files, not a subcommand — which is why
`copilot --help` shows no `hooks` command. Install a KennisBank-managed
`~/.copilot/hooks/kennisbank.json` (respecting `COPILOT_HOME`; repo-local
`.github/hooks/` is available but user-level is the KennisBank default).

Schema (verified from docs; cross-platform is native — Copilot picks `bash` on
Linux/macOS, `powershell` on Windows, matching KennisBank's `python3`/`py -3`
interpreter convention):

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      { "type": "command",
        "bash": "python3 <vault>/.claude/scripts/<script>.py",
        "powershell": "py -3 <vault>\\.claude\\scripts\\<script>.py",
        "cwd": ".", "timeoutSec": 60 }
    ]
  }
}
```

Events available: `sessionStart`, `sessionEnd`, `userPromptSubmitted`,
`preToolUse`, `postToolUse`, `errorOccurred`, `agentStop` (plus more in the
reference). Payload arrives as single-line JSON on **stdin** (camelCase keys such
as `sessionId`, `cwd`, `toolName`, `toolArgs`).

**Fail-open is mandatory and safety-critical.** `preToolUse` hooks are
fail-CLOSED on a non-zero exit (exit code 2 denies the tool call) but fail-OPEN
on timeout. KennisBank hooks therefore **always exit 0** and never emit a deny
decision — a missing Ollama, a script error, or a malformed payload skips the
KennisBank side effect but must never block Copilot. This matches the epic
non-goal ("no destructive changes / no blocking") and the existing Codex hook
posture. The Copilot payload shape differs from Claude's, so the KennisBank hook
handler parses Copilot's JSON explicitly (TASK-26.6 covers payload parsing +
secret redaction + malformed-payload tests).

### D4 — Wrapper / launcher (TASK-26.7): trivial exec, not a proxy

Headroom's `wrap` is a **proxy-interception** launcher: it injects durable
routing config, starts a background compression proxy, reroutes the agent's API
traffic to `http://127.0.0.1:{port}`, and needs SIGINT/SIGTERM handlers plus
restore-on-exit to tear all that down. **KennisBank has no proxy and reroutes
nothing.** The `kennisbank-copilot` launcher is therefore trivial: resolve
vault/runtime, set `KENNISBANK_VAULT` + instruction env, run a fast light-mode
validation, then hand off to the real `copilot` preserving argv and exit code
(`os.execvp` on POSIX; `subprocess.run` + propagate returncode on Windows). It
offers `--doctor`, `--dry-run`, `--print-env`, `--no-capture`, and works without
GitHub login in dry-run/doctor mode. The heavy machinery Headroom needs is
incidental to its proxy and is explicitly not copied.

### D5 — Rawlog / activity capture (TASK-26.8)

Two complementary sources, both local, both with `agent=github-copilot-cli`
provenance:

- **Live events** via the D3 hooks (a capture hook writes structured JSONL
  events to a KennisBank location).
- **Session import** from Copilot's own artifacts: `--share[=path]` markdown
  transcripts and `~/.copilot/session-state/<uuid>.jsonl`, imported into
  `01-raw/` with dedupe on `source_id`/`session_id` and an active-session skip
  policy, then extracted into `kb-activity.db` so `/watdeedik`, `/timeline`, and
  topic timeline surface Copilot activity.

### D6 — Config-mutation rule (TASK-26.2), borrowed from Headroom's *interfaces*

Two mechanisms, both KISS, both already present in KennisBank and generalized for
Copilot:

- **Structured config (JSON/TOML)** → key-scoped read-modify-write of a single
  namespaced key (`mcpServers.kennisbank`, the `hooks` object) + an equivalence
  check; read fails open on a missing/corrupt file; write is `indent=2` + trailing
  newline. No markers/backups needed because the edit touches one namespaced key.
- **Freeform files (AGENTS.md, copilot-instructions.md, the agent profile)** →
  marker-delimited managed block + presence check (the existing `_replace_block`
  with `KB_START`/`KB_END`).

From Headroom we borrow the **contract**, not the code: a `RegisterStatus`-style
outcome (registered / already / mismatch-left-untouched / failed) instead of a
bool; prefer-vendor-CLI-then-file-fallback for reads where useful; and
dependency-injectable paths (via `COPILOT_HOME`) for testability. We take
**inspiration, not interoperability, and no runtime dependency**.

### D7 — Headroom interoperability (TASK-26.12): not worthwhile

An import adapter for Headroom logs/config is **not** built. Headroom only
persists token-economics telemetry (savings ledger, proxy telemetry SQL); it
does not store session-knowledge (prompts, tool calls, files touched) that
KennisBank's recall needs. The purpose mismatch is grounded in Headroom's actual
schema, not a guess. Headroom stays inspiration only; if a concrete user ever
wants savings analytics inside KennisBank, that is a separate future task per
26.12 DoD. The KennisBank wrapper remains standalone.

## Config locations (cross-platform)

`~` = `$HOME` (POSIX) / `%USERPROFILE%` (Windows). All user-level paths honor
`COPILOT_HOME` when set. Windows paths marked *(inf)* are doc-only inferences to
verify empirically before hardcoding.

| Surface | User-level (global) | Repo-local | KennisBank writes |
|---|---|---|---|
| MCP servers | `~/.copilot/mcp-config.json` | `.mcp.json` / `.github/mcp.json` (undocumented, unused) | user-level, key `mcpServers.kennisbank` |
| Hooks | `~/.copilot/hooks/*.json` | `.github/hooks/NAME.json` | user-level `~/.copilot/hooks/kennisbank.json` |
| Custom agents | `~/.copilot/agents/*.agent.md` (wins on collision) | `.github/agents/*.agent.md` | user-level `kennisbank.agent.md` |
| Personal instructions | `~/.copilot/copilot-instructions.md` | — | user-level, managed block |
| Agent instructions | `AGENTS.md` via `COPILOT_CUSTOM_INSTRUCTIONS_DIRS` | `AGENTS.md` (root/cwd), `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md` | `AGENTS.md` managed block |
| Skills | `~/.copilot/skills/`, **`~/.agents/skills/`** | `.github/skills/`, `.agents/skills/`, `.claude/skills/` | already installed at `~/.agents/skills/` |
| Config/state | `~/.copilot/config.json` (auto), `~/.copilot/settings.json` (user) | — | none (never touch) |

## Fallbacks when Copilot is absent or not logged in

- **Not installed**: setup/doctor mark Copilot **skipped / non-fatal** with a
  concrete install hint. Copilot is never required unless the user explicitly
  selects it. Doctor gives 0 FAIL when Copilot is not selected.
- **Installed on Windows via nvm4w but binary missing**: verified real failure —
  `npm i -g @github/copilot` places the JS loader but may not fetch the optional
  platform binary, so `copilot --version` prints *"no platform package found"*.
  Remedy (setup must detect + advise, TASK-26.3): also install
  `@github/copilot-<platform>-<arch>` at the same version.
- **Installed but not logged in**: MCP/hook/instruction install and `copilot mcp
  list` all work login-free, so setup succeeds and doctor validates config; only
  a *live* end-to-end model turn needs `/login`. Login is never forced.

## Threat & operational risk

- **Credentials / cloud**: Copilot CLI is a cloud-backed service requiring a
  GitHub Copilot subscription; it sends requests to GitHub by design. This is an
  **explicit opt-in** integration — it does not change KennisBank's "nothing to
  the cloud without consent" default for the vault. Auth tokens
  (`COPILOT_GITHUB_TOKEN`/`GH_TOKEN`/`GITHUB_TOKEN`, or a PAT with "Copilot
  Requests") are the user's; KennisBank never stores, logs, or commits them.
- **Hook payloads**: hooks receive session/tool metadata on stdin and run
  arbitrary shell commands at lifecycle points. KennisBank's hook handler
  redacts known secret fields, never logs full credentials, tolerates malformed
  payloads, and always exits 0 (fail-open). A repo-committed `.github/hooks/*.json`
  from an untrusted repo is a code-execution vector — KennisBank installs only
  its own user-level hook and does not auto-trust repo hooks.
- **Transcript logging**: imported `--share`/session-state transcripts may
  contain sensitive content. They land in the local vault only, with provenance,
  and follow the same boundary as existing rawlog import — nothing is uploaded.
- **MCP secrets in plaintext**: `mcp-config.json` has no `${VAR}` interpolation;
  the KennisBank server needs no secret (Ollama-local), so its `env` holds only
  vault path + model settings — no tokens on disk or in shell history.
- **Rollback**: every mutation is a namespaced key or a marker-delimited block in
  a user file, so removal is surgical. `~/.copilot` pre-exists (populated by the
  IDE/language-server: `data.db`, `session-state/`); KennisBank touches only its
  own keys/files and never rewrites unmanaged content, with a backup before any
  freeform-file edit.
- **Version drift**: hook exit-code semantics and file schemas are
  version-sensitive (exit-2-deny hardened in v1.0.70). Doctor reports the
  detected `copilot --version`; the integration targets **v1.0.70+** and degrades
  to a WARN with a hint on older versions rather than silently misbehaving.

## Acceptance smoke (for the later implementation)

The end-to-end validation path (Windows PowerShell, vault
`D:\Users\Robert\Documents\Claude\Projects\Kluis`), reused by TASK-26.9/26.10 and
the epic AC#5:

1. **Detection** — `copilot --version` resolves and reports v1.0.70+ (or a clear
   skipped/upgrade diagnosis).
2. **MCP visible** — `~/.copilot/mcp-config.json` contains exactly one
   `mcpServers.kennisbank` with the real vault path; `copilot mcp list` shows it;
   `validate_mcp_runtime` completes the initialize + tool-list handshake.
3. **Hook event captured** — a synthetic Copilot hook payload piped to the
   KennisBank capture hook produces a structured activity event and exits 0.
4. **Rawlog written** — a fixture Copilot session/transcript imports idempotently
   into `01-raw/` with `agent=github-copilot-cli` provenance.
5. **Recall works** — `build-activity-index` ingests the Copilot source and a
   temporal recall query (`/watdeedik` / MCP `what_did_i_do`) returns the event
   with its source reference.

Each step is hermetic (temp `COPILOT_HOME`/`HOME`, fake `copilot` binary fixture,
synthetic payloads) so CI never needs a GitHub account; a live smoke is opt-in.

## Per-task mapping (no decision left vague)

| Task | Decision section |
|---|---|
| 26.2 config helpers & idempotency | D6; Config-locations table |
| 26.3 setup.sh agent choice + install caveat | Fallbacks (nvm4w binary) |
| 26.4 instructions + agent profile | D2 |
| 26.5 MCP registration | D1 |
| 26.6 hooks | D3 |
| 26.7 wrapper/launcher | D4 |
| 26.8 rawlog/activity import | D5 |
| 26.9 doctor/self-heal | D1–D6, Fallbacks, Acceptance smoke |
| 26.10 testsuite | Acceptance smoke; `COPILOT_HOME` hermetic key |
| 26.11 docs | whole ADR |
| 26.12 Headroom interop | D7 |
| 26.13 dashboard (install screen + summary) | Fallbacks; Acceptance smoke |

## Consequences

**Positive**
- Copilot becomes a first-class local agent by extending existing patterns
  (`AGENTS` tuple, `install_*`, `validate_*`, `_replace_block`, key-scoped JSON),
  not by inventing new machinery. Skills are essentially free.
- Every surface fact is verified against the installed CLI, so mocks and the fake
  binary fixture match reality instead of a hallucinated surface.
- Fully hermetic, login-free testing via `COPILOT_HOME`.

**Negative / trade-offs**
- Copilot is cloud-backed; its integration is opt-in and cannot honor
  "Lokaal, altijd" for model traffic (only KennisBank's own retrieval stays
  local). BYOK/Ollama for Copilot is deliberately deferred.
- Hook exit-code and schema behavior are version-sensitive; the integration
  pins expectations to v1.0.70+ and WARNs below it.
- A few doc-only facts (Windows path resolution, agent frontmatter) remain
  verify-before-hardcode and are validated empirically during implementation.

## References

- `scripts/install-agent-envs.py` — the cross-agent layer this ADR extends
  (`AGENTS`, `install_codex`/`install_opencode`, `_replace_block`,
  `_ensure_*_mcp`, `validate_mcp_runtime`).
- `docs/agent-integrations.md` — per-agent surface documentation (Copilot section
  added by TASK-26.11).
- ADR-0002 — cross-platform (macOS/Linux/Windows Git Bash) rules that govern all
  new Copilot scripts and tests.
- GitHub Copilot CLI docs: set-up/install, add-custom-instructions,
  add-mcp-servers, use-hooks (+ `reference/hooks-reference`),
  create-custom-agents-for-cli (fetched & verified 2026-07-11).
- Real CLI probe: `copilot` v1.0.70 win32-x64 (`--help`, `mcp add|list --help`,
  `help config|environment|logging`, hermetic `COPILOT_HOME` `mcp add`).
- `headroomlabs-ai/headroom` — `mcp_registry/base.py`+`claude.py` (idempotency
  contract, read verbatim), `cli/wrap.py`, `cli/doctor.py`,
  `providers/copilot/` (wrapper pattern & telemetry-only persistence, basis for
  the "inspiration, not dependency" decision).
```

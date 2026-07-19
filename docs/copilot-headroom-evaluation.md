# Headroom compatibility evaluation (KennisBank Copilot integration)

- **Task**: TASK-26.12 (child of TASK-26, the local Copilot CLI integration epic)
- **Date**: 2026-07-11
- **Grounds**: ADR-0003 (`docs/adr/0003-copilot-cli-integration.md`), sections
  **D4** (wrapper/launcher) and **D7** (Headroom interoperability), plus the
  Headroom source read for this epic.

This is the standalone technical evaluation that TASK-26.12 asks for. It answers
whether KennisBank should interoperate with Headroom
(`headroomlabs-ai/headroom`), and classifies what we take from it. ADR-0003 D4/D7
carry the full derivation; this doc restates the conclusion and makes the
three-way split explicit. It does **not** re-derive the facts — they are already
verified and Accepted in ADR-0003.

## Decision

**Do not adopt Headroom as a runtime dependency, and do not build a Headroom
log/config import adapter now.** KennisBank's `kennisbank-copilot` wrapper stays
a standalone trivial exec (ADR-0003 D4). Headroom remains **inspiration only**.

Coexistence is a separate, weaker claim and it holds: if a user chooses to run
Copilot *under* Headroom's launcher, KennisBank's MCP server, personal skills,
and instructions still work because they live in Copilot's own config which
Headroom does not remove. KennisBank no longer installs Copilot lifecycle hooks;
see ADR-005. Coexistence is possible but not something KennisBank builds,
requires, or depends on.

## What Headroom actually is

Headroom's `wrap` is a **proxy-interception launcher**. It injects durable
routing config, starts a background compression proxy, and reroutes the agent's
model API traffic to `http://127.0.0.1:{port}`. For Copilot specifically it sets
`COPILOT_PROVIDER_TYPE` / `COPILOT_PROVIDER_BASE_URL` / `COPILOT_PROVIDER_API_KEY`
/ `COPILOT_PROVIDER_WIRE_API` to point the agent at that local proxy. The
SIGINT/SIGTERM handlers and restore-on-exit machinery exist **only** to tear that
proxy lifecycle down cleanly — they are incidental to the proxy, not a general
wrapper requirement.

KennisBank has no proxy and reroutes no model traffic. Its goal is knowledge
retrieval, not token-economics compression. So most of Headroom's launcher
machinery is machinery for a problem KennisBank does not have.

## Three-way classification (the point of this doc)

### 1. Inspiration — interfaces borrowed, no code, no runtime dependency

Taken as design contracts (re-implemented in KennisBank's own idiom, cross-linked
from ADR-0003 D6):

- **The MCPRegistrar idempotency contract.** A `RegisterStatus`-style outcome
  enum (`registered` / `already` / `mismatch-left-untouched` / `failed`) instead
  of a bare bool. On a **mismatch**, the existing config is left untouched unless
  the caller forces an overwrite. Reads always come **direct from file**.
- **Prefer-vendor-CLI-then-file-fallback** for reads where a vendor CLI adds
  value, but the durable mutation is a direct file edit.
- **Key-scoped read-modify-write** of a single namespaced config key — never a
  whole-file overwrite.
- **Marker + backup + restore** applied only to *transient injected* freeform
  config, not to structured single-key edits.
- **Dependency-injectable paths** (`COPILOT_HOME`) for hermetic, login-free
  tests.
- **A `diagnose`/doctor convention**: `--json`, PASS/WARN/FAIL/SKIP statuses,
  and a `0/1/2` exit-code convention.

These are ideas. No Headroom code is vendored and no Headroom package is
imported.

### 2. Optional interoperability — possible, but not built and not required

The literal TASK-26.12 question: can Headroom, used as an *external launcher*,
still carry KennisBank's MCP / hooks / instructions?

**Yes, in principle.** Those surfaces live in Copilot's own config —
`~/.copilot/mcp-config.json`, `~/.copilot/hooks/`, `~/.copilot/agents/`,
`~/.copilot/copilot-instructions.md` — which Copilot reads regardless of who
launched it. Headroom's `wrap` injects provider-routing env and starts its proxy;
it does not delete or rewrite those KennisBank files. So a Headroom `wrap` and
KennisBank's Copilot config **coexist**: Headroom wraps the launch, Copilot still
loads the KennisBank MCP server and hooks.

The one hard boundary: **KennisBank owns and touches only its `KENNISBANK_*`
namespace and its own `~/.copilot/*` keys/blocks. It must never read or write
Headroom's `HEADROOM_*` / `COPILOT_PROVIDER_*` namespaces.** Reaching into
Headroom's config would create a hidden coupling and break the "no runtime
dependency" guarantee. Coexistence is a property we preserve by *not* entangling,
not a feature we wire up.

This is why there is no "clean integration point" to build: coexistence already
falls out of both tools writing to disjoint, well-namespaced locations. Nothing
needs to be added for it to hold.

### 3. Explicitly NOT adopted as a runtime dependency

KennisBank deliberately rejects, as runtime dependencies:

- The **proxy / compression core** itself.
- The **API rerouting** (`COPILOT_PROVIDER_BASE_URL=127.0.0.1:{port}` and the
  related `COPILOT_PROVIDER_*` env). KennisBank does not intercept model traffic.
- The **subprocess + signal-handler + restore-on-exit launch machinery** — only
  needed to manage the proxy lifecycle Headroom introduces.
- The **heavy dependency stack** (Rust / ONNX / PyTorch / Hugging Face) that the
  compression core pulls in. KennisBank stays light and local (SQLite, markdown,
  local Ollama).
- The **`HEADROOM_*` and `COPILOT_PROVIDER_*` config namespaces**.
- The **container / supervisor install model**.

Per ADR-0003 D4, `kennisbank-copilot` is a trivial exec: resolve vault/runtime,
set `KENNISBANK_VAULT` + instruction env, run a fast light-mode validation, then
hand off to the real `copilot` preserving argv and exit code (`os.execvp` on
POSIX; `subprocess.run` + returncode propagation on Windows). No proxy, no
rerouting, no signal-teardown dance.

## Import adapter for Headroom logs/config: NO

Grounded in Headroom's actual persistence, not a vibe. Headroom stores only
**token-economics telemetry** — a savings ledger and proxy telemetry
(`savings_ledger.py`, `sql/create_proxy_telemetry_v2.sql`,
`create_dashboard_summary.sql`) — plus **ephemeral in-flight compression
restoration** in the capture layer. It does **not** persist the
session-knowledge KennisBank recall needs: prompts, tool calls, files touched,
decisions.

An import adapter would therefore ingest savings/compression metrics with **zero
retrieval value** for KennisBank. This is a **purpose mismatch at the schema
level**, not a matter of effort or polish. KennisBank can capture the
session-knowledge it needs explicitly through `/sessielog`, `--share`
transcripts, and imports from `~/.copilot/session-state/*.jsonl`, which is the
layer Headroom does not keep. ADR-005 supersedes ADR-0003's lifecycle-hook
capture route.

## Rationale

1. **No shared problem.** Headroom optimizes token cost via a proxy; KennisBank
   surfaces knowledge. The bulk of Headroom's runtime exists to serve a goal
   KennisBank does not pursue, so importing it would add weight and a network
   interception path for no retrieval benefit.
2. **The valuable parts are interfaces, not code.** The idempotency contract,
   the doctor convention, and injectable paths are cheap to re-implement in
   KennisBank's own idiom and carry no dependency, no heavy stack, and no
   namespace coupling.
3. **Coexistence needs nothing built.** Because both tools write to disjoint,
   namespaced locations, running Copilot under Headroom already leaves KennisBank
   config intact. The only work is *restraint*: don't touch Headroom's namespaces.
4. **The import adapter fails on data, not sentiment.** Headroom simply does not
   store what recall consumes.

## Future work (none created now)

Integration is **not worthwhile now**, so no follow-up task is created (per
TASK-26.12 AC#3 / DoD: no Headroom dependency without an explicit follow-up
task). If a concrete user ever wants Headroom's savings analytics surfaced inside
KennisBank, or a deeper launcher hand-off, that is a **separate future task with
its own acceptance criteria** — evaluated on its own merits, not smuggled in
here. This document records the decision to defer; it does not open that task.

## Reviewed sources

Confirming AC#4 — the Headroom provider / wrapper / install / telemetry code was
read directly (`headroomlabs-ai/headroom`, via the GitHub API + raw file
fetches), matching ADR-0003's own References:

- `mcp_registry/base.py` + `mcp_registry/claude.py` — read **verbatim**; source
  of the idempotency-contract inspiration. `base.py` is the **shared registrar**
  and `claude.py` the representative concrete provider; the registrar pattern is
  shared across Headroom's agent providers (the Copilot provider is covered
  separately below). Codex / OpenCode provider variants were not separately read
  — AC#4's "waar aanwezig" (where present) scope is satisfied by the shared base
  plus the Claude and Copilot providers as representatives; no unread file is
  claimed here.
- `cli/wrap.py` — the proxy-interception launcher (durable routing injection,
  background proxy, API rerouting, signal handlers, restore-on-exit).
- `cli/doctor.py` — the diagnose/doctor convention (`--json`, PASS/WARN/FAIL/SKIP,
  `0/1/2` exit codes).
- `providers/copilot/install.py` + `providers/copilot/wrap.py` — the Copilot
  provider specifically: `COPILOT_PROVIDER_*` rerouting and the container/
  supervisor install model.
- `sql/` telemetry schema — `create_proxy_telemetry_v2.sql`,
  `create_dashboard_summary.sql`, and `savings_ledger.py` — token-economics
  telemetry only; the basis for the "no import adapter" decision.
- `headroom/capture/` — ephemeral in-flight compression restoration; confirms no
  durable session-knowledge is persisted.

## Cross-references

- **ADR-0003 D4** (`docs/adr/0003-copilot-cli-integration.md`) — wrapper/launcher:
  trivial exec, not a proxy.
- **ADR-0003 D7** — Headroom interoperability: not worthwhile; import adapter not
  built; grounded in Headroom's schema.
- **ADR-0003 D6** — the config-mutation contract borrowed from Headroom's
  *interfaces* (inspiration, not interoperability, no runtime dependency).
- **ADR-0003 D5**, as superseded by **ADR-005** — where KennisBank gets Copilot
  session-knowledge (explicit session skills, transcripts, and session-state),
  the layer Headroom does not persist.

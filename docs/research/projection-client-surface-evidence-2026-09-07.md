# Projection client-surface evidence — 2026-09-07

## Scope and semantic contract

All supported local CLI clients expose the same default-off product semantics:

1. use reviewed `experience_recall` first only when the user explicitly asks
   what worked before;
2. use `source_recall` only on demand for underlying evidence, verification, or
   exact reconstruction;
3. never inject either route automatically and never emit automatic failure
   advisories;
4. preserve ordinary wiki/memory recall when the optional route, projection,
   embedding backend, vector extension, or MCP SDK is unavailable.

The four capability flags remain independent and default off:
`experience_capture`, `experience_projection`,
`experience_explicit_recall`, and `source_explicit_recall`. Legacy broad flag
names grant no capability.

## Client-by-client artifact map

| Client | Explicit workflow artifacts | Runtime surface | Smoke proof |
|---|---|---|---|
| Claude Code | `~/.claude/commands/kennisbank/{experience-recall,source-recall}.md`; deployed gateway scripts under `<vault>/.claude/scripts/` | Namespaced commands execute the local gateways; setup deliberately does not register MCP for Claude | A temporary full setup executed both deployed scripts; each returned `disabled` and `hits=[]` with exit 0 |
| Codex | `~/.agents/skills/kennisbank-{experience-recall,source-recall}/SKILL.md`; matching `~/.codex/prompts/` aliases; managed `AGENTS.md` | `~/.codex/config.toml` local stdio MCP | Generated-artifact parity tests plus shared MCP initialize/list/call smoke |
| OpenCode | `~/.config/opencode/commands/kennisbank-{experience-recall,source-recall}.md`; shared skills; managed `AGENTS.md` | `opencode.json` local stdio MCP; plugin remains fail-open | Generated-artifact parity tests plus shared MCP initialize/list/call smoke |
| GitHub Copilot CLI | Shared personal skills; managed `copilot-instructions.md` and `agents/kennisbank.agent.md` | `~/.copilot/mcp-config.json` local stdio MCP; Copilot model traffic remains its separate cloud boundary | Config/profile tests plus shared MCP initialize/list/call smoke |

Operational rebuild and proposal workflows are generated alongside the recall
workflows: `kennisbank-rebuild-source-index`,
`kennisbank-rebuild-experience`, and `kennisbank-experience-proposal`.

## Runtime discovery and call proof

The wire harness started the real `kb-mcp.py` subprocess, completed the legacy
MCP initialize handshake, and discovered the exact ten-tool contract:

```text
capture, experience_recall, recall, review_decide, review_pending,
source_recall, timeline, topic_timeline, what_did_i_do, weeklog
```

It then called `experience_recall` and `source_recall` over JSON-RPC in a fresh
default-off vault. Both returned structured `disabled` responses with empty hit
lists and no MCP error. Setup's `validate_mcp_runtime` now performs the same
ordinary/source/experience call-smoke after `list_tools`; an empty ordinary
query keeps this validation independent of Ollama.

## Artifact parity proof

The client installers use one `NESTED_COMMAND_ALIASES` source map. Tests compare
the complete canonical command body against every generated Codex prompt,
OpenCode command, and shared Codex/Copilot skill. The generated managed
instructions for Codex/OpenCode and the separate Copilot instruction/profile
writer all contain the same experience-first, source-on-demand rule and pin
`KENNISBANK_VAULT`.

Current README variants, configuration guide, settings command, agent install
guide, C4 integration/retrieval/container views, upgrade skill, upgrade note,
and rebuild command now use the split ledger/index names and four current
flags. A static regression test rejects the prior broad flags, mixed-store
description, incremental+records-only contract, and failure-advisory wording.

## Fail-open matrix

| Missing/degraded dependency | Expected result | Evidence |
|---|---|---|
| MCP SDK absent | MCP server exits 0 with an actionable dependency notice; hook/direct routes remain unaffected | MCP SDK failure-mode tests |
| MCP SDK incompatible | Installer/server reports the broken SDK instead of claiming a valid MCP install | MCP SDK failure-mode and validator tests |
| Ollama/embedding unavailable | Ordinary recall returns no injected hit; experience rebuild/search uses labelled lexical fallback | MCP core and experience fallback tests |
| sqlite-vector extension unavailable | Source recall remains vector-free FTS; experience recall uses lexical fallback | source schema and experience production tests |
| source/experience gateway or projection absent | Explicit route returns `unavailable`; ordinary recall still returns its normal result | MCP isolation test |
| feature flag disabled | Direct CLI and real MCP calls return `disabled`, empty hits, and no exception | deployed Claude smoke and wire smoke |

## Verification result

```text
75 client, Copilot, MCP-wire, core, and documentation tests passed in 34.99s
4 temporary Claude setup/deploy tests passed in 70.79s
76 combined client plus deployed-gateway checks passed in 94.37s
```

The combined run includes the real MCP subprocess and a real isolated setup
deployment. It does not mutate global user client configuration or enable live
feature flags.

## Explicitly unsupported/limited surfaces

- Claude Code receives the explicit namespaced commands but no MCP registration
  from setup; this is intentional and documented.
- Claude Cowork is not an `--agents` install target. A user may connect the MCP
  server manually, but that surface is outside this release gate.
- Hosted agents cannot reach local stdio without violating the local-only
  boundary. No tunnel or hosted fallback is provided.
- Product usefulness is not established by this integration smoke. Frozen
  evaluation and owner canary remain the next independent gate.

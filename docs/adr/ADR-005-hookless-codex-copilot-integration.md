---
id: "ADR-005"
title: "Use hookless integrations for Codex and Copilot"
status: "Accepted"
date: "2026-07-19"
binding: false
gate: null
documents_shipped: true
verified_in:
  - "tests/test_agent_envs_install.py"
  - "tests/test_copilot_config.py"
supersedes: []
superseded_by: null
format: "madr"
---

<!-- markdownlint-disable MD025 -->

# ADR-005 Use hookless integrations for Codex and Copilot

## Status

Accepted, 2026-07-19.

## Status History

```yaml
status_history:
  - date: 2026-07-19
    status: Proposed
    changed_by: Codex
    reason: Client-rendered lifecycle rows cannot be suppressed by hook output
    changed_via: adr-kit
  - date: 2026-07-19
    status: Accepted
    changed_by: Codex
    reason: TASK-34 implementation and migration tests satisfy the decision gates
    changed_via: adr-kit
```

## Context and Problem Statement

KennisBank v0.16.1 made hook processes quiet, but Codex and the standalone
GitHub Copilot CLI still display `Running ... hook` and
`SessionStart hook (completed)`. The clients render those rows because a hook
is registered; child-process output cannot remove them.

The Codex manual says `suppressOutput` is parsed but not implemented. GitHub
Copilot's hook schema has no equivalent lifecycle-UI suppression field. Both
clients support personal skills and the local KennisBank MCP server.

## Decision Drivers

* Guarantee zero KennisBank hook rows in Codex and Copilot.
* Preserve local recall and capture without a hosted dependency.
* Preserve hooks owned by the user or other integrations.
* Provide native, agent-readable session workflows on Windows, macOS, and Linux.

## Considered Options

* Keep all hooks and suppress process output.
* Consolidate startup work behind one hook.
* Remove KennisBank hooks and use skills plus MCP.

## Decision Outcome

Chosen option: **remove KennisBank hooks and use skills plus MCP**, because it is
the only deterministic way to prevent client-rendered lifecycle rows.

Fresh installs create no KennisBank hooks for Codex or Copilot. Upgrades remove
only commands targeting known KennisBank scripts and preserve unrelated hooks.
Every KennisBank command is installed under
`~/.agents/skills/<command>/SKILL.md`.

Copilot invokes `/sessiestart` and `/sessielog`. Codex invokes `$sessiestart`
and `$sessielog`; `/prompts:<command>` remains a deprecated compatibility path.
MCP remains the live local recall/capture API. Claude and OpenCode behavior is
unchanged.

This supersedes ADR-0003 D3 and the live-hook part of D5. Session import remains
supported.

### Confirmation

Tests verify fresh hookless installs, selective legacy-hook removal,
idempotency, native skill generation, MCP vault pinning, and validation failure
when KennisBank hooks remain.

## Consequences

### Positive

* Codex and Copilot produce zero KennisBank hook progress/completion rows.
* Migration is deterministic, local, dependency-free, and preserves user hooks.
* Commands are discoverable as agent-readable Markdown skills.

### Negative

* Startup maintenance and session capture are explicit, not automatic.
* Codex cannot provide arbitrary bare slash aliases.

The README places the two session commands directly after install instructions,
and MCP remains available independently of lifecycle hooks.

## Pros and Cons of the Options

### Keep all hooks and suppress process output

* Good, because maintenance remains automatic.
* Bad, because client-rendered lifecycle rows remain visible.

### Consolidate startup work behind one hook

* Good, because it reduces several rows to one.
* Bad, because one row still violates the zero-noise requirement.

### Remove KennisBank hooks and use skills plus MCP

* Good, because it guarantees zero KennisBank hook rows.
* Good, because skills and MCP are local and cross-platform.
* Bad, because users explicitly invoke session maintenance and capture.

## Related Decisions

* ADR-0003: superseded for D3 and the live-hook portion of D5.
* ADR-0002: cross-platform path and interpreter rules still apply.

## References

* [Codex manual](https://developers.openai.com/codex/codex-manual.md)
* [GitHub Copilot hooks reference](https://docs.github.com/en/copilot/reference/hooks-reference)
* [GitHub Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)
* `scripts/install-agent-envs.py`
* `scripts/_copilot.py`
* TASK-34

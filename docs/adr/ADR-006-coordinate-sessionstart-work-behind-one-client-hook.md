---
id: "ADR-006"
title: "Coordinate SessionStart work behind one client hook"
status: "Accepted"
date: "2026-07-19"
binding: false
gate: null
documents_shipped: false
verified_in: []
supersedes:
  - "ADR-005"
superseded_by: null
format: "madr"
---

<!-- markdownlint-disable MD025 -->

# ADR-006 Coordinate SessionStart work behind one client hook

## Status

Accepted, 2026-07-19.

## Status History

```yaml
status_history:
  - date: 2026-07-19
    status: Proposed
    changed_by: Codex
    reason: Initial proposal
    changed_via: adr-kit
  - date: 2026-07-19
    status: Accepted
    changed_by: Codex
    reason: Four ADR quality gates pass and implementation verification is green
    changed_via: adr-kit lifecycle
  - date: 2026-07-19
    status: Accepted
    changed_by: Codex
    reason: Coordinated automation selected for v0.17.0 after the explicit-session trade-off was reconsidered
    changed_via: adr-kit lifecycle
```

## Context and Problem Statement

KennisBank previously registered six independent SessionStart maintenance hooks
in Claude Code and Codex, and eight in the GitHub Copilot command-line
interface. The clients schedule
matching hooks concurrently and render lifecycle progress themselves. A quiet
wrapper suppresses routine child output but cannot reliably hide a client-owned
`Running SessionStart hook` or `SessionStart hook (completed)` row.

The observed result was repeated interface noise, non-deterministic
dependency order,
and duplicate maintenance after startup/resume event bursts. Removing startup
automation would eliminate the rows but make freshness, health notices, and
Copilot event capture depend on a person remembering an explicit command.
In the reported large vault, one activity-index run took `26.2 s`, so serializing
the independent index builders would materially increase startup latency.

## Decision Drivers

* Reduce six to eight client lifecycle rows to the smallest portable number.
* Preserve automatic index freshness, health notices, and activity capture.
* Run independent work concurrently so large activity indexes do not serialize
  all startup work.
* Make data dependencies explicit and deterministic.
* Preserve unrelated hooks and non-SessionStart KennisBank behavior on upgrade.
* Remain stdlib-only, cross-platform, time-bounded, and fail-open.
* Emit only actionable changes through each client's native context envelope.

## Considered Options

* Register one phased SessionStart coordinator per client.
* Keep the independent SessionStart hook fan-out.
* Remove SessionStart automation and rely on commands plus the local
  model-context protocol.
* Run all startup tasks sequentially.
* Build a separate coordinator for each client.

## Decision Outcome

Chosen option: **register one phased SessionStart coordinator per client**,
because it reduces the unavoidable client interface to one lifecycle row while
retaining automatic freshness and concurrent performance.

`kb-session-start.py`:

1. runs Copilot import before maintenance when Copilot is the client;
2. runs embedding, knowledge, activity, and sweep-launch jobs concurrently;
3. runs memory and distillation notices concurrently after maintenance;
4. captures Copilot SessionStart even when maintenance is freshness-gated;
5. uses a per-vault lock and five-minute completion stamp to collapse rapid
   startup/resume/clear/compact event bursts;
6. captures child output, discards routine no-change text, and emits at most one
   client-native context payload containing only changes or actions;
7. applies a timeout per child and always exits zero.

Setup recognizes legacy SessionStart script basenames, removes only those
entries, preserves unrelated hooks, and installs one coordinator in Claude
Code, Codex, and Copilot. Prompt retrieval, presearch, transcript/usage capture,
and Copilot prompt/tool/session capture remain installed.

Command workflows are installed as user-invocable skills: Codex uses
`$sessiestart` and `$sessielog` with `/prompts:*` compatibility; Copilot uses
`/sessiestart` and `/sessielog`.

MADR (Markdown Architecture Decision Records) 4 is used because its explicit
drivers, options, outcome, confirmation, and per-option trade-offs are
deterministic for agents to scan and verify. It is the ADR Kit preferred profile
and exposes more reasoning structure than the repository's older lightweight
records.

### Confirmation

Verification requires:

* unit tests proving concurrent overlap and notification-after-maintenance order;
* tests for freshness, lock, timeout/failure, and one context envelope;
* migration/idempotency tests preserving unrelated hooks in all three clients;
* Windows `py -3` and macOS/Linux `python3` command-shape tests;
* setup/doctor integration tests for exactly one coordinator;
* documentation contract tests for native invocation and the one-row boundary.

## Consequences

### Positive

* KennisBank SessionStart registrations fall from `6` in Claude/Codex and `8`
  in Copilot to `1` per client, an `83%` to `87.5%` reduction.
* Independent jobs retain parallel performance.
* Dependencies and output aggregation become explicit and testable.
* Rapid repeated lifecycle events do not repeatedly rebuild unchanged indexes.
* Upgrade remains deterministic and non-destructive.

### Negative

* One generic lifecycle row may remain because the client owns that interface.
  Mitigation: register only one handler and keep its routine output empty.
* Shared startup infrastructure increases the coordinator's blast radius.
  Mitigation: per-child timeouts, exception isolation, exit-zero behavior, and
  dedicated concurrency/migration tests.
* A five-minute freshness window can briefly defer a just-landed change.
  Mitigation: explicit session commands remain available and the next event
  after the short window refreshes automatically.

## Pros and Cons of the Options

### One phased coordinator

* Good, because it combines one lifecycle row, deterministic phases, and
  concurrent independent work.
* Good, because one stdlib implementation can emit native envelopes for all
  clients and is testable on every supported platform.
* Bad, because it cannot remove the final client-owned lifecycle row.

### Independent hook fan-out

* Good, because clients schedule independent handlers concurrently.
* Bad, because each registration may create an interface row and dependencies are not
  ordered.

### No SessionStart automation

* Good, because it guarantees zero KennisBank startup rows.
* Bad, because freshness, notices, and capture silently depend on user memory.

### Fully sequential coordinator

* Good, because ordering is straightforward.
* Bad, because independent runtimes add together; a large activity index can
  materially delay startup.

### Per-client coordinators

* Good, because each implementation could target one client schema directly.
* Bad, because behavior and migration logic would drift across clients.

## Related Decisions

* ADR-0003 remains authoritative for Copilot integration. Its D3 SessionStart
  fan-out is refined by this decision; prompt/tool/session-end capture remains.
* ADR-0002 defines cross-platform script requirements.

## References

* `scripts/kb-session-start.py:46` defines the concurrent maintenance phase.
* `scripts/kb-session-start.py:239` implements phased coordination.
* `scripts/_hooks_manifest.py:13` registers the single Claude coordinator.
* `scripts/install-agent-envs.py:352` defines the single Codex coordinator.
* `scripts/_copilot.py:339` defines the single Copilot coordinator.
* `tests/test_session_start.py` verifies concurrency, order, freshness, and
  output envelopes.
* [Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/hooks)
* [GitHub Copilot hooks reference](https://docs.github.com/en/copilot/reference/hooks-configuration)
* [OpenAI Codex documentation](https://developers.openai.com/codex/)

## Enforcement

```json
{
  "forbid_pattern": [
    {
      "path_glob": "scripts/_hooks_manifest.py",
      "pattern": "\\(\"SessionStart\",\\s+\"(?:build-embed-index|build-kb-index|build-activity-index|sweep-launch|memory-notify|distill-notify)\\.py\"",
      "message": "Register SessionStart maintenance only through kb-session-start.py."
    }
  ],
  "forbid_import": [],
  "require_pattern": [
    {
      "path_glob": "scripts/_hooks_manifest.py",
      "pattern": "\\(\"SessionStart\",\\s+\"kb-session-start\\.py\"",
      "message": "The Claude manifest must retain the single SessionStart coordinator."
    }
  ],
  "llm_judge": false
}
```

---
id: "ADR-007"
title: "Coordinate session logging and exit work behind one client hook"
status: "Accepted"
date: "2026-07-19"
binding: false
gate: null
documents_shipped: false
verified_in: []
supersedes: []
superseded_by: null
format: "madr"
---

<!-- markdownlint-disable MD025 -->

# ADR-007 Coordinate session logging and exit work behind one client hook

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
    reason: Focused, broad, migration, setup, and quality verification passed
    changed_via: adr-kit lifecycle
```

## Context and Problem Statement

ADR-006 reduced SessionStart fan-out to one phased coordinator, but each client
still registered multiple KennisBank exit handlers: Claude Code and Codex ran
transcript archival and usage attribution separately; Copilot captured the
session-end event and ran usage attribution separately. Clients can render one
lifecycle row per registered handler, so quiet child output does not prevent
repeated exit rows. Independent handlers also leave capture-before-analysis
ordering implicit.

The explicit `/sessielog` workflow has a different constraint. An agent must
summarize the current conversation, reconcile wiki material, and make editorial
judgments. Those semantic steps cannot be replaced deterministically without
losing the user's current context. Its mechanical follow-up, however, repeated
index, sweep, and notice invocations as prose instead of exposing one tested
execution boundary.

## Decision Drivers

* Reduce KennisBank exit registrations to one per Claude, Codex, and Copilot.
* Guarantee capture completes before work that consumes the completed session.
* Run independent post-capture work concurrently.
* Keep routine shutdown output empty and never delay indefinitely or block exit.
* Preserve unrelated user exit hooks during install and upgrade.
* Retain agent judgment for semantic `/sessielog` authoring.
* Give `/sessielog` one cross-platform, deterministic post-save helper.
* Remain stdlib-only and work on Windows, macOS, and Linux.

## Considered Options

* One phased exit coordinator plus one mechanical sessielog helper.
* One exit coordinator that also generates the semantic session log.
* Keep independent exit hooks and prose-only sessielog follow-up.
* Remove exit automation and require `/sessielog`.
* Run every exit and sessielog child fully sequentially.

## Decision Outcome

Chosen option: **one phased exit coordinator plus one mechanical sessielog
helper**, because capture order becomes deterministic without automating
editorial judgment, while independent follow-up retains parallel performance.

`kb-session-end.py` reads the client payload once and always exits zero:

1. Claude and Codex run `archive-transcript.py` as the capture phase.
2. Copilot runs `kb-copilot-capture.py --event sessionEnd` as the capture phase.
3. After capture completes, usage attribution runs; Copilot also imports the
   completed staging stream with `import-copilot.py --include-active`.
4. Independent post-capture jobs run concurrently with per-child timeouts.
5. Routine stdout is always empty. The last aggregate status is written to
   `<vault>/.claude/kb-session-end-state.json` for diagnostics.

Setup deterministically removes the known legacy exit script basenames,
deduplicates `kb-session-end.py`, preserves unrelated entries, and registers
one coordinator as Claude `SessionEnd`, Codex `Stop`, and Copilot `sessionEnd`.

The native `/sessielog` workflow remains responsible for writing the semantic
session log and curating wiki changes. After all writes it invokes
`kb-session-log.py --session-log <path>` once. The helper validates that the
path is inside `<vault>/01-raw/sessies`, runs independent index and sweep-launch
jobs concurrently, and runs notices after indexes complete.

MADR 4 is used because explicit drivers, options, outcome, confirmation, and
trade-offs make the capture-order invariant and the semantic/mechanical
boundary easy for coding agents to retrieve and verify. It is ADR Kit's
preferred agent-friendly profile; Nygard is terser but exposes less option
structure, while the canonical profile primarily serves backward compatibility.

### Confirmation

Verification requires:

* concurrency tests proving capture-before-follow-up and parallel Copilot jobs;
* tests proving routine exit stdout is empty, timeouts are recorded, and main
  remains exit zero;
* migration/idempotency tests for exactly one coordinator in all three clients
  while preserving unrelated exit hooks;
* sessielog tests proving parallel index work and notices-after-index order;
* validation of Windows `py -3` and macOS/Linux `python3` command shapes;
* setup deployment and real-vault validation;
* strict ADR lint and all four ADR quality gates.

## Consequences

### Positive

* KennisBank exit registrations fall from `2` to `1` per client, a `50%`
  reduction in KennisBank-owned exit rows.
* Capture-before-analysis is explicit, deterministic, and testable.
* Copilot activity becomes importable immediately at exit instead of waiting
  for the next startup.
* `/sessielog` has one stable mechanical execution boundary that agents can
  invoke without reproducing a script fan-out.
* Known legacy hooks are migrated without touching unrelated user automation.

### Negative

* One client-owned lifecycle row may remain for start and one for exit.
  Mitigation: routine coordinator output is empty and registrations are reduced
  to the portable minimum.
* The exit coordinator is a shared failure boundary. Mitigation: child
  isolation, timeouts, aggregate local diagnostics, and unconditional exit zero.
* Immediate Copilot import adds bounded exit work. Mitigation: capture remains
  first, import has a `60 s` timeout, and any failure is deferred to the
  next idempotent startup import.
* Semantic `/sessielog` behavior is not fully deterministic. Mitigation: keep
  the agent-authored portion explicit and move every mechanical post-save step
  behind a tested helper.

## Pros and Cons of the Options

### Phased exit coordinator plus mechanical sessielog helper

* Good, because capture order, concurrency, silence, and migration are explicit.
* Good, because agents retain the conversational context needed for semantic
  summarization while deterministic work has one script entrypoint.
* Bad, because two coordinator scripts must be maintained alongside startup.

### Exit coordinator also generates the semantic session log

* Good, because session capture would be fully automatic.
* Bad, because a deterministic hook lacks the agent's current reasoning context
  and an LLM-backed exit hook would add latency, cost, and failure modes.

### Independent hooks and prose-only sessielog follow-up

* Good, because each child remains operationally isolated.
* Bad, because clients render multiple rows, ordering is implicit, and agents
  can execute or omit mechanical steps inconsistently.

### No exit automation

* Good, because it eliminates exit hook rows.
* Bad, because archival, attribution, and Copilot import depend on user memory.

### Fully sequential execution

* Good, because the schedule is simple.
* Bad, because independent runtimes add together and unnecessarily extend
  explicit sessielog and exit workflows.

## Related Decisions

* ADR-006 defines the same phased coordination principle for SessionStart.
* ADR-0003 remains authoritative for Copilot integration; this decision refines
  its independent `sessionEnd` registrations.
* ADR-0002 defines cross-platform script and path behavior.

## References

* `scripts/kb-session-end.py:121` implements capture-before-follow-up phases.
* `scripts/kb-session-log.py:127` implements mechanical post-save coordination.
* `scripts/_hooks_manifest.py:15` registers one Claude exit coordinator.
* `scripts/install-agent-envs.py:391` registers one Codex exit coordinator.
* `scripts/_copilot.py:350` registers one Copilot exit coordinator.
* `tests/test_session_end.py` verifies ordering, concurrency, silence, and state.
* `tests/test_session_log.py` verifies concurrent follow-up and dependency order.
* [Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/hooks)
* [GitHub Copilot hooks reference](https://docs.github.com/en/copilot/reference/hooks-configuration)
* [OpenAI Codex documentation](https://developers.openai.com/codex/)

## Enforcement

```json
{
  "forbid_pattern": [
    {
      "path_glob": "scripts/_hooks_manifest.py",
      "pattern": "\\(\"SessionEnd\",\\s+\"(?:archive-transcript|kb-usage-scan)\\.py\"",
      "message": "Register Claude exit work only through kb-session-end.py."
    }
  ],
  "forbid_import": [],
  "require_pattern": [
    {
      "path_glob": "scripts/_hooks_manifest.py",
      "pattern": "\\(\"SessionEnd\",\\s+\"kb-session-end\\.py\"",
      "message": "The Claude manifest must retain the single exit coordinator."
    },
    {
      "path_glob": "commands/sessielog.md",
      "pattern": "kb-session-log\\.py.*--session-log",
      "message": "The native sessielog workflow must invoke its mechanical coordinator once."
    }
  ],
  "llm_judge": false
}
```

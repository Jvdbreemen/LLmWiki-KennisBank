---
id: TASK-35
title: Coordinate KennisBank session lifecycle across clients
status: In Progress
assignee:
  - Codex
created_date: '2026-07-19 15:49'
labels:
  - hooks
  - claude
  - codex
  - copilot
  - sessielog
  - documentation
  - release
dependencies: []
references:
  - 'https://developers.openai.com/codex/'
  - 'https://docs.github.com/en/copilot/reference/hooks-configuration'
  - 'https://docs.anthropic.com/en/docs/claude-code/hooks'
documentation:
  - README.md
  - CONFIGURATION.md
  - docs/agent-integrations.md
  - docs/adr/ADR-006-coordinate-sessionstart-work-behind-one-client-hook.md
  - >-
    docs/adr/ADR-007-coordinate-session-logging-and-exit-work-behind-one-client-hook.md
priority: high
ordinal: 53000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Supersede the v0.16 hookless Codex/Copilot policy with one fail-open SessionStart and one exit coordinator per Claude Code, Codex, and Copilot. Run independent work concurrently with deterministic phase ordering, keep routine output silent, preserve unrelated hooks, and give the native sessielog workflow one deterministic mechanical post-save helper. Ship as v0.17.0.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Exactly one KennisBank SessionStart and one exit coordinator are installed for Claude Code, Codex, and Copilot.
- [ ] #2 Legacy KennisBank lifecycle fan-out is removed deterministically while unrelated hooks and explicit KENNISBANK_VAULT configuration are preserved.
- [ ] #3 Exit capture completes before independent follow-up; concurrent work, timeouts, silent routine output, local diagnostics, and fail-open behavior are covered by tests.
- [ ] #4 The native sessielog workflow retains agent semantic judgment and invokes one deterministic mechanical post-save coordinator.
- [ ] #5 README, configuration, integration, troubleshooting, changelog, and MADR records explain the policy change and client UI boundary.
- [ ] #6 A green PR is merged and v0.17.0 is tagged and published, then the real Kluis deployment validates all three clients.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Rebase on v0.16.3; supersede ADR-005 with ADR-006 and add ADR-007; implement start, exit, and sessielog coordination; migrate three clients; test focused, broad, setup, and real-vault paths; merge and publish v0.17.0.
<!-- SECTION:PLAN:END -->

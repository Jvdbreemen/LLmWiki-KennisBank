---
id: TASK-36
title: Coordinate KennisBank session lifecycle across clients
status: Done
assignee:
  - Codex
created_date: '2026-07-19 16:10'
updated_date: '2026-07-19 16:22'
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
ordinal: 54000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Supersede the v0.16 hookless Codex/Copilot policy with one fail-open SessionStart and one exit coordinator per Claude Code, Codex, and Copilot. Run independent work concurrently with deterministic phase ordering, keep routine output silent, preserve unrelated hooks, and give the native sessielog workflow one deterministic mechanical post-save helper. Ship as v0.17.1 after the independently published v0.17.0 release.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Exactly one KennisBank SessionStart and one exit coordinator are installed for Claude Code, Codex, and Copilot.
- [x] #2 Legacy KennisBank lifecycle fan-out is removed deterministically while unrelated hooks and explicit KENNISBANK_VAULT configuration are preserved.
- [x] #3 Exit capture completes before independent follow-up; concurrent work, timeouts, silent routine output, local diagnostics, and fail-open behavior are covered by tests.
- [x] #4 The native sessielog workflow retains agent semantic judgment and invokes one deterministic mechanical post-save coordinator.
- [x] #5 README, configuration, integration, troubleshooting, changelog, and MADR records explain the policy change and client UI boundary.
- [x] #6 A green PR is merged and v0.17.1 is tagged and published, then the real Kluis deployment validates all three clients.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Rebase on released v0.17.0; supersede ADR-005 with ADR-006 and add ADR-007; implement start, exit, and sessielog coordination; migrate Claude Code, Codex, and Copilot; test focused, broad, setup, and real-vault paths; merge and publish v0.17.1.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implementation and documentation complete on top of v0.17.0. ADR-006 supersedes ADR-005; ADR-007 records exit and sessielog coordination. Verification: strict ADR gates pass; focused coordinator/integration tests pass; broad suite passes (769 passed, 2 skipped); setup deployment tests previously pass (5 passed); real Kluis setup reports 110 PASS and only the pre-existing provenance-lint failure; install-agent-envs validation PASS; exact live start/exit entry counts are one per Claude/Codex/Copilot; freshness rerun is silent (357 ms, 0 stdout/stderr); live sessielog coordinator returns ok.

PR #44 merged as b5d5a10. Release v0.17.1 was published from that merge commit and verified non-draft/non-prerelease. The deployed Kluis manifest matches the released source hash and install-agent-envs validation remains PASS.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Coordinated KennisBank lifecycle automation across Claude Code, Codex, and GitHub Copilot CLI. Added one fail-open start and exit coordinator per client, concurrent maintenance with deterministic phase ordering, silent routine output, local diagnostics, and a mechanical sessielog post-save coordinator. Deterministically removes legacy lifecycle fan-out while preserving unrelated hooks and the configured vault. Updated MADR decisions and all user-facing integration documentation. Verification: GitHub CI passed twice; broad suite 769 passed/2 skipped; focused gate 81 passed; setup slice 5 passed; live Kluis deployment and silent freshness path validated. Released as v0.17.1.
<!-- SECTION:FINAL_SUMMARY:END -->

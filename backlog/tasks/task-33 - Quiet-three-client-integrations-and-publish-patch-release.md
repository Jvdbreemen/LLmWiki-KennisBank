---
id: TASK-33
title: Quiet three-client integrations and publish patch release
status: In Progress
assignee:
  - Codex
created_date: '2026-07-19 10:56'
updated_date: '2026-07-19 11:45'
labels:
  - hooks
  - claude
  - codex
  - copilot
  - documentation
  - release
dependencies: []
documentation:
  - README.md
  - CONFIGURATION.md
  - docs/agent-integrations.md
modified_files:
  - scripts/kb-retrieve.py
  - scripts/kb-presearch.py
  - scripts/memory-notify.py
  - scripts/distill-notify.py
  - scripts/register-hooks.py
  - scripts/install-agent-envs.py
  - scripts/_copilot.py
  - skills
  - README.md
  - README.nl.md
  - CONFIGURATION.md
  - docs/agent-integrations.md
  - CHANGELOG.md
  - tests
priority: high
ordinal: 51000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make KennisBank quiet on successful background activity across Claude Code, Codex, and GitHub Copilot CLI while preserving model-only retrieval context and actionable warnings. Standardize shipped skill descriptions in English, remove unsupported-client references from active product surfaces, update documentation for the three supported integrations, validate installation behavior, and publish a patch release.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 All shipped KennisBank skill descriptions and generated Codex prompt descriptions are valid English metadata.
- [x] #2 Claude Code retrieval and notification hooks use structured model-only context with maximum supported output suppression, omit routine status messages, remain fail-open, and surface only actionable warnings.
- [x] #3 Codex and Copilot integrations remain silent on routine success; hook capture, MCP registration, and skill discovery remain functional and fail-open.
- [x] #4 Regression tests cover quiet hook envelopes, English metadata, three-client installer output, fail-open behavior, and documentation contracts.
- [x] #5 Focused tests, full repository tests, setup validation, and live installed-vault validation pass without modifying personal vault content unexpectedly.
- [ ] #6 A patch version is merged to upstream main through a green pull request, tagged on the merged commit, and published as an upstream GitHub Release for automatic upgrades.
- [x] #7 README, CONFIGURATION, integration documentation, installers, and runtime help prominently document Claude Code, Codex, and GitHub Copilot CLI; OpenCode remains supported and Cursor product references are removed.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Audit skill metadata, hook payloads, generated client configs, documentation, and release/version mechanisms from origin/main. 2. Convert non-English skill and generated prompt descriptions to English. 3. Add suppressOutput to Claude/Codex structured context envelopes; silence routine lifecycle commands; remove routine statusMessage fields; preserve actionable model context and fail-open behavior; silence Copilot hook stdout/stderr. 4. Remove Cursor product references and prominently document Claude Code, Codex, and GitHub Copilot CLI while preserving existing OpenCode support. 5. Add deterministic regression tests and run focused/full/setup/live validation against the explicit Kluis vault path. 6. Bump the patch release, push to the fork, merge a green upstream PR, tag the upstream merged commit, publish the upstream GitHub Release, and finalize the task.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented fail-open quiet-hook.py for routine Claude/Codex/Copilot lifecycle commands; added suppressOutput to retrieval and actionable notification envelopes; installers remove KennisBank-owned statusMessage fields; translated shipped skill and generated prompt metadata to English; updated English/Dutch README, configuration, and integration docs; removed obsolete product references. Focused regression set: 96 passed, 1 skipped; setup deployment smoke passed. Full suite is running before release.

User clarified that suppression must preserve useful KennisBank reporting. Implemented relevance-aware quiet-hook behavior: routine no-change maintenance is silent; changed index counts and warnings become structured session context; retrieval hits and actionable notices remain structured context; Copilot uses its native sessionStart additionalContext output.

Validation evidence: focused hook/client tests 96 passed, 1 skipped; complete non-deployment suite 752 passed, 2 skipped; real setup deployment smoke passed; live setup against KENNISBANK_VAULT=D:/Users/Robert/Documents/Claude/Projects/Kluis validated Claude, Codex, and Copilot configs, MCP tool registration, Copilot v1.0.71 visibility, and quiet/relevant output behavior. Live doctor reported only two pre-existing vault-content findings: 13 unverified memories older than 48h and 2 wiki articles with dangling provenance; personal content was intentionally not mutated. Direct live probes confirmed no-change index output is empty, notification context is suppressed/structured, and retrieval returns relevant structured results.
<!-- SECTION:NOTES:END -->

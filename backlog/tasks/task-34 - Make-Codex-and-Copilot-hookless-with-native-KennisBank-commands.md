---
id: TASK-34
title: Make Codex and Copilot hookless with native KennisBank commands
status: Done
assignee:
  - Codex
created_date: '2026-07-19 15:11'
updated_date: '2026-07-19 15:16'
labels: []
dependencies: []
modified_files:
  - scripts/install-agent-envs.py
  - scripts/_copilot.py
  - README.md
  - README.nl.md
  - CONFIGURATION.md
  - docs/agent-integrations.md
  - docs/adr/ADR-005-hookless-codex-copilot-integration.md
priority: high
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Suppress client-rendered lifecycle progress/completion rows by removing KennisBank hooks from Codex and Copilot and replacing automatic session workflows with native skills plus MCP. Preserve unrelated hooks and document the explicit-session trade-off.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Fresh Codex and Copilot installs create no KennisBank lifecycle hooks.
- [x] #2 Upgrade removes only legacy KennisBank hooks and preserves unrelated entries.
- [x] #3 Codex installs sessiestart/sessielog skills plus prompt compatibility aliases; Copilot exposes native slash-command skills.
- [x] #4 README, configuration, integration, troubleshooting, changelog, and MADR explain the suppression boundary and trade-off.
- [x] #5 Focused integration tests, setup validation, and ADR gates pass.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Implement selective hook migration and generated command skills; update validation and doctor; document and accept ADR-005; verify, commit, push, merge, and release v0.16.2.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented hookless Codex/Copilot installs with selective removal, generated command skills, updated validation/doctor, English and Dutch docs, and accepted MADR ADR-005. Verification: 50 passed + 1 skipped focused integration slice; 276 passed + 1 skipped a-h batch; 270 passed + 1 skipped i-m after documentation fix; 104 passed n-z excluding long setup deploy; changed setup path smoke passed; ADR gates had 0 failures (one advisory for no numeric consequence metric). Full monolithic suite exceeds the local command timeout because test_setup_deploy repeatedly runs setup; deterministic batches isolate it.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented and verified hookless KennisBank integrations for Codex and Copilot. Setup installs native sessiestart/sessielog command skills plus MCP, selectively removes legacy KennisBank hooks while preserving unrelated hooks, and updates validation, doctor, README, configuration, integration, troubleshooting, changelog, and accepted MADR ADR-005. GitHub CI passed the full suite.
<!-- SECTION:FINAL_SUMMARY:END -->

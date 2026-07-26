---
id: TASK-82
title: 'Agent install guide: per-platform instructions and README entry point'
status: Done
assignee: []
created_date: '2026-07-26 18:07'
updated_date: '2026-07-26 18:12'
labels:
  - docs
dependencies: []
priority: medium
ordinal: 92000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Write docs/AGENT-INSTALL.md: a guide written FOR coding agents that install KennisBank, with per-platform instructions for Claude Code, Claude Cowork, Codex and GitHub Copilot CLI. Link it prominently at the top of README.md (and README.nl.md) so an agent that lands on the repo finds the install path instantly. English per the language policy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 docs/AGENT-INSTALL.md covers Claude Code, Claude Cowork, Codex and Copilot CLI with concrete commands per platform
- [x] #2 README.md and README.nl.md link the guide in the opening section
- [x] #3 Claims about Claude Cowork integration verified against current documentation, uncertainty labelled
- [x] #4 Docs-consistency tests green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Merged via PR #76 (1980f95 on origin/main). docs/AGENT-INSTALL.md covers Claude Code, Codex, Copilot CLI, OpenCode and Claude Cowork with per-platform commands and a capability matrix; the Cowork section is verified against the Claude Desktop 3P extensions docs (2026-07) and honestly states that hooks do not exist there (MCP/skills/plugins only). Both READMEs link the guide in their opening lines. CI green; Copilot review unavailable (quota) — docs-only change.
<!-- SECTION:FINAL_SUMMARY:END -->

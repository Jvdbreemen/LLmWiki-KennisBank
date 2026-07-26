---
id: TASK-82
title: 'Agent install guide: per-platform instructions and README entry point'
status: In Progress
assignee: []
created_date: '2026-07-26 18:07'
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
- [ ] #1 docs/AGENT-INSTALL.md covers Claude Code, Claude Cowork, Codex and Copilot CLI with concrete commands per platform
- [ ] #2 README.md and README.nl.md link the guide in the opening section
- [ ] #3 Claims about Claude Cowork integration verified against current documentation, uncertainty labelled
- [ ] #4 Docs-consistency tests green
<!-- AC:END -->

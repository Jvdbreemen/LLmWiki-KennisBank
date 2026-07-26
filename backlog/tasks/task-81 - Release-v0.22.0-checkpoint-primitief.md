---
id: TASK-81
title: 'Release v0.22.0: checkpoint-primitief'
status: Done
assignee: []
created_date: '2026-07-26 15:28'
updated_date: '2026-07-26 15:43'
labels:
  - release
milestone: Agent-geheugen
dependencies: []
priority: high
ordinal: 91000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Release volgens skills/kennisbank-release/SKILL.md. Draagt TASK-78 (build-graph-index in worker-jobs) en TASK-79 (checkpoint-primitief + toggle-oppervlakken-fixes). Minor: feat-commit in de delta.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
v0.22.0 released: tag on verified origin/main SHA 52f3274, GitHub release published with non-empty notes (3838 chars). PR #75 (fork → upstream), CI green after fixing a pytest-only expectation in tests/test_session_start.py (local unittest discover does not collect function-style tests — recorded as a lesson). Copilot review unavailable on both PRs (quota limit); substituted a local code-review agent on the feature PR and noted it here. The release also introduces the English-by-default documentation policy (top of AGENTS.md and CLAUDE.md).
<!-- SECTION:FINAL_SUMMARY:END -->

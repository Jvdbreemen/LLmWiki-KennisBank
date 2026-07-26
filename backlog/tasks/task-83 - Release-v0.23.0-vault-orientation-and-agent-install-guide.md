---
id: TASK-83
title: 'Release v0.23.0: vault orientation and agent install guide'
status: Done
assignee: []
created_date: '2026-07-26 19:18'
updated_date: '2026-07-26 19:24'
labels:
  - release
dependencies: []
priority: high
ordinal: 93000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Release per skills/kennisbank-release/SKILL.md. Carries TASK-80 (vault orientation at session start, opt-in toggle), TASK-82 (agent install guide + README entry points) and the test-isolation fix in test_activity_multilang.py. Minor: feat commits in the delta.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
v0.23.0 released and deployed. PR #78 merged (271ba10 verified on origin/main), tag v0.23.0 on that SHA, GitHub release published (notes 1430 chars, non-empty verified). Vault upgraded via setup.sh (doctor 126 PASS / 1 FAIL — the pre-existing provenance-lint issue), version stamp updated. Smoke test: kb-orientation.py returns the summary in the deployed vault and the orientation toggle reads 1. Copilot review unavailable on the release PR (quota); docs-only delta, CI green.
<!-- SECTION:FINAL_SUMMARY:END -->

---
id: TASK-57
title: Research cross-client hooks and plugin architecture for KennisBank
status: Done
assignee: []
created_date: '2026-07-19 17:43'
updated_date: '2026-07-19 18:00'
labels:
  - research
  - plugins
  - hooks
  - cross-client
dependencies: []
references:
  - 'https://github.com/kilo-org/kilocode'
  - 'https://kilo.ai/docs/automate/extending/plugins'
  - 'https://learn.chatgpt.com/docs/hooks'
  - 'https://code.claude.com/docs/en/hooks'
  - 'https://docs.github.com/en/copilot/reference/hooks-reference'
modified_files:
  - docs/research/cross-client-hooks-plugin-architecture.md
priority: high
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create a KennisBank-owned report from the cross-client agent research. Cover memory retrieval, transcript capture, subagent and compaction hooks, Stop and SessionEnd behavior, hard-exit recovery, latency budgets, fail-open design, wiki publication, plugin packaging, installer/update/doctor implications, and Kilo Code. Keep ADR Kit implementation scope out of this repository report.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Report is stored in the KennisBank repository and clearly identifies KennisBank as the product scope.
- [x] #2 Hook-by-hook analysis covers retrieval, capture, compaction, subagents, Stop, SessionEnd, raw transcripts, and hard-exit recovery.
- [x] #3 Performance budgets and fail-open behavior distinguish synchronous hot paths from queued processing.
- [x] #4 Client assessment includes current supported environments plus Kilo Code and separates full candidates from partial compatibility.
- [x] #5 Report proposes packaging, idempotent installation, updates, doctor checks, privacy controls, and phased next steps without changing runtime behavior.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Separate the KennisBank lifecycle and plugin analysis from ADR Kit; define normalized events, hot/warm/cold paths, hook-by-hook behavior, hard-exit recovery, raw capture versus wiki publication, latency, client matrix, Kimi/Kilo assessments, installer/update/doctor requirements, privacy choices, and phased follow-up.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Created docs/research/cross-client-hooks-plugin-architecture.md. The report preserves the explicit KENNISBANK_VAULT rule and fail-open posture, includes supported Claude/Codex/OpenCode/Copilot plus expansion candidates, and adds official Kimi and Kilo analysis. Kilo evidence: current CLI/VS Code plugin API, Agent Skills, Markdown workflows, AGENTS.md, MCP, versioned plugin/update/uninstall, 26.4k stars, current release. Verification: git diff --check clean; scope headings and all required lifecycle sections present. No runtime behavior changed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added a KennisBank-owned cross-client hooks and plugin architecture report. It covers bounded retrieval, capture, compaction, subagents, Stop/SessionEnd, hard-exit recovery, raw transcript provenance, cold wiki publication, latency budgets, fail-open semantics, client support assessment, Kimi/Kilo expansion, idempotent setup/update/rollback, doctor, privacy policy, and phased implementation direction. Documentation only.
<!-- SECTION:FINAL_SUMMARY:END -->

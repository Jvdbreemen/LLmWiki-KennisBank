---
id: TASK-226
title: Freeze the v1 production contract and amend ADR-010 evidence
status: To Do
assignee: []
created_date: '2026-09-04 00:00'
labels:
  - architecture
  - adr
  - production
  - evidence
dependencies:
  - TASK-225
ordinal: 176500
---

## Description

Convert the experiment result into a versioned product contract before
implementation. Amend ADR-010's proposal and evidence sections to select only
explicit experience recall plus exact source hydration and lexical source
search. Preserve its Proposed lifecycle state until the final owner decision.

Record which operational ideas are adopted from comparable systems such as
Supamem (temporal validity, rebuildable indexes, central filters, explicit
tools, doctor/migration support) and which are rejected (one mixed collection,
unreviewed agent-written lessons, source pre-embedding, and automatic recall
injection).

## Acceptance Criteria

- [ ] #1 ADR-010 names the selected v1 scope and the rejected source-vector/advisory paths without rewriting historical evidence
- [ ] #2 The ADR stays Proposed and non-binding until TASK-237
- [ ] #3 API, storage, SourceRef, lifecycle, privacy, feature-flag, migration, rollback, and observability contracts are versioned
- [ ] #4 Every must/must-not rule maps to at least one planned test
- [ ] #5 No claim presents the spent holdouts as reusable independent evidence
- [ ] #6 ADR context identifies ADR-008 and ADR-009 as governing constraints and this is recorded

## Evidence

Add exact file links, ADR context output summary, and contract review notes here
when complete.

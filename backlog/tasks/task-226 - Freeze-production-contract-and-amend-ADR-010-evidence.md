---
id: TASK-226
title: Freeze the v1 production contract and amend ADR-010 evidence
status: Done
assignee: []
created_date: '2026-09-04 00:00'
updated_date: '2026-09-04 00:00'
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

- [x] #1 ADR-010 names the selected v1 scope and the rejected source-vector/advisory paths without rewriting historical evidence
- [x] #2 The ADR stays Proposed and non-binding until TASK-237
- [x] #3 API, storage, SourceRef, lifecycle, privacy, feature-flag, migration, rollback, and observability contracts are versioned
- [x] #4 Every must/must-not rule maps to at least one planned test
- [x] #5 No claim presents the spent holdouts as reusable independent evidence
- [x] #6 ADR context identifies ADR-008 and ADR-009 as governing constraints and this is recorded

## Evidence

The v1 contract is frozen in
`docs/superpowers/plans/2026-09-04-source-grounded-experience-production.md`.
It defines the API, stores, SourceRef v1, validation lifecycle, flags,
migration, rollback, observability, test order, release gates, canary, and
parallel dependency graph. Its Supamem section records adopted operational
patterns and rejected mixed-authority/automatic-injection patterns.

ADR-010 remains `Proposed`, `binding: false`; its gate now points at TASK-236
and TASK-237 retains owner lifecycle authority. The amendment preserves the
original experiment proposal and adds the measured narrowing: explicit
reviewed experience recall, exact source-on-demand hydration, and lexical-only
free source search. It explicitly rejects automatic advisories and source
vectors for v1.

The local ADR-context fallback ranked ADR-010 primary and returned Accepted
ADR-008 and ADR-009 as governing supporting decisions. The generated
`ADR-INDEX.json` was absent, so the result was correctly labelled Markdown
compatibility fallback rather than presented as indexed retrieval. ADR lint's
Completeness, Evidence, Clarity, and Consistency gates reported zero failures;
the unresolved production and longitudinal questions remain advisory while the
record is Proposed.

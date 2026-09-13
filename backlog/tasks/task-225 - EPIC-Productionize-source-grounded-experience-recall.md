---
id: TASK-225
title: 'EPIC: Productionize source-grounded experience recall'
status: In Progress
assignee: []
created_date: '2026-09-04 00:00'
updated_date: '2026-09-08 05:13'
labels:
  - epic
  - experience-memory
  - source-recall
  - production
  - evaluation
dependencies:
  - TASK-211
  - TASK-223
  - TASK-224
ordinal: 176400
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Turn the successful part of the source/experience experiment into a bounded
production feature. Ship explicit, validated experience recall followed by
on-demand exact source hydration. Retain explicit lexical source search, but do
not ship source-vector reranking, automatic advisories, automatic source
fallback, mixed ranking, outcome boosts, or skill promotion.

The executable design is
`docs/superpowers/plans/2026-09-04-source-grounded-experience-production.md`.
ADR-010 remains Proposed until every production gate passes and the owner
explicitly accepts or amends it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria

- [ ] #1 TASK-226 through TASK-237 are completed or explicitly rejected with evidence
- [ ] #2 Raw sources, canonical experience ledger, source projection, experience projection, and existing wiki/memory index have separate ownership and recovery paths
- [ ] #3 Experience recall exposes only reviewed, evidence-verified records and returns resolvable SourceRef ids
- [ ] #4 Source recall supports exact SourceRef hydration and labelled lexical search without vectors
- [ ] #5 Automatic advisory, source fallback, mixed ranking, outcome boost, and promotion are absent from the public v1 route
- [ ] #6 Normal recall is byte/shape compatible and adds no more than 1 ms p95 overhead when the new routes are unused
- [ ] #7 Migration, doctor, setup, cross-client smoke tests, privacy checks, canary, and rollback all pass
- [ ] #8 ADR-010 receives an explicit owner lifecycle decision before release to main

## Definition of Done

- [ ] #1 Every child task contains focused test evidence and the full suite is green
- [ ] #2 The owner-vault canary meets the preregistered quality and safety gates
- [ ] #3 Release occurs through the normal reviewed release workflow from this feature branch

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
2026-09-08 execution: repair projection authority under TASK-239 with test-first evidence; process TASK-209 and TASK-210 in disjoint parallel work; rebuild only owner-reviewed shadow corpus; obtain current full/client/rollback proof; collect prospective explicit-use reviews without recycling spent holdouts; request owner ADR/release decision only after all prerequisite gates pass.
<!-- SECTION:PLAN:END -->

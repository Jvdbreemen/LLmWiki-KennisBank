---
id: TASK-212
title: Source recall and experience architecture contract and schemas
status: To Do
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-25 00:00'
labels:
  - memory
  - source-recall
  - experience-memory
  - architecture
dependencies: []
ordinal: 175100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Write the architecture contract before adding code. Define the boundaries and
schemas for raw evidence, source recall, current memory/wiki, episodes,
outcomes, experience lessons, procedures, and skills.

The design must decide, with reasons, whether experience records live in a new
projection such as `10-experience/` or in a namespaced part of the existing
memory layer. The preferred design is a distinct experience projection because
an outcome-linked lesson is not the same object as an unvalidated fact. Raw
source files remain the authority; Markdown/JSONL or equivalent event records
remain inspectable; SQLite/vector tables are derived indexes only.

Define the lifecycle:

    observed -> candidate -> validated -> superseded/retracted
                         \-> unknown

Define the minimum experience schema: task/work-unit, session, goal,
situation, approach, actions, observed result, outcome state, evidence refs,
source refs, memory refs, applicability scope, confidence, attribution
strength, extractor version, and evaluation status.

Define the source schema: stable source id, path, hash, session, document and
chunk identity, offsets, timestamps, project/client/role metadata, redaction
status, embedding model and index version.

Record the distinctions that implementation must preserve:

- observation is not interpretation;
- exposure is not use;
- use is not helpfulness;
- session outcome is not item causality;
- a successful commit/test is evidence, not proof of user value;
- `unknown` is preferable to a guessed label;
- a raw source citation cannot be replaced by a generated summary.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A design document and, where repository practice requires it, an ADR describe the target data flow and ownership of every layer
- [ ] #2 Source, episode, outcome, experience, procedure, and skill schemas are written with required fields, optional fields, status values, and versioning rules
- [ ] #3 The document defines exact provenance and retraction behaviour for every derived record
- [ ] #4 The document defines how task/work-unit boundaries are represented when one session contains multiple tasks
- [ ] #5 The document explicitly rejects a single scalar success score as the initial outcome model
- [ ] #6 Storage, rebuild, retention, privacy, redaction, and fail-open decisions are recorded
- [ ] #7 The design maps each schema to existing scripts, hooks, indexes, tests, and relevant backlog tasks
<!-- AC:END -->

## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
Research must include the accepted/rejected lessons from Reflexion, ExpeL,
ReasoningBank, ProjectMem, SWE-Exp, Memp, EverOS, Hindsight, EverMemOS, and the
warning that continuous LLM consolidation can damage useful memory. Do not copy
third-party code or introduce a hosted memory dependency.
<!-- SECTION:NOTES:END -->


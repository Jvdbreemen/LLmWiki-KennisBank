---
id: TASK-232
title: Build production explicit experience recall with lexical fallback
status: To Do
assignee: []
created_date: '2026-09-04 00:00'
labels:
  - experience-memory
  - retrieval
  - fail-open
  - production
dependencies:
  - TASK-230
  - TASK-231
ordinal: 177100
---

## Description

Create the production read path over the small, reviewed experience projection.
Use hybrid FTS+dense retrieval when the approved local embedding model is
available and a labelled FTS fallback otherwise. Return lessons and SourceRef
ids, not raw source passages.

## Planned Files

- update `scripts/_experience.py`
- update `scripts/kb-experience-recall.py`
- update `scripts/build-experience-index.py`
- extend experience retrieval and contract tests

## Acceptance Criteria

- [ ] #1 Only validated, evidence-verified, owner-accepted records are searchable
- [ ] #2 Public API accepts explicit mode only; failure advisory mode is unavailable
- [ ] #3 Results are capped at three and diversified by source/task to avoid duplicate lessons
- [ ] #4 Response includes applicability, attempt/resolution/outcome states, validation stamp, scores, retrieval route, and SourceRef ids
- [ ] #5 Missing Ollama or incompatible vector metadata yields labelled FTS fallback, not an exception or false hybrid claim
- [ ] #6 No raw passage is returned until source recall is explicitly invoked
- [ ] #7 Locked regression hit@3 is >= 0.85, evidence precision is 1.00, and no thresholds are tuned on the spent set
- [ ] #8 Warm explicit p95 is <= 250 ms on reference hardware

## Evidence

Record focused retrieval tests, locked-regression aggregate, fallback smoke,
and latency distribution without private query text.

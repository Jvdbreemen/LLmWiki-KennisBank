---
id: TASK-232
title: Build production explicit experience recall with lexical fallback
status: Done
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

- [x] #1 Only validated, evidence-verified, owner-accepted records are searchable
- [x] #2 Public API accepts explicit mode only; failure advisory mode is unavailable
- [x] #3 Results are capped at three and diversified by source/task to avoid duplicate lessons
- [x] #4 Response includes applicability, attempt/resolution/outcome states, validation stamp, scores, retrieval route, and SourceRef ids
- [x] #5 Missing Ollama or incompatible vector metadata yields labelled FTS fallback, not an exception or false hybrid claim
- [x] #6 No raw passage is returned until source recall is explicitly invoked
- [x] #7 Locked regression hit@3 is >= 0.85, evidence precision is 1.00, and no thresholds are tuned on the spent set
- [x] #8 Warm explicit p95 is <= 250 ms on reference hardware

## Evidence

Record focused retrieval tests, locked-regression aggregate, fallback smoke,
and latency distribution without private query text.

- Focused production suite: 74 passed; the one deselected red contract is the
  TASK-233 settings split, not experience retrieval behavior.
- Locked reviewed regression: hit@3 1.00, evidence precision 1.00, zero
  candidate leakage and zero false warnings. This is a small synthetic
  regression guard, not the frozen value holdout.
- Warm end-to-end synthetic gateway, 100 measured runs per route: hybrid p95
  6.338 ms; lexical fallback p95 5.375 ms (budget 250 ms).
- Embedding-failure smoke publishes a complete FTS projection without a
  `vec_docs` table and reports the failed embedding ids.
- Configured owner vault had no experience stores; no canary was possible. The
  private frozen holdout remains unopened and unspent.
- Detailed record: `docs/research/experience-production-recall-evidence-2026-09-06.md`.

---
id: TASK-223
title: Evaluate sparse-first source recall with on-demand vector reranking
status: To Do
assignee: []
created_date: '2026-08-29 00:00'
labels:
  - source-recall
  - evaluation
  - performance
  - provenance
dependencies:
  - TASK-213
  - TASK-215
  - TASK-220
ordinal: 176200
---

## Description

Replace the unproven assumption that every raw chunk must be pre-embedded with
a measured sparse-first candidate path. Use the full-corpus FTS/BM25 index to
select documents or passages, embed only bounded candidates on demand, cache
those embeddings by exact body hash and model id, and rerank without losing
exact provenance.

The experiment must use a separate development set for thresholds and then run
the frozen private source holdout once. It must compare full-corpus lexical,
sparse-first hybrid, and the existing vector-index design where operationally
feasible. Do not tune on the reviewed holdout.

## Acceptance Criteria

- [ ] #1 Candidate generation and reranking retain exact source path, hash, and passage offsets
- [ ] #2 On-demand embeddings are content-addressed, model-stamped, persistent, and invalidated safely
- [ ] #3 Full-corpus hit@5 improves lexical 0.66 by at least 0.10 or records a rejection
- [ ] #4 No-hit specificity is at least 0.95 on untouched negatives
- [ ] #5 Warm p95 remains below 2 seconds and build/storage costs are reported against the 1.105 GB FTS baseline
- [ ] #6 Paired answer correctness is measured on at least 50 reviewed source cases
- [ ] #7 Evaluation writes no production usage telemetry and cannot replace a known-good index on failure
- [ ] #8 The result explicitly chooses sparse-first, full-vector, lexical-only, or reject

## Evidence baseline

The 2026-08-29 packet measured full-corpus lexical hit@5 0.66, candidate
coverage 0.76 at 20, 0.84 at 50, and 0.88 at 100. The approved corpus is
781,127,644 bytes; only the 28 expected documents already produce 37,085
2,000/200 chunks. These measurements justify this bounded experiment and do
not justify a full pre-embedding build.

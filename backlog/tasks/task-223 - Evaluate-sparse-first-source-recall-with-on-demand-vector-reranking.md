---
id: TASK-223
title: Evaluate sparse-first source recall with on-demand vector reranking
status: Done
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

- [x] #1 Candidate generation and reranking retain exact source path, hash, and passage offsets
- [x] #2 On-demand embeddings are content-addressed, model-stamped, persistent, and invalidated safely
- [x] #3 Full-corpus hit@5 improves lexical 0.66 by at least 0.10 or records a rejection
- [ ] #4 No-hit specificity is at least 0.95 on untouched negatives
- [ ] #5 Warm p95 remains below 2 seconds and build/storage costs are reported against the 1.105 GB FTS baseline
- [ ] #6 Paired answer correctness is measured on at least 50 reviewed source cases
- [x] #7 Evaluation writes no production usage telemetry and cannot replace a known-good index on failure
- [x] #8 The result explicitly chooses sparse-first, full-vector, lexical-only, or reject

## Evidence baseline

The 2026-08-29 packet measured full-corpus lexical hit@5 0.66, candidate
coverage 0.76 at 20, 0.84 at 50, and 0.88 at 100. The approved corpus is
781,127,644 bytes; only the 28 expected documents already produce 37,085
2,000/200 chunks. These measurements justify this bounded experiment and do
not justify a full pre-embedding build.

## Final evidence and decision

The implementation contracts cover exact byte-derived hashes and character
offsets, stale-FTS rejection, model-stamped float32 cache records, bounded
candidate heaps, private write-once reports, and disabled usage telemetry. The
focused sparse suite passes 28 tests.

The owner reviewed an independent 30-case development set: 20 positives over
20 unique source documents and 10 hard negatives. It has no id, normalized
query, or expected-source overlap with the 60 frozen cases. Live source hashes,
reviewed windows, and FTS body snapshots were validated before model work.

All 18 preregistered configurations failed the development constraints. The
best available point used 100 candidate documents, 40 passages, and cosine
0.70. It measured hit@5 0.25, passage hit@5 0.15, citation precision 0.40,
no-hit specificity 0.90, and warm p95 8,332 ms. Its shared content-addressed
calibration cache was 33,939,456 bytes versus the 1,105,334,272-byte lexical
index. Pure BM25 on the same development set measured hit@5 0.75 and p95
50.4 ms, but no-hit precision 0.00.

The decision is **reject sparse-first vector reranking**. It loses 0.50 hit@5
to the lexical development baseline, misses both the specificity and latency
gates, and therefore did not earn the one-shot frozen holdout or the 50-case
paired answer benchmark. AC #4, #5, and #6 remain visibly unchecked for that
reason. Running those downstream evaluations after a development pre-reject
would spend the holdout and collect answer labels for a candidate already
disqualified by its safety, retrieval, and latency gates. Full-corpus
pre-embedding remains rejected on operational grounds; lexical-only remains a
labelled explicit evidence-search baseline, not a safe automatic no-hit route.

Aggregate evidence is documented in
`docs/research/source-sparse-development-result-2026-08-31.md`; private reports
remain outside the repository.

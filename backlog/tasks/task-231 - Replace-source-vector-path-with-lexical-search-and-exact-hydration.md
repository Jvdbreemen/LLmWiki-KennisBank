---
id: TASK-231
title: Replace the source vector path with lexical search and exact hydration
status: Done
assignee: []
created_date: '2026-09-04 00:00'
labels:
  - source-recall
  - fts
  - performance
  - provenance
dependencies:
  - TASK-228
ordinal: 177000
---

## Description

Turn source recall into the product path supported by evidence: deterministic
SourceRef hydration plus explicit FTS/BM25 evidence search. Remove embeddings,
vector tables, sparse reranking, and automatic fallback from the public v1
source route.

## Planned Files

- refactor `scripts/_source_recall.py`
- refactor `scripts/build-source-index.py`
- update `scripts/kb-source-recall.py`
- update source command, MCP wrapper, doctor, and tests

## Acceptance Criteria

- [x] #1 `reconstruct` resolves SourceRef directly without embedding or ranking
- [x] #2 `explicit` free search uses FTS/BM25 only and is labelled best-effort evidence search
- [x] #3 `verify` reuses the same resolver and exposes stale/conflict/current state
- [x] #4 Public `fallback` mode is rejected and cannot influence normal recall
- [x] #5 Source build creates no vector table and invokes no embedding backend
- [x] #6 Every hit has exact path/hash/offset/passage-hash provenance and clear freshness state
- [x] #7 Warm FTS p95 is <= 250 ms and exact hydration p95 <= 50 ms on reference hardware
- [x] #8 Existing frozen source holdout remains unspent and is not used for tuning

## Evidence

Record schema inspection proving no source vectors, focused test output, and
latency measurements against synthetic and configured local indexes.

- Configured-vault scale run: 16,286 sources, 490,317 chunks, zero failed
  sources/chunks, SQLite integrity `ok`, and no vector-like tables.
- Published source index size: 2,410.5 MB. Streaming plus one staging
  transaction kept observed memory around 38-191 MB after scale defects in
  earlier implementations were fixed.
- Warm benchmark, 30 iterations: FTS median 40.476 ms / p95 67.385 ms; exact
  hydration median 6.330 ms / p95 11.931 ms.
- Relevant regression suite: 118 passed, 1 skipped. The source holdout was not
  opened, queried, or used for tuning.
- Detailed record: `docs/research/source-lexical-production-evidence-2026-09-06.md`.

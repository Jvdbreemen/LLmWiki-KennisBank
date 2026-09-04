---
id: TASK-231
title: Replace the source vector path with lexical search and exact hydration
status: To Do
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

- [ ] #1 `reconstruct` resolves SourceRef directly without embedding or ranking
- [ ] #2 `explicit` free search uses FTS/BM25 only and is labelled best-effort evidence search
- [ ] #3 `verify` reuses the same resolver and exposes stale/conflict/current state
- [ ] #4 Public `fallback` mode is rejected and cannot influence normal recall
- [ ] #5 Source build creates no vector table and invokes no embedding backend
- [ ] #6 Every hit has exact path/hash/offset/passage-hash provenance and clear freshness state
- [ ] #7 Warm FTS p95 is <= 250 ms and exact hydration p95 <= 50 ms on reference hardware
- [ ] #8 Existing frozen source holdout remains unspent and is not used for tuning

## Evidence

Record schema inspection proving no source vectors, focused test output, and
latency measurements against synthetic and configured local indexes.

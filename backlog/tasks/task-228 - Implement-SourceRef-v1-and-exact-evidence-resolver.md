---
id: TASK-228
title: Implement SourceRef v1 and exact evidence resolver
status: Done
assignee: []
created_date: '2026-09-04 00:00'
updated_date: '2026-09-04 00:00'
labels:
  - provenance
  - source-recall
  - security
  - schema
dependencies:
  - TASK-227
ordinal: 176700
---

## Description

Replace legacy string source references with a canonical, versioned SourceRef
object. Add deterministic ids and one resolver used by validation, source
recall, doctor, and migration. The resolver must never silently retarget a ref
after source content changes.

## Planned Files

- create `scripts/_source_ref.py`
- update `scripts/_source_recall.py`
- update source and experience schema helpers
- tests from TASK-227

## Acceptance Criteria

- [x] #1 SourceRef contains version, deterministic id, approved-root-relative path, source hash, chunk id, half-open offsets, offset unit, passage hash, capture time, and redaction state
- [x] #2 Resolver verifies root containment, traversal, symlink escape, source hash, bounds, and passage hash
- [x] #3 Changed, deleted, unreadable, and redacted evidence returns explicit stale/missing/redacted states
- [x] #4 Legacy strings convert only to unverified candidates until exact validation succeeds
- [x] #5 Round-trip serialization is deterministic and rejects unknown schema versions
- [x] #6 Focused tests pass with 100% exact passage integrity

## Evidence

`scripts/_source_ref.py` now owns approved roots, canonical v1 serialization,
content-addressed ids, exact creation, safe resolution, and legacy candidate
conversion. `_source_recall.py` imports the same approved-root tuple and exposes
the canonical resolver rather than maintaining another evidence path.

The synthetic contract covers Unicode codepoint offsets, exact passage
hydration, deterministic identity, source mutation, deletion, unreadable
replacement, redaction, traversal, absolute paths, unknown schema, legacy
strings, and the source-recall integration seam. Focused regression:
`37 passed, 1 skipped` across SourceRef, source recall, chunk-stamp, and source
builder tests.
The skipped test is the explicit symlink-escape fixture because this Windows
environment did not permit symlink creation; the resolver still validates the
resolved target against both vault and approved-root boundaries.

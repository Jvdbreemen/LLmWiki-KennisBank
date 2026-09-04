---
id: TASK-228
title: Implement SourceRef v1 and exact evidence resolver
status: To Do
assignee: []
created_date: '2026-09-04 00:00'
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

- [ ] #1 SourceRef contains version, deterministic id, approved-root-relative path, source hash, chunk id, half-open offsets, offset unit, passage hash, capture time, and redaction state
- [ ] #2 Resolver verifies root containment, traversal, symlink escape, source hash, bounds, and passage hash
- [ ] #3 Changed, deleted, unreadable, and redacted evidence returns explicit stale/missing/redacted states
- [ ] #4 Legacy strings convert only to unverified candidates until exact validation succeeds
- [ ] #5 Round-trip serialization is deterministic and rejects unknown schema versions
- [ ] #6 Focused tests pass with 100% exact passage integrity

## Evidence

Record focused tests and a synthetic tamper demonstration with no private
passage content.

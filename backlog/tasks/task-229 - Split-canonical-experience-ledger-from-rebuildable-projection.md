---
id: TASK-229
title: Split the canonical experience ledger from the rebuildable projection
status: To Do
assignee: []
created_date: '2026-09-04 00:00'
labels:
  - experience-memory
  - storage
  - migration
  - reliability
dependencies:
  - TASK-227
ordinal: 176800
---

## Description

Move append-only events, outcomes, and review decisions to
`kb-experience-ledger.db`; move derived searchable experiences to
`kb-experience-index.db`. Preserve the old experimental `kb-experience.db`
until a verified migration and a later explicit cleanup decision.

## Planned Files

- refactor `scripts/_experience.py`
- update `scripts/build-experience-index.py`
- create or extend projection migration helpers
- update rebuild and maintenance tests

## Acceptance Criteria

- [ ] #1 Ledger tables are canonical, append-only, versioned, and use idempotency keys
- [ ] #2 Projection can be deleted and rebuilt solely from ledger, source refs, and explicit reviews
- [ ] #3 Build uses a temporary database, integrity checks, and atomic replacement
- [ ] #4 Failed or interrupted builds preserve the previous known-good projection
- [ ] #5 Legacy migration performs preflight, backup, copy, count/hash verification, and idempotent resume
- [ ] #6 Migration never turns legacy records into validated records implicitly
- [ ] #7 Focused storage, migration, crash-recovery, and rebuild tests pass

## Evidence

Record before/after schema inventories, migration test output, and checksums of
synthetic canonical rows.

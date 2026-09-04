---
id: TASK-229
title: Split the canonical experience ledger from the rebuildable projection
status: Done
assignee: []
created_date: '2026-09-04 00:00'
updated_date: '2026-09-04 00:00'
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

- [x] #1 Ledger tables are canonical, append-only, versioned, and use idempotency keys
- [x] #2 Projection can be deleted and rebuilt solely from ledger, source refs, and explicit reviews
- [x] #3 Build uses a temporary database, integrity checks, and atomic replacement
- [x] #4 Failed or interrupted builds preserve the previous known-good projection
- [x] #5 Legacy migration performs preflight, backup, copy, count/hash verification, and idempotent resume
- [x] #6 Migration never turns legacy records into validated records implicitly
- [x] #7 Focused storage, migration, crash-recovery, and rebuild tests pass

## Evidence

`_experience.py` now defines separate ledger and projection paths and schemas.
The ledger contains only append-only events, outcomes, and review decisions;
stable primary ids act as event/outcome idempotency keys and reviews carry a
separate unique idempotency key. The projection contains derived experience,
FTS, and optional vector tables but no canonical history.

`build-experience-index.py` gained an atomic projection-only rebuild. It derives
from a read-only ledger connection, validates the staged SQLite database, and
only then swaps it into place. Deleting and rebuilding the synthetic projection
produces the same experience rows without changing the ledger bytes; an
injected derivation failure preserves the previous projection byte-for-byte.
The legacy mixed-store builder remains temporarily available for compatibility.

`_experience_migration.py` provides non-mutating preflight/dry-run plus a
content-addressed backup, staged canonical copy, backup hash verification,
per-table count verification, integrity check, atomic swap, and migration hash
for idempotent resume. It intentionally copies no legacy derived experiences,
so no old string-ref record becomes validated by migration.

Focused evidence: `41 passed` across projection boundary, migration, existing
store/extractor/recall/maintenance, and outcome-ledger tests.

---
id: TASK-238
title: Add bounded fast mode to projection doctor
status: Done
assignee: []
created_date: '2026-09-07 00:00'
labels:
  - doctor
  - performance
  - canary
  - operations
dependencies:
  - TASK-234
ordinal: 177550
---

## Description

The first owner-vault canary run exposed that the default projection doctor
hashes the complete 16,318-file (~0.82 GiB) raw-source inventory before
reporting anything. Keep the exact full mode, but add an explicit bounded mode
for routine canary health that checks SQLite integrity, schemas, flags, and
counts without touching raw source files. It must label freshness/provenance
results as not checked rather than returning misleading empty green lists.

## Acceptance Criteria

- [x] #1 `--fast` does not enumerate, open, hash, or resolve raw sources
- [x] #2 Fast output still reports route flags, forbidden flags, store status,
  schema/version, source document count, and ledger/projection integrity/counts;
  the multi-gigabyte source integrity/chunk scans are explicitly skipped
- [x] #3 Skipped freshness, orphan, redaction, and exact SourceRef checks are
  explicit `not_checked`/null states, never false zero-success claims
- [x] #4 Existing exact and `--deep` doctor behavior remains available and its
  stale/missing/redaction tests stay green
- [x] #5 Focused tests and a timed owner-vault fast smoke pass without mutation

## Evidence

Record focused tests and only aggregate owner-vault timing/status. Do not store
private source paths in repository evidence.

Implemented `health(..., fast=True)` and CLI `--fast`. The fast branch reads
SQLite schema/metadata and small ledger/projection counts but never calls the
raw inventory or exact SourceRef resolver; source quick/deep integrity and
passage-table counts are null because they scan the 2.5 GB source database.
The unflagged and `--deep` paths are unchanged.

Focused doctor/privacy/docs/backlog evidence: 16 passed. The existing exact
doctor tests still detect stale, missing, redacted, and changed-hash evidence.
Timed read-only owner-vault smoke: exit 0 in 546.8 ms, inventory
`not_checked`, source store `present` with 16,286 manifest documents, both
read routes disabled, ledger/projection absent, and `mutated=false`. The prior
unbounded run was stopped and is not counted as a pass.

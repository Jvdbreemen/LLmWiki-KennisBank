---
id: TASK-234
title: Add production migrations, doctor, rebuild, observability, and privacy controls
status: To Do
assignee: []
created_date: '2026-09-04 00:00'
labels:
  - operations
  - doctor
  - migration
  - privacy
dependencies:
  - TASK-228
  - TASK-229
  - TASK-230
  - TASK-233
ordinal: 177300
---

## Description

Make the two explicit read routes supportable in a real vault. Add reversible
migration, staged rebuild, health checks, aggregate metrics, retention and
redaction behavior, and tested recovery. Preserve the configured local vault
and fail-open clients.

## Planned Files

- update migration/setup scripts
- update `scripts/kb-projection-doctor.py`
- update rebuild and maintenance commands
- add privacy/observability schemas and tests

## Acceptance Criteria

- [ ] #1 Preflight reports legacy files, schema versions, counts, disk estimate, flags, and backup target without mutation
- [ ] #2 Migration is backed up, resumable, idempotent, and leaves legacy data intact
- [ ] #3 Doctor checks ledger integrity, projection versions, SourceRef coverage, stale/missing/contradictory counts, model compatibility, and forbidden flags
- [ ] #4 Rebuilds show bounded progress and atomically preserve the previous good projection on any failure
- [ ] #5 Retraction, supersession, source deletion, redaction, and changed hashes have tested projection effects
- [ ] #6 Logs/telemetry exclude prompts, passages, lessons, absolute personal paths, embeddings, and full refs
- [ ] #7 All behavior remains under `KENNISBANK_VAULT` with no hosted fallback
- [ ] #8 Temporary-vault setup, migration, doctor, rebuild, and rollback tests pass

## Evidence

Record sanitized preflight/doctor outputs, failure-injection tests, and privacy
field audit.

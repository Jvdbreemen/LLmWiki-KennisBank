---
id: TASK-227
title: Write failing production contract tests before implementation
status: Done
assignee: []
created_date: '2026-09-04 00:00'
updated_date: '2026-09-04 00:00'
labels:
  - tests-first
  - contracts
  - safety
  - regression
dependencies:
  - TASK-226
ordinal: 176600
---

## Description

Commit the production contracts as tests before changing feature code. The
first run must fail for the expected missing production behavior, and that red
baseline must be recorded. Keep fixtures synthetic; private holdout prompts and
passages stay outside the repository.

## Planned Files

- `tests/test_source_ref_contract.py`
- `tests/test_source_exact_hydration.py`
- `tests/test_experience_validation_policy.py`
- `tests/test_experience_projection_boundary.py`
- `tests/test_explicit_recall_policy.py`
- `tests/test_projection_migration.py`
- `tests/test_projection_privacy.py`
- extend `tests/test_kb_mcp.py`, `tests/test_settings.py`, and normal-recall regressions

## Acceptance Criteria

- [x] #1 Structured SourceRef, hash/offset validation, approved-root, traversal, symlink, redaction, stale, and missing-source cases are specified
- [x] #2 Tests prove extractors cannot self-validate and unreviewed/candidate/unknown records cannot be recalled as validated
- [x] #3 Tests require physically separate canonical ledger and rebuildable projection stores
- [x] #4 Tests forbid source embedding calls/vector tables and public advisory/fallback/ranking/promotion modes
- [x] #5 Tests specify labelled experience FTS fallback when embeddings are unavailable
- [x] #6 Normal recall compatibility and disabled-path p95 measurement are specified
- [x] #7 Migration interruption, idempotency, backup, and previous-good-index preservation are specified
- [x] #8 The red run is captured before implementation and failures match the intended gaps

## Evidence

Seven production contract files were added before feature implementation:
structured SourceRef and exact hydration, validation policy, ledger/projection
separation, explicit-route policy, migration/recovery, and aggregate-only
privacy. Existing normal retrieval already passed the isolation assertion.

Red baseline command:

`python -m pytest tests/test_source_ref_contract.py tests/test_source_exact_hydration.py tests/test_experience_validation_policy.py tests/test_experience_projection_boundary.py tests/test_explicit_recall_policy.py tests/test_projection_migration.py tests/test_projection_privacy.py -q`

The corrected baseline is 22 failed, 1 passed, and 1 skipped. The symlink
escape case is specified but skipped because this Windows environment did not
permit test symlink creation. Failures identify absent
`_source_ref.py`, `_experience_migration.py`, and `_projection_metrics.py`;
weak automatic validation; mixed ledger/projection storage; legacy coarse
flags; source vector/embedding code; public advisory/fallback modes; and the
missing structured-ref MCP argument. The single pass proves `kb-retrieve.py`
already has no direct source/experience gateway dependency. The repository's
existing TASK-215 benchmark remains the disabled-path p95 contract; TASK-236
will repeat it against the production implementation.

One initial failure was caused by a test helper named `_outcome`, which
collided with `unittest.TestCase` internals. It was renamed before recording
this baseline, so every remaining failure represents an intended product gap.

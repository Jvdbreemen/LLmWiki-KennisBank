---
id: TASK-227
title: Write failing production contract tests before implementation
status: In Progress
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

- [ ] #1 Structured SourceRef, hash/offset validation, approved-root, traversal, symlink, redaction, stale, and missing-source cases are specified
- [ ] #2 Tests prove extractors cannot self-validate and unreviewed/candidate/unknown records cannot be recalled as validated
- [ ] #3 Tests require physically separate canonical ledger and rebuildable projection stores
- [ ] #4 Tests forbid source embedding calls/vector tables and public advisory/fallback/ranking/promotion modes
- [ ] #5 Tests specify labelled experience FTS fallback when embeddings are unavailable
- [ ] #6 Normal recall compatibility and disabled-path p95 measurement are specified
- [ ] #7 Migration interruption, idempotency, backup, and previous-good-index preservation are specified
- [ ] #8 The red run is captured before implementation and failures match the intended gaps

## Evidence

Record the contract-only commit, exact test command, failed test names, and
why each failure is expected.

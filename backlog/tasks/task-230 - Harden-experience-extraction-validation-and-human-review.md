---
id: TASK-230
title: Harden experience extraction, validation, and human review
status: Done
assignee: []
created_date: '2026-09-04 00:00'
updated_date: '2026-09-05 00:00'
labels:
  - experience-memory
  - validation
  - human-review
  - safety
dependencies:
  - TASK-228
  - TASK-229
ordinal: 176900
---

## Description

Make extraction candidate-only and separate status, evidence state, and review
state. Add a review operation that records an immutable owner decision. A
validated record must have exact evidence, a task-consistent known outcome,
non-contradictory semantics, version stamps, and an accepted review.

## Planned Files

- update `scripts/_experience_extract.py`
- update `scripts/_experience.py`
- extend rebuild/review CLI or add `scripts/kb-experience-review.py`
- add/update command documentation and tests

## Acceptance Criteria

- [x] #1 Extraction always emits candidate/unreviewed regardless of model confidence
- [x] #2 Evidence state and review state are independent, explicit schema fields
- [x] #3 Validation checks every SourceRef and OutcomeRef plus session/task consistency
- [x] #4 Attempt, resolution, and final outcome states remain separate
- [x] #5 Unknown, missing, stale, contradictory, rejected, superseded, and retracted records cannot enter the production projection
- [x] #6 Review writes an append-only decision with actor, timestamp, reason, schema, and target content hash
- [x] #7 Re-extraction invalidates review when material lesson/evidence content changes
- [x] #8 Focused validation and lifecycle tests pass with zero candidate leakage

## Evidence

Record transition matrices, focused tests, and one synthetic changed-content
review invalidation example.

Implemented transition matrix:

| Exact evidence | Latest complete review | Lifecycle | Projection result |
| --- | --- | --- | --- |
| verified | accepted | candidate | validated |
| verified | unreviewed/rejected | candidate | candidate, skipped |
| unverified/missing/stale/contradictory/redacted | any | candidate | candidate, skipped |
| any | any | superseded/retracted | lifecycle preserved, skipped |

`_experience_extract.py` now always derives `candidate/unreviewed` records.
`_experience.py` recomputes SourceRef and OutcomeRef evidence from the vault,
requires matching session/task ownership and version stamps, chooses review
order by append order, fails closed on incomplete review rows, and binds each
review to all material lesson/evidence/link content. A manually cached
`evidence_state=verified` cannot bypass exact revalidation. Synthetic tests also
show that changed source or lesson content invalidates eligibility.

`kb-experience-review.py` adds read-only `list`/`inspect` operations and an
append-only `review` operation with actor, UTC timestamp, reason, schema,
content hash, and idempotency key. Review never promotes or writes the
projection. Operator usage is documented in `docs/experience-review.md`.

Focused Gate-B regression: `124 passed, 1 skipped` across all experience tests,
reviewed retrieval evaluation, layer CLI, SourceRef, source recall/chunk/index,
projection migration, and outcome ledger. The skip is the Windows symlink
fixture already documented by TASK-228. Isolated migration and removed-client
documentation regression: `4 passed`.

A full-suite diagnostic before the final targeted repairs reported `1851
passed, 4 skipped, 14 failed`. Four TASK-230/TASK-229 integration failures were
then repaired and rerun green. The ten intentionally unresolved failures are
nine prewritten contracts owned by TASK-231/TASK-233/TASK-234 plus the unrelated
pre-existing Windows `test_proc_bounded` timeout failure; they are not hidden as
TASK-230 evidence.

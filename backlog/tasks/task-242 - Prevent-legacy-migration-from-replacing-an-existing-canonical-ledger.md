---
id: TASK-242
title: Prevent legacy migration from replacing an existing canonical ledger
status: Done
assignee: []
created_date: '2026-09-08 17:14'
updated_date: '2026-09-09 05:56'
labels:
  - bug
  - production
  - migration
  - data-safety
dependencies: []
references:
  - docs/research/canonical-ledger-no-clobber-evidence-2026-09-08.md
ordinal: 181600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The legacy migration stages only legacy rows and unconditionally replaces the canonical target, so an already active ledger or a concurrent first capture can be lost. Fail closed on unmatched existing ledgers and use no-clobber publication for a new target. The current owner vault has no legacy mixed database, but the general upgrade path must still be safe.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Tests first reproduce replacement of an existing ledger and loss of a ledger created immediately before publication
- [x] #2 An unmatched existing canonical ledger is preserved byte-for-byte and requires explicit operator review; exact idempotent replay still works
- [x] #3 New target publication is atomic and cannot overwrite a concurrently created ledger; staging files are operation-unique and cleaned only by their owner
- [x] #4 Focused migration and full regression suites pass with sanitized evidence and no live canonical mutation
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add real temporary SQLite fixtures for existing and concurrent ledgers; record red. 2. Refuse unmatched existing targets and publish a staged new target using an atomic no-clobber operation, without inventing a merge or accepting legacy decisions. 3. Preserve backup and replay semantics and verify interruption cleanup. 4. Record focused/full proof and keep current owner data unchanged.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Red: 3 failed, 3 passed in 1.30s, proving existing and concurrent canonical-target replacement plus foreign-stage deletion. Repaired with target conflict reporting, operation-unique stages and atomic no-clobber hard-link publication; unsupported filesystems fail safely. Focused migration/versioning/store/boundary tests: 46 passed in 3.48s. Independent unittest: 8 passed in 0.487s. Owner-vault read-only preflight: no legacy mixed DB; current 42 events/42 outcomes/1 review remained untouched. Full-suite AC4 pending.

Verified 2026-09-09: clean 12c690ca679b23920a8437cd18e187b84fde62b8 JUnit reports 2035 tests, zero failures/errors, four skips (2031 passed), 708.772 seconds. SHA256 1700722884391b5426e9b5ecee1bd57759fd9c26dfb977b924761d5e1cca9f33. Later focused migration/doctor tests also pass. This closes migration mechanics, not owner-canary or release acceptance.
<!-- SECTION:NOTES:END -->

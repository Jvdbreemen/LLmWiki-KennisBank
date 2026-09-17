---
id: TASK-252
title: Keep research and evaluation tools out of the vault deploy
status: Done
assignee: []
created_date: '2026-09-17 17:02'
updated_date: '2026-09-17 17:02'
labels:
  - deploy
  - evaluation
dependencies: []
ordinal: 190600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
setup.sh deployed every scripts/*.py, so 28 research harnesses landed in every vault. Move them to scripts/dev/, delete the TASK-245 one-offs, and prune old vault copies on upgrade (ADR-012).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Tools that only tests and docs reference live in scripts/dev/ and are not deployed
- [x] #2 An upgraded vault loses the retired copies through a schema migration
- [x] #3 Runtime-coupled tools such as kb-eval.py stay deployed
- [x] #4 Full suite green except failures already present on HEAD
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Moved 25 test/doc-only research tools to scripts/dev/ (outside the deploy glob), deleted three TASK-245 fixture generators, added migration 0.39.0 with RETIRED_SCRIPTS and bumped _migrations.VERSION. Fixed the dev tools' repository boundary (parents[1] -> parents[2]) that the move had narrowed. Evidence: tests/test_migrations.py 36 passed (3 new tests red before the migration); full suite 2031 passed with 2 test_proc_bounded failures that also fail on clean HEAD; sandbox install of HEAD then setup.sh from this branch went 155 -> 127 deployed files, all 28 retired names gone, kb-eval.py/doctor.sh/memory-doctor.py/kb-retrieve.py kept, stamp 0.39.0.
<!-- SECTION:FINAL_SUMMARY:END -->

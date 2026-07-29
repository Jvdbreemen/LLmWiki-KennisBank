---
id: TASK-97
title: 'kb-eval --frozen: eval runs never write usage telemetry'
status: In Progress
assignee: []
created_date: '2026-07-29 19:23'
updated_date: '2026-07-29 19:46'
labels: []
dependencies: []
ordinal: 100700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Eval runs are sterile by construction AND self-restoring: kb-eval.py sets KB_USAGE_DISABLE=1 unconditionally in main() (no opt-in flag), prints an explicit stderr banner before (telemetry OFF) and after (telemetry restored) the run, and restores the previous env state via try/finally so in-process callers (long-lived hosts, tests, Claude Code sessions) get normal learning behavior back. _usage.enabled() returns False when the var is set; all writers gate on it. doctor.sh warns on a stray KB_USAGE_DISABLE in the environment (silent-empty failure guard, TASK-15 lesson). Verified adversarially (3-skeptic workflow, no refutations) plus before/after db-hash measurement.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _usage.enabled() returns False when KB_USAGE_DISABLE is set
- [ ] #2 test covers both
- [ ] #3 pytest suite green
- [ ] #4 kb-eval sets the guard unconditionally during the run and restores the previous env state after
- [ ] #5 stderr banner before (telemetry OFF) and after (restored) the eval output
- [ ] #6 doctor.sh warns on a stray KB_USAGE_DISABLE in the environment
<!-- AC:END -->

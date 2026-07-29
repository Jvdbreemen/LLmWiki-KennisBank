---
id: TASK-97
title: 'kb-eval --frozen: eval runs never write usage telemetry'
status: Done
assignee: []
created_date: '2026-07-29 19:23'
updated_date: '2026-07-29 21:17'
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
- [x] #1 _usage.enabled() returns False when KB_USAGE_DISABLE is set
- [x] #2 test covers both
- [x] #3 pytest suite green
- [x] #4 kb-eval sets the guard unconditionally during the run and restores the previous env state after
- [x] #5 stderr banner before (telemetry OFF) and after (restored) the eval output
- [x] #6 doctor.sh warns on a stray KB_USAGE_DISABLE in the environment
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
kb-eval now sets KB_USAGE_DISABLE=1 unconditionally for the duration of a run and restores the previous environment state in a try/finally, so an in-process caller (long-lived host, test, eval inside a Claude Code session) gets normal learning behaviour back. _usage.enabled() returns False while the variable is set, gating log_injected/mark_used/mark_noise. The run is framed on stderr (telemetry off before, restored after; a pre-existing disable is preserved and reported), leaving stdout clean for --json. doctor.sh warns on a stray KB_USAGE_DISABLE in the environment. Tests: full suite 1097 passed / 2 skipped; three new guard tests. Adversarial verification (3 skeptics: persistence, alternate writers, env inheritance) found no refutations. Known caveats: the read-only stats_for() path still runs CREATE TABLE IF NOT EXISTS on connect, so an eval can create an empty kb-usage.db while writing zero telemetry rows; and an eval still reads usage history, which is intended production parity. Merged as PR #87 (c9f5698). Copilot review unavailable on this PR (account quota limit) - merged on green CI plus local suite and adversarial verification instead.
<!-- SECTION:FINAL_SUMMARY:END -->

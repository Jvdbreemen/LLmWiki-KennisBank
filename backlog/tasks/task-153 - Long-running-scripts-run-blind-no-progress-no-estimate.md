---
id: TASK-153
title: 'Long-running scripts run blind: no progress, no estimate'
status: In Progress
assignee: []
created_date: '2026-08-13 17:31'
updated_date: '2026-08-13 17:32'
labels:
  - tooling
  - ux
  - performance
dependencies: []
priority: high
ordinal: 147700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every heavy path in this repo prints nothing until it is done. `memory-sweep.py` spent ten minutes writing nothing while `--help` accidentally swept the vault (TASK-148). `_maintenance.current_items()` reads and embeds 1500+ memories in silence. `build-kb-index.py` walks 1800 documents. A read-only measurement over the corpus produced zero bytes of output in more than ten minutes, which is indistinguishable from a hang.

That is the same failure class the last three tasks fixed one level down: a silence a reader cannot tell apart from a crash. Here it costs the user's attention rather than knowledge, but the fix has the same shape - say what is happening while it happens.

Add one shared helper, `scripts/_progress.py`, and use it on every path that can run longer than a few seconds. Rendering: percentage, a bar, done/total, elapsed, and an estimate extrapolated from the run so far. On a terminal it rewrites one line; in a pipe or a log it prints a throttled line, so output stays readable instead of becoming thousands of carriage returns.

Silence stays available and stays the default where it belongs: `KB_NO_PROGRESS=1` and a `quiet` flag, so hooks and the heartbeat keep their clean output. The helper must never raise into its caller - a progress bar that breaks the job it reports on is worse than no bar.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _progress.py renders percentage, bar, counts, elapsed and an ETA extrapolated from measured throughput
- [ ] #2 On a non-tty (pipe, log, background job) output is throttled to readable lines instead of carriage returns
- [ ] #3 KB_NO_PROGRESS=1 and quiet=True silence it completely, so hooks and heartbeats are unaffected
- [ ] #4 A failure inside the progress helper never propagates to the caller, proven by a test
- [ ] #5 current_items(), similar_pairs(), memory-sweep.py and build-kb-index.py report progress
- [ ] #6 An unknown total degrades to a counter plus elapsed rather than a wrong percentage
- [ ] #7 python -m pytest tests -q is green
<!-- AC:END -->

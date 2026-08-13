---
id: TASK-153
title: 'Long-running scripts run blind: no progress, no estimate'
status: In Progress
assignee: []
created_date: '2026-08-13 17:31'
updated_date: '2026-08-13 18:56'
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
- [x] #1 _progress.py renders percentage, bar, counts, elapsed and an ETA extrapolated from measured throughput
- [x] #2 On a non-tty (pipe, log, background job) output is throttled to readable lines instead of carriage returns
- [x] #3 KB_NO_PROGRESS=1 and quiet=True silence it completely, so hooks and heartbeats are unaffected
- [x] #4 A failure inside the progress helper never propagates to the caller, proven by a test
- [x] #5 current_items(), similar_pairs(), memory-sweep.py and build-kb-index.py report progress
- [x] #6 An unknown total degrades to a counter plus elapsed rather than a wrong percentage
- [x] #7 python -m pytest tests -q is green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
`_progress.py` gives every heavy path a percentage, a bar, counts, elapsed time and an estimate extrapolated from measured throughput. On a terminal it rewrites one line; in a pipe it prints a throttled line, so a log stays a log. `KB_NO_PROGRESS=1` and `quiet=True` keep hooks and heartbeats clean, and no failure inside the helper can reach its caller.

Wired into `current_items()`, `similar_pairs()`, `neighbor_counts()`, `memory-sweep.py` and `build-kb-index.py`. The sweep steps per transcript but also ticks per chunk, so a forty-chunk transcript with an LLM call per chunk no longer goes minutes without a sign of life.

One detail worth keeping: the triangular loops count PAIRS, not rows. Extrapolating from rows done overweights the wide early rows and overestimated by more than a factor of two (24 minutes predicted where 11 remained). Counting in the unit the work is actually in makes both the percentage and the estimate true.

It paid for itself on the first run. `similar_pairs` turned out to spend 15m26s on 1,271,315 comparisons to find ten pairs, and `neighbor_counts` walks the same triangle again — half an hour of CPU per sweep, invisible until now. That is TASK-154.

Not addressed here, worth knowing: the detached worker's stdout and stderr go to DEVNULL, so the automatic background sweep still shows nothing. The progress helps the human who runs a script by hand, which is where the waiting actually hurts.
<!-- SECTION:FINAL_SUMMARY:END -->
